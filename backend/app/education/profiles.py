import csv
import io
import json
import re

from app.domain import AppError, now, sha, uid
from app.education.models import ClassProfile, Fact

LABELS = {'not_submitted': '未提交', 'infinite_loop': 'while死循环', 'boundary_error': '边界错误'}
PATTERNS = {
    'not_submitted': r'(\d+)\s*人?\s*(?:未交|没交|未提交|没提交)',
    'infinite_loop': r'(\d+)\s*人?\s*(?:把\s*)?(?:while\s*)?(?:写成(?:了)?\s*)?(?:了)?死循环',
    'boundary_error': r'(\d+)\s*人?\s*(?:出现|有|犯了)?\s*边界错误',
}


def invalid(message):
    raise AppError('INVALID_CLASS_DATA', message, 422)


def integer(value, location, nullable=False):
    if nullable and value in (None, ''):
        return None
    if isinstance(value, bool) or not re.fullmatch(r'\d+', str(value)):
        invalid(f'{location}须为非负整数。')
    result = int(value)
    if result > 1000:
        invalid(f'{location}不能超过1000。')
    return result


def parse_profile(content, format, stage, grade, revision=1, profile_id=None):
    """只保留汇总白名单字段；原文仅留Hash，定位不含姓名或原始行。"""
    if len(content.encode('utf-8')) > 1048576 or len(content.splitlines()) > 1000:
        invalid('导入上限为1 MiB、1000行。')
    size, prior, rows = None, [], []
    if format == 'text':
        # 负数不能被正数正则局部匹配后悄悄变为正数。
        if re.search(r'-\s*\d|\d+[.．]\d+\s*人|(?:约|至少|至多|大概)\s*\d', content):
            invalid('文本人数必须是明确的非负整数，不能为负数、小数或约数。')
        sizes = re.findall(r'(?:班级共|全班|班级人数[：:]?)\s*(\d+)\s*人?', content)
        if len(set(sizes)) > 1:
            invalid('班级人数存在冲突。')
        size = integer(sizes[0], '班级人数') if sizes else None
        for kind, pattern in PATTERNS.items():
            matches = list(re.finditer(pattern, content, re.I))
            # 同时支持“未交5人”“死循环3人”。
            reverse = {'not_submitted': r'(?:未交|没提交|未提交)\s*(\d+)\s*人',
                       'infinite_loop': r'(?:while\s*)?死循环\s*(\d+)\s*人',
                       'boundary_error': r'边界错误\s*(\d+)\s*人'}[kind]
            matches += list(re.finditer(reverse, content, re.I))
            for match in matches:
                rows.append((kind, match.group(1), None, f'text:{match.start()}-{match.end()}'))
        if re.search(r'刚学完|已学', content) and '条件语句' in content:
            prior = ['条件语句']
    elif format == 'json':
        def unique_fields(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    invalid('JSON包含重复字段，请先核实冲突。')
                result[key] = value
            return result
        try:
            data = json.loads(content, object_pairs_hook=unique_fields)
        except ValueError:
            invalid('JSON语法错误。')
        if not isinstance(data, dict) or not isinstance(data.get('facts'), list):
            invalid('JSON须为包含facts数组的对象。')
        size = integer(data.get('class_size'), 'class_size', True)
        # 只允许已知课程术语，防止把原始个人信息传入模型。
        values = data.get('prior_knowledge', [])
        if not isinstance(values, list):
            invalid('prior_knowledge须为数组。')
        prior = [x for x in values if x in ('条件语句', '变量', '输入输出', '列表', '函数')]
        for i, fact in enumerate(data['facts']):
            if not isinstance(fact, dict):
                invalid(f'facts[{i}]须为对象。')
            rows.append((fact.get('type'), fact.get('count'), fact.get('denominator'), f'json:$.facts[{i}]'))
    elif format == 'csv':
        try:
            reader = csv.DictReader(io.StringIO(content.lstrip('\ufeff')), strict=True)
            if not reader.fieldnames or not {'type', 'count'} <= set(reader.fieldnames):
                invalid('CSV需要type,count列；可选class_size,denominator。')
            if len(set(reader.fieldnames)) != len(reader.fieldnames):
                invalid('CSV不能包含重复列名。')
            sizes = set()
            for i, row in enumerate(reader, 2):
                if None in row or any(row.get(k) is None for k in ('type', 'count')):
                    invalid(f'CSV第{i}行列数错误。')
                if row.get('class_size'):
                    sizes.add(integer(row['class_size'], f'CSV第{i}行class_size'))
                rows.append((row['type'], row['count'], row.get('denominator'), f'csv:row={i}'))
            if len(sizes) > 1:
                invalid('CSV的class_size存在冲突。')
            size = next(iter(sizes), None)
        except csv.Error:
            invalid('CSV格式错误。')
    else:
        invalid('不支持的班情格式。')
    if size == 0:
        invalid('班级人数须大于0或保持未知。')
    facts, seen = [], {}
    for kind, count, denominator, ref in rows:
        if kind not in LABELS:
            invalid(f'{ref}的type不在允许的三类汇总观察中。')
        count = integer(count, ref + '.count')
        denominator = integer(denominator, ref + '.denominator', True)
        if denominator == 0 or (size and denominator and denominator != size):
            invalid(f'{ref}分母必须与班级人数一致。')
        denominator = denominator or size
        if denominator is not None and count > denominator:
            invalid(f'{ref}计数超过分母。')
        if kind in seen:
            if seen[kind] != (count, denominator):
                invalid(f'{ref}与已有同类观察冲突，请教师核实。')
            continue
        seen[kind] = (count, denominator)
        facts.append(Fact(id='fact-' + kind, type=kind, count=count, denominator=denominator,
                          source_ref=ref, observation=f'{LABELS[kind]}：{count}人'))
    if not facts:
        invalid('未识别到汇总观察；请使用“5人未交、3人while死循环”或JSON/CSV模板。')
    unknowns = ['各类观察的学生集合交集未知，不能直接相加为不同学生人数。',
                '观察不能证明病因；变量更新、边界理解等原因均为待诊断假设。']
    if size is None:
        unknowns.append('班级总人数未知，不计算比例。')
    if not prior:
        unknowns.append('先修知识未确认，课前须由教师核对。')
    for kind in LABELS.keys() - seen.keys():
        unknowns.append(f'{LABELS[kind]}人数未知，不能当作0人。')
    return ClassProfile(id=profile_id or uid(), revision=revision, stage=stage, grade=grade,
                        class_size=size, prior_knowledge=prior, source_hash=sha(content),
                        source_format=format, facts=facts, unknowns=unknowns, created_at=now())
