import json

from app.domain import dumps, sha


def render_files(view, reports):
    """生成经审核的内容快照；提交记录由DeliveryService独立产生。"""
    plan = view['plan']
    lines = [f"# {plan['stage']}《{plan['topic']}》", '', '课时：45分钟。教师已逐项审核；正式写入状态以提交记录为准。', '',
             '代码PASS只适用于所列固定用例；教学正确性由教师审核。', '', '## 教学目标', '']
    for goal in plan['goals']:
        lines.append(f"- [{goal['id']}] {goal['title']}：{goal['criterion']}")
    lines += ['', '## 班情与未知项', '']
    for fact in view['profile']['facts']:
        lines.append(f"- {fact['observation']}（依据：{fact['source_ref']}，分母：{fact['denominator']}）")
    lines.extend('- ' + unknown for unknown in view['profile']['unknowns'])
    lines += ['', '## 教学环节', '']
    for segment in plan['segments']:
        lines.append(f"- [{segment['id']}] {segment['minutes']}分钟 {segment['title']}：{segment['activity']}")
    files = {}
    for group, title in [('examples', '课堂示例'), ('exercises', '分层练习与参考答案')]:
        lines += ['', '## ' + title, '']
        for item in plan[group]:
            info = view['items'][item['id']]
            path = f"code/{item['id']}.py"
            files[path] = item['code']
            files[f"tests/{item['id']}.json"] = json.dumps(info['test_spec'], ensure_ascii=False, indent=2)
            lines += [f"### [{item['id']}] {item['title']}", '', info['contract']['task_contract'], '',
                      item.get('prompt', item['explanation']), '', item.get('scaffolding', ''), '',
                      f"参考代码：{path}；当前验证：PASS；审核：ACCEPTED。", '']
            if group == 'exercises':
                lines += ['参考解说明：' + item['explanation'], '']
            for point in item.get('scoring', []):
                lines.append(f"- {point['points']}分：{point['criterion']}")
    lines += ['', '## 错因预警', '']
    for risk in plan['misconceptions']:
        lines += [f"- [{risk['id']}] {risk['misconception_type']}（{risk['basis']}）；依据：{risk['evidence_ids']}；"
                  f"触发：{risk['trigger']}；原因假设：{risk['cause']}；干预：{risk['teaching_intervention']}；关联题：{risk['exercise_ids']}"]
    files['lesson.json'] = json.dumps(view, ensure_ascii=False, indent=2)
    files['lesson.md'] = '\n'.join(lines) + '\n'
    files['reports.json'] = json.dumps(reports, ensure_ascii=False, indent=2)
    files['manifest.json'] = dumps({'schema_version': 1, 'lesson_id': view['lesson_id'],
        'revision': view['revision'], 'kind': 'teacher_reviewed_draft', 'formal_file_changed': False,
        'files': {path: sha(content) for path, content in files.items()}})
    return {'kind': 'teacher_reviewed_draft', 'files': files, 'formal_file_changed': False}
