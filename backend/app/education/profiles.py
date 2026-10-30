import csv
import io
import json
import re

from app.domain import AppError, dumps, now, sha, uid
from app.education.models import ClassProfile, Fact, ProfileSource

LABELS = {'not_submitted': '未提交', 'infinite_loop': 'while死循环', 'boundary_error': '边界错误'}
PATTERNS = {
    'not_submitted': r'(\d+)\s*(?:人|名学生|位学生|名|位)?\s*(?:未交|没交|未提交|没提交)',
    'infinite_loop': r'(\d+)\s*(?:人|名学生|位学生|名|位)?\s*(?:出现|有|把)?\s*(?:while\s*)?(?:写成(?:了)?\s*)?(?:了)?死循环',
    'boundary_error': r'(\d+)\s*(?:人|名学生|位学生|名|位)?\s*(?:出现|有|犯了)?\s*边界错误',
}
REVERSE = {'not_submitted': r'(?:未交|没提交|未提交)\s*(\d+)\s*人',
           'infinite_loop': r'(?:while\s*)?死循环\s*(\d+)\s*人',
           'boundary_error': r'边界错误\s*(\d+)\s*人'}
SIZE_PATTERN = r'(?:班级(?:共|共有|有|人数[：:]?)|全班(?:共|共有|有)?|本班(?:共|共有|有)?|班上(?:共|共有|有)?)\s*((?:约|至少|至多|大概)?\s*[-−]?\d+(?:[.．]\d+)?)\s*(?:人|名学生)?'
PRIOR_PATTERN = r'(?:刚学完|已经学过|已学过|已学|学过)\s*((?:条件语句|变量|输入输出|列表|函数)(?:[、和与及]\s*(?:条件语句|变量|输入输出|列表|函数))*)'


def text_observations(content):
    for kind in PATTERNS:
        for pattern in (PATTERNS[kind], REVERSE[kind]):
            for match in re.finditer(pattern, content, re.I):
                yield kind, match


def request_profile_text(content):
    """只抽取明确的汇总班情片段；保留原文字符位置，排除假设和例题。"""
    selected = [None] * len(content)
    matches = [match for _, match in text_observations(content)
               if re.search(r'人|名|位|学生', match.group())]
    matches += list(re.finditer(SIZE_PATTERN, content)) + list(re.finditer(PRIOR_PATTERN, content))
    for match in matches:
        start = match.start()
        sentence = re.split(r'[。！？；;\n]', content[:start])[-1]
        clause = re.split(r'[，,]', sentence)[-1]
        if (re.search(r'假设|假如|例如|比如|如果|题目中|例题中|举例', sentence)
                or re.search(r'不要|并非|不是', clause)):
            continue
        if re.search(r'(?:没有|没|尚未|未曾|未)\s*$', clause):
            continue
        modifier = re.search(r'(?:[-−]\s*|\d+[.．]|(?:约|至少|至多|大概)\s*)$', content[:start])
        if modifier:
            start = modifier.start()
        selected[start:match.end()] = content[start:match.end()]
    if all(value is None for value in selected):
        return None
    return ''.join(value if value is not None else ('\n' if content[i] == '\n' else '。')
                   for i, value in enumerate(selected))


def profile_unknowns(facts, size, prior):
    unknowns = ['各类观察的学生集合交集未知，不能直接相加为不同学生人数。',
                '观察不能证明病因；变量更新、边界理解等原因均为待诊断假设。']
    if size is None:
        unknowns.append('班级总人数未知，不计算比例。')
    if not prior:
        unknowns.append('先修知识未确认，课前须由教师核对。')
    for kind in LABELS.keys() - {f.type for f in facts}:
        unknowns.append(f'{LABELS[kind]}人数未知，不能当作0人。')
    return unknowns


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


