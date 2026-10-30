"""离线材料与快照闸口回归。合成报告仅测试协议，不作真实执行证据。"""
import io
import json
import re
import zipfile
from html import unescape
from html.parser import HTMLParser

import pytest
from app.domain import AppError, dumps, now, sha, uid
from app.education.models import ReviewItem, ReviseItem
from app.education.render import render_files
from app.education.rules import suggested_plan
from app.verification.service import fingerprint
from conftest import ScriptedProvider


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.links.extend(value for key, value in attrs if key in {'href', 'src'})


@pytest.fixture
def reviewed(setup_agent):
    agent, store, session, root = setup_agent(ScriptedProvider())
    sid = session['id']
    with store.tx():
        profile = agent.education.import_profile(session, '40人，5人未交、3人死循环，刚学完条件语句。', 'text')
        view = agent.education.propose(session, suggested_plan(agent.education.profile(sid)), profile['id'], 1, 0)
        identity = {'ready': True, 'runtime_digest': 'SYNTHETIC_PROTOCOL_FIXTURE', 'runner_policy_hash': 'SYNTHETIC'}
        for did in view['bindings'].values():
            draft = store.get('drafts', did)
            spec = agent.verification.latest_spec(sid, draft['path'])
            report = {'id': uid(), 'session_id': sid, 'draft_id': did, 'path': draft['path'],
                      'code_hash': draft['content_hash'], 'test_spec_hash': spec['content_hash'],
                      'test_spec_revision': spec['id'], 'created_at': now(), 'status': 'PASS',
                      'fingerprint': fingerprint(draft['content_hash'], spec['content_hash'], identity),
                      'runtime_digest': identity['runtime_digest'], 'runner_policy_hash': identity['runner_policy_hash'],
                      'cases': [{**c, 'actual': c['expected'], 'stdout': c['expected'], 'stderr': '',
                                 'exit_code': 0, 'status': 'PASS', 'duration_ms': 0,
                                 'evidence': {'cleanup': True, 'synthetic_fixture': True}} for c in spec['cases']]}
            agent.verification.commit(report)
        for iid in view['items']:
            agent.education.review(session, view['lesson_id'], ReviewItem(expected_revision=1, item_id=iid,
                decision='accept', note='合成协议夹具，不代表教师专业审核或真实Runner执行'))
    return agent, store, session, root, agent.education.view(sid, view['lesson_id'])


def publish(reviewed):
    agent, _, session, _, view = reviewed
    files = agent.education.export(session['id'], view['lesson_id'])['files']
    with agent.store.tx():
        approval = agent.delivery.prepare(session, {f"published/{view['lesson_id']}/{p}": c for p, c in files.items()},
            lesson_id=view['lesson_id'], lesson_revision=view['revision'], lesson_hash=view['content_hash'])
    agent.delivery.decide(approval['id'], session['revision'], True)
    return files


def test_materials_are_offline_linked_complete_and_student_is_independent(reviewed):
    agent, _, session, _, view = reviewed
    files = agent.education.export(session['id'], view['lesson_id'])['files']
    html_files = [p for p in files if p.endswith('.html')]
    assert len(html_files) == 6
    for name in html_files:
        parser = Links()
        parser.feed(files[name])
        assert all(link in files for link in parser.links)
        assert not {'script', 'iframe', 'object', 'img', 'link'} & set(parser.tags)
        assert 'https://' not in files[name] and 'http://' not in files[name]
        assert '<html lang="zh-CN">' in files[name] and '@media print' in files[name]
    student = files['学生练习.html']
    links = Links()
    links.feed(student)
    assert links.links == []
    assert all(word not in student for word in ('参考解说明', '教师答案', '评分点', 'code/', 'lesson.json'))
    for i, item in enumerate(view['plan']['exercises'], 1):
        assert f"第{i}题（{item['level']}）" in student
        assert item['code'] not in student and item['explanation'] not in student
        assert f"第{i}题（{item['level']}）" in files['教师答案.html']
    for group, name in [('examples', '课堂示例.html'), ('exercises', '教师答案.html')]:
        rendered_codes = [unescape(c) for c in re.findall(r'<pre><code>(.*?)</code></pre>', files[name], re.S)]
        for item in view['plan'][group]:
            assert item['code'] in rendered_codes
            assert files[f"code/{item['id']}.py"] == item['code']
    assert all(x in files['教案.html'] for x in ('初二', '条件语句', '45分钟', '原因假设（待核实）', '5人', '3人'))
    assert '不能直接相加' in files['教案.html']
    assert '实际输出' in files['验证报告.html'] and '退出码：0' in files['验证报告.html']
    assert '请勿整包直接发给学生' in files['开始阅读.html']


