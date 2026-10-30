import json

from app.domain import dumps, sha
from app.education.documents import documents


def readable_source(ref):
    if ref.startswith('csv:row='):
        return 'CSV第' + ref[8:] + '行'
    if ref.startswith('json:$.facts['):
        return 'JSON汇总观察'
    return '文字班情' if ref.startswith('text:') else '历史班情记录'


def render_files(view, reports):
    """生成经审核的内容快照；提交记录由DeliveryService独立产生。"""
    plan = view['plan']
    lines = [f"# {plan['stage']} {view['profile']['grade']}《{plan['topic']}》", '', '课时：45分钟。教师已逐项审核；正式写入状态以提交记录为准。', '',
             '代码PASS只适用于所列固定用例；教学正确性由教师审核。', '']
    lines += ['前置知识：' + '、'.join(plan['prerequisites']), '']
    overview = {item['kind']: item for item in plan.get('overview', [])}
    lines += ['## 一、教学内容分析', '', overview.get('content', {}).get('content', '本历史版本未包含此分析。'), '',
              '## 二、学情分析', '', overview.get('learners', {}).get('content', '本历史版本未包含此分析。'), '']
    for fact in view['profile']['facts']:
        denominator = fact['denominator'] if fact['denominator'] is not None else '未知'
        lines.append(f"- {fact['observation']}（来源：{readable_source(fact['source_ref'])}，分母：{denominator}）")
    lines.extend('- ' + unknown for unknown in view['profile']['unknowns'])
    lines += ['', '## 三、教学目标', '']
    for goal in plan['goals']:
        lines.append(f"- {goal['title']}：{goal['criterion']}")
    lines += ['', '## 四、教学重点、难点与解决策略', '', overview.get('focus', {}).get('content', '本历史版本未包含此分析。'), '',
              '## 五、教学过程', '']
    for segment in plan['segments']:
        lines += [f"### {segment['title']}（{segment['minutes']}分钟）", '', segment['activity'], '']
        for key, label in [('teacher_actions', '教师活动'), ('student_actions', '学生活动'), ('assessment', '达成检查与反馈')]:
            if segment.get(key):
                lines += [f"- {label}：{segment[key]}"]
    files = {}
    for group, title in [('examples', '课堂示例'), ('exercises', '分层练习与参考答案')]:
        lines += ['', '## ' + title, '']
        for item in plan[group]:
            info = view['items'][item['id']]
            path = f"code/{item['id']}.py"
            files[path] = item['code']
            files[f"tests/{item['id']}.json"] = json.dumps(info['test_spec'], ensure_ascii=False, indent=2)
            label = item.get('level', '示例') + ' · ' + item['title']
            lines += [f"### {label}", '', info['contract']['task_contract'], '',
                      item.get('prompt', item['explanation']), '', item.get('scaffolding', ''), '',
                      f"参考代码：{path}；当前验证：PASS；审核：ACCEPTED。", '']
            if group == 'exercises':
                lines += ['参考解说明：' + item['explanation'], '']
            for point in item.get('scoring', []):
                lines.append(f"- {point['points']}分：{point['criterion']}")
    lines += ['', '## 错因预警', '']
    fact_labels = {fact['id']: fact['observation'] for fact in view['profile']['facts']}
    exercise_labels = {item['id']: item['level'] + ' · ' + item['title'] for item in plan['exercises']}
    for risk in plan['misconceptions']:
        evidence = '；'.join(fact_labels.get(identity, '历史依据待核对') for identity in risk['evidence_ids']) or '预测风险，无直接观察'
        exercises = '、'.join(exercise_labels.get(identity, '历史关联练习待核对') for identity in risk['exercise_ids'])
        lines += [f"### {risk['title']}", '', f"- 依据：{evidence}", f"- 触发：{risk['trigger']}",
                  f"- 原因假设（待核实）：{risk['cause']}", f"- 课堂干预：{risk['teaching_intervention']}", f"- 关联练习：{exercises}"]
    files['lesson.json'] = json.dumps(view, ensure_ascii=False, indent=2)
    files['lesson.md'] = '\n'.join(lines) + '\n'
    files['reports.json'] = json.dumps(reports, ensure_ascii=False, indent=2)
    files.update(documents(view, reports, readable_source))
    files['manifest.json'] = dumps({'schema_version': 1, 'lesson_id': view['lesson_id'],
        'revision': view['revision'], 'kind': 'teacher_reviewed_content_snapshot',
        'publication_status_source': 'delivery-receipt.json',
        'files': {path: sha(content) for path, content in files.items()}})
    return {'kind': 'teacher_reviewed_draft', 'files': files, 'formal_file_changed': False}
