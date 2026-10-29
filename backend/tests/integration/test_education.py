"""真实阶段03 Runner纵向测试；没有Runner配置就失败，不使用执行Mock。"""
import json
import os
from pathlib import Path

import pytest
from app.domain import AppError, dumps, sha
from app.education.models import ReviewItem, ReviseItem
from app.education.rules import suggested_plan
from app.verification.runner import RemoteRunner
from conftest import ScriptedProvider

A = '班级共40人，刚学完条件语句；5人未交、3人while死循环。'
B = 'type,count,class_size\nnot_submitted,0,40\ninfinite_loop,0,40\nboundary_error,8,40\n'


def prepare(setup_agent, stage='初中', text=A, format='text', bad_code=None):
    agent, store, session, root = setup_agent(ScriptedProvider())
    session['context'].update(stage=stage, grade='初二' if stage == '初中' else '大一')
    agent.verification.runner = RemoteRunner(Path(os.environ['YUNYUN_TEST_RUNNER_SOCKET']),
                                           os.environ['YUNYUN_TEST_RUNNER_TOKEN'])
    with store.tx():
        store.put('sessions', session)
        profile = agent.education.import_profile(session, text, format)
        plan = suggested_plan(agent.education.profile(session['id']))
        if bad_code:
            plan.exercises[0].code = bad_code
        view = agent.education.propose(session, plan, profile['id'], 1, 0)
    return agent, store, session, root, view


@pytest.mark.parametrize('stage,text,format', [('初中', A, 'text'), ('初中', B, 'csv'), ('大学', A, 'text')])
async def test_full_plan_all_examples_answers_real_runner(setup_agent, stage, text, format, record_property):
    agent, store, session, root, view = prepare(setup_agent, stage, text, format)
    sid, lid = session['id'], view['lesson_id']
    assert not view['candidate_ready'] and not view['delivery_ready']
    view = await agent.education.verify(sid, lid, 1)
    reports = store.find('reports', sid)
    assert len(reports) == 5 and all(r['status'] == 'PASS' for r in reports)
    assert view['code_status'] == 'PASS' and view['candidate_ready']
    assert not view['delivery_ready'] and view['teacher_review_status'] == 'PENDING'
    for item in [*view['plan']['examples'], *view['plan']['exercises']]:
        info = view['items'][item['id']]
        report = next(r for r in reports if r['draft_id'] == info['draft_id'])
        assert report['code_hash'] == sha(item['code'])
        assert [(c['id'], c['input'], c['expected']) for c in report['cases']] == [
            (c['id'], c['input'], c['expected']) for c in info['contract']['cases']]
        assert all(c['actual'] == c['expected'] and c['exit_code'] == 0 and c['evidence']['cleanup'] for c in report['cases'])
    with pytest.raises(AppError):
        agent.education.export(sid, lid)
    # 显式合成教师决策，仅验证审核机制，不冒充真实教师教育判断。
    with store.tx():
        for item_id in view['items']:
            agent.education.review(session, lid, ReviewItem(expected_revision=1, item_id=item_id,
                decision='accept', note='合成教师动作：验证逐项审核协议，不代表人工教育审查'))
    package = agent.education.export(sid, lid)
    manifest = json.loads(package['files']['manifest.json'])
    assert all(sha(package['files'][p]) == h for p, h in manifest['files'].items())
    assert len([p for p in package['files'] if p.endswith('.py')]) == 5
    assert '分：' in package['files']['lesson.md']
    assert all(e['explanation'] in package['files']['lesson.md'] for e in view['plan']['exercises'])
    assert sorted(p.name for p in root.iterdir()) == ['fixture.md']
    record_property('education_evidence', dumps({'lesson': agent.education.view(sid, lid),
                    'reports': reports, 'manifest': manifest, 'review_source': 'synthetic teacher actions'}))


