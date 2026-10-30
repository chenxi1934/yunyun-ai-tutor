"""确定性离线教师材料；不调用模型，不改写已审核的教学文字或代码。"""
from html import escape

STYLE = """+:root{font-family:system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;color:#292635;background:#faf9fc;line-height:1.7}
body{max-width:960px;margin:32px auto;padding:0 24px}h1{font-size:28px}h2{margin-top:32px;border-bottom:1px solid #ded8e8;padding-bottom:8px}h3{margin-top:24px}
a{color:#61469b;text-underline-offset:3px}a:focus-visible{outline:2px solid #61469b;outline-offset:4px}
nav{display:flex;flex-wrap:wrap;gap:8px 20px;padding:12px 0;border-bottom:1px solid #ded8e8}p{white-space:pre-wrap;overflow-wrap:anywhere}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f0edf5;padding:12px;border-radius:6px;line-height:1.5}code{font-family:ui-monospace,monospace}
table{border-collapse:collapse;width:100%;margin:16px 0;table-layout:fixed}th,td{border:1px solid #d9d3e3;padding:8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#f0edf5}td pre{margin:0;padding:4px;background:transparent}
.notice{border-left:4px solid #8668b4;background:#f0edf5;padding:12px 16px}.meta{font-size:14px;color:#625b70}section{margin:24px 0}li{margin:6px 0}
@media(max-width:600px){body{margin:16px auto;padding:0 12px}h1{font-size:24px}th,td{padding:5px;font-size:14px}}
@media print{body{max-width:none;margin:0;padding:0;background:white;color:black}nav,.no-print{display:none}h2,h3{break-after:avoid}pre,tr{break-inside:avoid}a{color:inherit;text-decoration:none}.notice,th,pre{background:white}}
"""

PAGES = [('开始阅读.html', '材料目录'), ('教案.html', '教案与错因'),
         ('课堂示例.html', '课堂示例'), ('学生练习.html', '学生练习'),
         ('教师答案.html', '教师答案'), ('验证报告.html', '验证报告')]


def text(value):
    return escape(str(value), quote=True)


def paragraph(value):
    return '<p>' + text(value) + '</p>'


def listing(values):
    return '<ul>' + ''.join('<li>' + text(v) + '</li>' for v in values) + '</ul>'


def code(value):
    return '<pre><code>' + text(value) + '</code></pre>'


def table(headers, rows):
    # Cell content is already escaped/rendered by this module, never model HTML.
    return ('<table><thead><tr>' + ''.join('<th scope="col">' + text(h) + '</th>' for h in headers)
            + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + c + '</td>' for c in row)
              + '</tr>' for row in rows) + '</tbody></table>')


def page(title, body, view, *, student=False):
    # 学生文件独立成文，无教师导航、答案链接或共享数据依赖。
    navigation = '' if student else '<nav aria-label="材料目录">' + ''.join(
        f'<a href="{path}">{label}</a>' for path, label in PAGES) + '</nav>'
    metadata = (f"{view['plan']['stage']} · {view['profile']['grade']} · {view['plan']['topic']}"
                f" · {view['plan']['duration_minutes']}分钟 · 第{view['revision']}版")
    return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
            'style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
            f'<title>{text(title)}</title><style>{STYLE}</style></head><body>{navigation}'
            f'<main><h1>{text(title)}</h1><p class="meta">{text(metadata)}</p>{body}</main></body></html>')


def io_table(cases, *, actual=False):
    headers = ['用例', '标准输入', '预期输出']
    if actual:
        headers += ['实际输出', '结果']
    rows = []
    for case in cases:
        row = [text(case['id']), code(case['input'] or '（空输入）'), code(case['expected'] or '（无输出）')]
        if actual:
            state = {'PASS': '通过', 'TIMEOUT': '超时', 'OUTPUT_MISMATCH': '输出不符',
                     'SYNTAX_ERROR': '语法错误', 'RUNTIME_ERROR': '运行异常'}.get(case['status'], '未通过')
            detail = (f"{state}；退出码：{case['exit_code'] if case['exit_code'] is not None else '无'}；"
                      f"耗时：{case['duration_ms']:.1f}毫秒")
            row += [code(case['actual'] or '（无输出）'), text(detail)]
        rows.append(row)
    return table(headers, rows)