def test_untrusted_text_and_code_are_escaped_and_preview_has_no_fake_report(reviewed):
    _, _, _, _, view = reviewed
    payload = '<script>alert("x")</script>&中文'
    item = view['plan']['examples'][0]
    item['title'] = payload
    item['explanation'] = payload
    item['code'] = 'print("<tag>&中文")\n'
    files = render_files(view, [])['files']
    assert '<script>' not in files['课堂示例.html']
    assert '&lt;script&gt;' in files['课堂示例.html']
    assert '&lt;tag&gt;&amp;中文' in files['课堂示例.html']
    assert '未取得当前有效通过证据' in files['验证报告.html']
    assert '验证结果：通过' not in files['验证报告.html']
    assert files[f"code/{item['id']}.py"] == item['code']


def test_current_report_only_and_archived_snapshot_round_trip(reviewed):
    agent, store, session, root, view = reviewed
    # 同一草稿旧报告保留在数据库，新有效报告才进入当前包。
    latest = store.find('reports', session['id'])[0]
    newer = {**latest, 'id': uid(), 'created_at': '2099-01-01T00:00:00Z'}
    with store.tx():
        agent.verification.commit(newer)
    files = publish(reviewed)
    selected = json.loads(files['reports.json'])
    assert len(selected) == 5 and latest['id'] not in [r['id'] for r in selected]
    assert newer['id'] in [r['id'] for r in selected]
    with zipfile.ZipFile(io.BytesIO(agent.delivery.archive(session, view['lesson_id']))) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(files) | {'delivery-receipt.json'}
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['kind'] == 'teacher_reviewed_content_snapshot'
        assert 'formal_file_changed' not in manifest
        receipt = json.loads(archive.read('delivery-receipt.json'))
        assert receipt['formal_file_changed'] is True
        assert all(sha(archive.read(p).decode()) == digest for p, digest in manifest['files'].items())
        assert all(archive.read(p) == (root / f"published/{view['lesson_id']}/{p}").read_bytes() for p in files)


@pytest.mark.parametrize('change', ['new_report', 'new_spec', 'external_file', 'incomplete_snapshot', 'rejected_item'])
def test_changed_or_rejected_material_cannot_download_old_commit(reviewed, change):
    agent, store, session, root, view = reviewed
    files = publish(reviewed)
    if change == 'new_report':
        report = store.find('reports', session['id'])[0]
        with store.tx():
            agent.verification.commit({**report, 'id': uid(), 'created_at': '2099-01-01T00:00:00Z'})
    elif change == 'new_spec':
        from app.verification.models import TestCase
        draft = store.get('drafts', next(iter(view['bindings'].values())))
        spec = agent.verification.latest_spec(session['id'], draft['path'])
        with store.tx():
            agent.verification.freeze(session['id'], draft['path'], [TestCase(**c) for c in spec['cases']])
    elif change == 'external_file':
        (root / f"published/{view['lesson_id']}/学生练习.html").write_text('外部修改')
    elif change == 'incomplete_snapshot':
        commit = store.find('commits', session['id'])[-1]
        commit['entries'] = commit['entries'][:-1]
        with store.tx():
            store.put('commits', commit)
    else:
        with store.tx():
            agent.education.review(session, view['lesson_id'], ReviewItem(expected_revision=1,
                item_id='goal-1', decision='reject', note='合成拒绝'))
    before = {p: (root / f"published/{view['lesson_id']}/{p}").read_bytes() for p in files}
    with pytest.raises(AppError):
        agent.delivery.archive(session, view['lesson_id'])
    assert before == {p: (root / f"published/{view['lesson_id']}/{p}").read_bytes() for p in files}


def test_export_does_not_change_reviewed_content_and_edits_invalidate(reviewed):
    agent, store, session, _, view = reviewed
    before = dumps(store.find('lessons', session['id']))
    agent.education.export(session['id'], view['lesson_id'])
    assert before == dumps(store.find('lessons', session['id']))
    item = view['plan']['examples'][0]
    with store.tx():
        agent.education.revise(session, view['lesson_id'], ReviseItem(expected_revision=1, item_id=item['id'],
            replacement={**item, 'code': item['code'] + '# 新版本\n'}, reason='合成版本变化'))
    with pytest.raises(AppError):
        agent.education.export(session['id'], view['lesson_id'])