async def test_failure_repair_single_edit_and_rejection(setup_agent, record_property):
    bad = 'n=int(input())\nwhile n>=0:\n    print(n)\n    n-=1\n'
    agent, store, session, _, view = prepare(setup_agent, bad_code=bad)
    sid, lid = session['id'], view['lesson_id']
    failed = await agent.education.verify(sid, lid, 1)
    assert not failed['candidate_ready'] and not failed['delivery_ready']
    original_reports = store.find('reports', sid)
    failed_report = next(r for r in original_reports if r['draft_id'] == view['bindings']['exercise-1'])
    assert failed_report['status'] == 'OUTPUT_MISMATCH'
    assert failed_report['cases'][0]['expected'] == '' and failed_report['cases'][0]['actual'] == '0\n'
    specs_before = {s['path']: s['id'] for s in store.find('test_specs', sid)}
    good = suggested_plan(agent.education.profile(sid)).exercises[0].model_dump()
    with store.tx():
        updated = agent.education.revise(session, lid, ReviseItem(expected_revision=1,
            item_id='exercise-1', replacement=good, reason='修正n=0时不应输出0'))
    assert updated['revision'] == 2
    assert updated['items']['exercise-1']['verification_status'] == 'NOT_TESTED'
    assert all(updated['bindings'][i] == view['bindings'][i] for i in view['bindings'] if i != 'exercise-1')
    passed = await agent.education.verify(sid, lid, 2)
    assert passed['candidate_ready'] and not passed['delivery_ready']
    assert len(store.find('reports', sid)) == 6  # 只重测修改后的参考解。
    assert specs_before == {s['path']: s['id'] for s in store.find('test_specs', sid)}
    with store.tx():
        for item_id in passed['items']:
            agent.education.review(session, lid, ReviewItem(expected_revision=2, item_id=item_id, decision='accept', note='合成教师审核'))
        agent.education.review(session, lid, ReviewItem(expected_revision=2, item_id='exercise-1', decision='reject', note='合成教师拒绝：解释需调整'))
    with pytest.raises(AppError):
        agent.education.export(sid, lid)
    with store.tx():
        edited = agent.education.revise(session, lid, ReviseItem(expected_revision=2, item_id='exercise-1',
            replacement={**good, 'code': good['code'] + '# 教师补充追踪说明\n'}, reason='补充说明'))
    assert edited['items']['exercise-1']['review_status'] == 'PENDING'
    assert edited['items']['risk-infinite_loop']['review_status'] == 'PENDING'
    assert edited['items']['example-1']['review_status'] == 'ACCEPTED'
    assert store.get('drafts', passed['bindings']['exercise-1'])['verification_status'] == 'STALE'
    assert store.get('reports', failed_report['id']) == failed_report
    assert not edited['candidate_ready']
    record_property('failure_repair_history', dumps({'versions': store.find('lessons', sid),
        'reports': store.find('reports', sid), 'reviews': store.find('education_reviews', sid)}))


@pytest.mark.parametrize('bad,status', [('for i in range(2)\n print(i)', 'SYNTAX_ERROR'), ('while True: pass', 'TIMEOUT')])
async def test_failed_answer_never_becomes_candidate(setup_agent, bad, status, record_property):
    agent, store, session, _, view = prepare(setup_agent, bad_code=bad)
    view = await agent.education.verify(session['id'], view['lesson_id'], 1)
    assert view['items']['exercise-1']['verification_status'] == status
    assert not view['candidate_ready']
    assert len(store.find('reports', session['id'])) == 5  # 不能因一个失败漏测其余答案。
    with pytest.raises(AppError):
        agent.education.export(session['id'], view['lesson_id'])
    record_property('failed_answer', dumps({'lesson': view, 'reports': store.find('reports', session['id'])}))


async def test_code_pass_does_not_hide_curriculum_risk(setup_agent, record_property):
    agent, store, session, _, view = prepare(setup_agent)
    item = view['plan']['examples'][0]
    with store.tx():
        view = agent.education.revise(session, view['lesson_id'], ReviseItem(expected_revision=1,
            item_id=item['id'], replacement={**item, 'code': 'def extra():\n    pass\n' + item['code']},
            reason='合成超纲探针：保持输出相同'))
    view = await agent.education.verify(session['id'], view['lesson_id'], 2)
    assert view['code_status'] == 'PASS'
    assert view['curriculum_risks'] and not view['candidate_ready'] and not view['delivery_ready']
    record_property('curriculum_block', dumps({'lesson': view, 'reports': store.find('reports', session['id'])}))


async def test_subset_tests_pass_cannot_replace_education_baseline(setup_agent, record_property):
    from app.verification.models import TestCase as Case
    agent, store, session, _, view = prepare(setup_agent)
    sid, lid = session['id'], view['lesson_id']
    view = await agent.education.verify(sid, lid, 1)
    did = view['bindings']['exercise-1']
    draft = store.get('drafts', did)
    with store.tx():
        spec = agent.verification.freeze(sid, draft['path'], [Case(id='n=0', input='0\n', expected='')])
    report = await agent.verification.prepare(sid, did, spec['id'])
    with store.tx():
        agent.verification.commit(report)
    assert report['status'] == 'PASS' and agent.verification.current_pass(store.get('drafts', did))
    view = agent.education.view(sid, lid)
    assert not view['items']['exercise-1']['current_pass']
    assert not view['candidate_ready'] and not view['delivery_ready']
    with pytest.raises(AppError, match='删减'):
        await agent.education.verify(sid, lid, 1)
    record_property('subset_tests_block', dumps({'lesson': view, 'subset_report': report}))