def documents(view, reports, source_label):
    plan, profile = view['plan'], view['profile']
    report_by_draft = {r['draft_id']: r for r in reports}
    body = ('<div class="notice">本包包含参考答案，请勿整包直接发给学生。'
            '只需单独复制“学生练习.html”即可发放；它不依赖其他文件。</div>'
            + paragraph('解压后双击本文件，在浏览器阅读。所有网页可断网打开，并可用浏览器“打印”保存或打印；阅读无需安装本项目或 Python。')
            + table(['材料', '用途'], [[f'<a href="{path}">{label}</a>', text(use)] for (path, label), use in zip(PAGES[1:], [
                '教学目标、前置知识、45分钟过程、班情事实与错因干预',
                '示例代码、输入输出和课堂讲解', '独立学生题目，不含参考代码、解题说明和评分解析',
                '按相同题号查找参考解、解题说明和评分点', '当前代码版本的真实输出、用例和技术证据'], strict=True)])
            + '<h2>代码与可选技术数据</h2>'
            + paragraph('code/ 保留每个示例与参考解的原始 .py 文件；课堂示例、教师答案中提供对应链接。运行这些文件需要 Python 3.12：在解压目录打开终端，运行 python3 code/文件名.py，再按题目输入整数并回车。阅读网页不需要运行代码。')
            + paragraph('lesson.md 可供文本编辑；lesson.json、tests/、reports.json 和 manifest.json 用于程序复用与证据核对，教师阅读无需打开。正式交付状态见 delivery-receipt.json；审批前的内容快照不等于已写入文件。')
            + '<h2>使用边界</h2>' + paragraph('代码通过只表示配套固定用例通过，不代表所有输入或教学文字均正确。教学适配、超纲风险、课堂使用和评分仍须教师把关。'))
    result = {'开始阅读.html': page('循环结构 · 备课材料目录', body, view)}
    overview = {s['kind']: s['content'] for s in plan.get('overview', [])}
    body = '<h2>前置知识</h2>' + listing(plan['prerequisites'])
    body += '<h2>一、教学内容分析</h2>' + paragraph(overview.get('content', '本历史版本未包含此分析，请教师补充审核。'))
    body += '<h2>二、学情分析</h2>' + paragraph(overview.get('learners', '本历史版本未包含此分析，请教师补充审核。'))
    body += '<h3>已导入的班情事实</h3>' + listing([
        f"{f['observation']}；来源：{source_label(f['source_ref'])}；统计分母：{f['denominator'] if f['denominator'] is not None else '未知'}"
        for f in profile['facts']]) + listing(profile['unknowns'])
    body += '<h2>三、教学目标</h2>' + listing([g['title'] + '：' + g['criterion'] for g in plan['goals']])
    body += '<h2>四、教学重点、难点与解决策略</h2>' + paragraph(overview.get('focus', '本历史版本未包含此分析，请教师补充审核。'))
    body += '<h2>五、教学过程</h2>' + table(['环节', '时间', '活动与反馈'], [
        [text(s['title']), text(str(s['minutes']) + '分钟'), paragraph(s['activity']) + ''.join(
            paragraph(label + '：' + s[key]) for key, label in [('teacher_actions', '教师活动'),
            ('student_actions', '学生任务'), ('assessment', '达成检查与反馈')] if s.get(key))] for s in plan['segments']])
    body += paragraph(f"总时间：{sum(s['minutes'] for s in plan['segments'])}分钟。")
    body += '<h2>错因预警与提前干预</h2>'
    facts = {f['id']: f['observation'] for f in profile['facts']}
    labels = {e['id']: f"第{i}题（{e['level']}）：{e['title']}" for i, e in enumerate(plan['exercises'], 1)}
    for risk in plan['misconceptions']:
        evidence = '；'.join(facts.get(i, '历史依据待核对') for i in risk['evidence_ids']) or '知识点预测，无直接班情观察'
        body += '<section><h3>' + text(risk['title']) + '</h3>' + listing([
            '依据：' + evidence, '触发情境：' + risk['trigger'], '原因假设（待核实）：' + risk['cause'],
            '提前干预：' + risk['teaching_intervention'],
            '关联练习：' + '；'.join(labels.get(i, '历史练习待核对') for i in risk['exercise_ids'])]) + '</section>'
    result['教案.html'] = page('循环结构 · 教案与错因预警', body, view)
    examples, student, answers, verification = '', '', '', paragraph('下列结果只对应本包代码及所列固定用例；不代替教师专业审核。')
    for group in ['examples', 'exercises']:
        for number, item in enumerate(plan[group], 1):
            info = view['items'][item['id']]
            title = (f"示例{number}：{item['title']}" if group == 'examples'
                     else f"第{number}题（{item['level']}）：{item['title']}")
            heading = '<h2>' + text(title) + '</h2>'
            task = paragraph(info['contract']['task_contract'])
            if group == 'exercises':
                if item['prompt'] != info['contract']['task_contract']:
                    task += paragraph(item['prompt'])
                if item.get('scaffolding'):
                    task += paragraph('学习支架：' + item['scaffolding'])
                student += heading + task + io_table(info['contract']['cases'])
            path = 'code/' + item['id'] + '.py'
            reference = (paragraph(('讲解：' if group == 'examples' else '参考解说明：') + item['explanation'])
                         + f'<p><a href="{path}">打开对应 Python 代码</a> · 运行命令：</p>'
                         + code('python3 ' + path) + code(item['code']))
            report = report_by_draft.get(info['draft_id'])
            status = '通过（固定用例）' if report and report['status'] == 'PASS' and info.get('current_pass') else '未取得当前有效通过证据'
            reference += paragraph('代码验证：' + status)
            if group == 'examples':
                examples += heading + task + reference + io_table(info['contract']['cases'])
            else:
                answers += heading + task + reference + '<h3>评分点（总分100分）</h3>' + listing([
                    f"{p['points']}分：{p['criterion']}" for p in item['scoring']])
            verification += heading + paragraph('对应代码：' + path + '；验证结果：' + status)
            if report:
                verification += paragraph('执行时间：' + report['created_at']) + io_table(report['cases'], actual=True)
                for case in report['cases']:
                    if case.get('error') or case.get('stderr'):
                        verification += paragraph('用例 ' + case['id'] + ' 的诊断') + code(case.get('error') or '') + code(case.get('stderr') or '')
                verification += '<details><summary>版本与运行环境证据</summary>' + listing([
                    '代码SHA-256：' + report['code_hash'], '测试规格SHA-256：' + report['test_spec_hash'],
                    '用例版本：' + report['test_spec_revision'], '运行环境：' + report['runtime_digest'],
                    '隔离策略：' + report['runner_policy_hash'], '验证指纹：' + report['fingerprint']]) + '</details>'
    result['课堂示例.html'] = page('循环结构 · 课堂示例', examples, view)
    result['学生练习.html'] = page('循环结构 · 分层练习', student, view, student=True)
    result['教师答案.html'] = page('循环结构 · 教师答案与评分点', answers, view)
    result['验证报告.html'] = page('循环结构 · 代码验证报告', verification, view)
    return result