def parse_profile(content, format, stage, grade, revision=1, profile_id=None, *, allow_empty=False):
    """只保留汇总白名单字段；原文仅留Hash，定位不含姓名或原始行。"""
    if len(content.encode('utf-8')) > 1048576 or len(content.splitlines()) > 1000:
        invalid('导入上限为1 MiB、1000行。')
    size, prior, rows = None, [], []
    if format == 'text':
        sizes = re.findall(SIZE_PATTERN, content)
        if len(set(sizes)) > 1:
            invalid('班级人数存在冲突。')
        size = integer(sizes[0], '班级人数') if sizes else None
        for kind, match in text_observations(content):
            prefix = content[max(0, match.start(1) - 12):match.start(1)]
            if re.search(r'(?:[-−]\s*|\d+[.．]|(?:约|至少|至多|大概)\s*)$', prefix):
                invalid('文本人数必须是明确的非负整数，不能为负数、小数或约数。')
            rows.append((kind, match.group(1), None, f'text:{match.start()}-{match.end()}'))
        for match in re.finditer(PRIOR_PATTERN, content):
            if not re.search(r'(?:没有|没|尚未|未曾|未)\s*$', content[:match.start()]):
                prior.extend(re.findall(r'条件语句|变量|输入输出|列表|函数', match.group(1)))
        prior = list(dict.fromkeys(prior))
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
    if not facts and size is None and not prior and not allow_empty:
        invalid('未识别到汇总观察；请使用“5人未交、3人while死循环”或JSON/CSV模板。')
    unknowns = profile_unknowns(facts, size, prior)
    return ClassProfile(id=profile_id or uid(), revision=revision, stage=stage, grade=grade,
                        class_size=size, prior_knowledge=prior, source_hash=sha(content),
                        source_format=format, facts=facts, unknowns=unknowns, created_at=now())


def supplement_profile(previous, incoming):
    size = incoming.class_size if incoming.class_size is not None else previous.class_size
    if (previous.class_size is not None and incoming.class_size is not None
            and previous.class_size != incoming.class_size):
        raise AppError('CLASS_PROFILE_CONFLICT', '补充的班级人数与当前班情不同，请核实；如需更正，请明确选择整体替换。', 409)
    facts = {fact.type: fact.model_copy(deep=True) for fact in previous.facts}
    for fact in incoming.facts:
        old = facts.get(fact.type)
        if old and (old.count != fact.count or (old.denominator is not None and fact.denominator is not None
                                               and old.denominator != fact.denominator)):
            raise AppError('CLASS_PROFILE_CONFLICT', f'{LABELS[fact.type]}人数与已有观察冲突，请核实；不同来源不能直接累加，如需更正请选择整体替换。', 409)
        if old is None:
            facts[fact.type] = fact.model_copy(deep=True)
        elif old.denominator is None and fact.denominator is not None:
            old.denominator = fact.denominator
    for fact in facts.values():
        if fact.denominator is None:
            fact.denominator = size
        if (size is not None and fact.denominator is not None and fact.denominator != size
                or fact.denominator is not None and fact.count > fact.denominator):
            raise AppError('CLASS_PROFILE_CONFLICT', '补充后的观察人数或分母与班级人数不一致，请先核实。', 409)
        if not fact.source_hash:
            fact.source_hash = previous.source_hash
    prior = list(dict.fromkeys([*previous.prior_knowledge, *incoming.prior_knowledge]))
    if ([(f.type, f.count, f.denominator) for f in facts.values()]
            == [(f.type, f.count, f.denominator) for f in previous.facts]
            and size == previous.class_size and prior == previous.prior_knowledge):
        return previous
    sources = previous.sources or [ProfileSource(format=previous.source_format, source_hash=previous.source_hash, origin='legacy')]
    sources = list({(s.source_hash, s.origin): s for s in [*sources, *incoming.sources]}.values())
    return incoming.model_copy(update={'facts': list(facts.values()), 'class_size': size,
        'prior_knowledge': prior, 'sources': sources,
        'source_hash': sha(dumps([s.model_dump() for s in sources])),
        'unknowns': profile_unknowns(facts.values(), size, prior)})
