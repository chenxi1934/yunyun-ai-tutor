import json

import pytest
from app.domain import AppError, dumps, uid
from app.education.models import LessonPlan, ReviewItem, ReviseItem
from app.education.profiles import parse_profile
from app.education.rules import curriculum_risks, strategies, suggested_plan, validate_grounding
from conftest import ScriptedProvider, reply
from pydantic import ValidationError

A = '刚学完条件语句，5人未交、3人把while写成了死循环。'
B = 'type,count,class_size\nnot_submitted,0,40\ninfinite_loop,0,40\nboundary_error,8,40\n'


def prepare(setup_agent, text=A, format='text'):
    agent, store, session, root = setup_agent(ScriptedProvider())
    with store.tx():
        profile = agent.education.import_profile(session, text, format)
        plan = suggested_plan(agent.education.profile(session['id']))
        view = agent.education.propose(session, plan, profile['id'], profile['revision'], 0)
    return agent, store, session, root, view


def test_profile_evidence_unknown_overlap_and_no_denominator():
    profile = parse_profile(A, 'text', '初中', '初二')
    assert [(f.type, f.count, f.denominator) for f in profile.facts] == [
        ('not_submitted', 5, None), ('infinite_loop', 3, None)]
    assert profile.prior_knowledge == ['条件语句']
    assert any('交集未知' in x for x in profile.unknowns)
    assert any('不计算比例' in x for x in profile.unknowns)
    for fact in profile.facts:
        start, end = map(int, fact.source_ref.split(':')[1].split('-'))
        assert str(fact.count) in A[start:end]
    assert '8人' not in dumps(profile.model_dump())


@pytest.mark.parametrize('format,text', [
    ('text', '未交5人，死循环3人'),
    ('json', '{"facts":[{"type":"not_submitted","count":5},{"type":"infinite_loop","count":3}]}'),
    ('csv', 'type,count\nnot_submitted,5\ninfinite_loop,3\n'),
])
def test_three_import_formats(format, text):
    p = parse_profile(text, format, '初中', '初二')
    assert {f.type: f.count for f in p.facts} == {'not_submitted': 5, 'infinite_loop': 3}


@pytest.mark.parametrize('format,text', [
    ('text', '没有任何班情'), ('text', '-3人未交'), ('text', '3人未交，5人未交'),
    ('text', '1.5人未交'), ('text', '约5人未交'),
    ('json', '{"facts":[{"type":"not_submitted","count":1,"count":5}]}'),
    ('csv', 'type,count,count\nnot_submitted,1,5'),
    ('json', '{'), ('json', '[]'), ('json', '{"facts":[]}'),
    ('json', '{"facts":[{"type":"not_submitted","count":true}]}'),
    ('json', '{"facts":[{"type":"not_submitted","count":-1}]}'),
    ('json', '{"facts":[{"type":"not_submitted","count":1.5}]}'),
    ('json', '{"class_size":4,"facts":[{"type":"not_submitted","count":5}]}'),
    ('json', '{"facts":[{"type":"unknown","count":1}]}'),
    ('json', '{"class_size":0,"facts":[{"type":"not_submitted","count":0}]}'),
    ('json', '{"class_size":40,"facts":[{"type":"not_submitted","count":1,"denominator":30}]}'),
    ('csv', 'name,result\na,1'), ('csv', 'type,count\nnot_submitted,1,extra'),
    ('csv', 'type,count,class_size\nnot_submitted,1,40\ninfinite_loop,2,30'),
    ('text', '5人未交\n' * 1001), ('text', 'a' * 1048577),
])
def test_invalid_data_not_guessed(format, text):
    with pytest.raises(AppError) as error:
        parse_profile(text, format, '初中', '初二')
    assert error.value.code == 'INVALID_CLASS_DATA'


def test_pii_and_unknown_columns_are_not_persisted():
    text = 'type,count,name,student_id\nnot_submitted,5,测试姓名,secret-id\n'
    profile = parse_profile(text, 'csv', '初中', '初二')
    value = dumps(profile.model_dump())
    assert '测试姓名' not in value and 'secret-id' not in value
    assert profile.facts[0].source_ref == 'csv:row=2'


def test_two_profiles_and_two_stages_have_material_differences():
    a, b = parse_profile(A, 'text', '初中', '初二'), parse_profile(B, 'csv', '初中', '初二')
    pa, pb = suggested_plan(a), suggested_plan(b)
    assert [s.minutes for s in pa.segments] == [5, 8, 10, 10, 10, 2]
    assert [s.minutes for s in pb.segments] == [2, 8, 8, 15, 10, 2]
    assert [e.task_id for e in pa.examples] != [e.task_id for e in pb.examples]
    assert pa.exercises[0].scaffolding != pb.exercises[0].scaffolding
    assert pa.exercises[1].scoring != pb.exercises[1].scoring
    assert {s.rule_id for s in strategies(a)} == {'R00', 'R01', 'R02'}
    assert {s.rule_id for s in strategies(b)} == {'R00', 'R03'}
    u = parse_profile(A, 'text', '大学', '大一')
    pu = suggested_plan(u)
    assert '不变量' in pu.goals[1].criterion and '复杂度' in pu.goals[1].criterion
    assert [e.task_id for e in pu.exercises] == ['sum', 'divisors', 'primes']
    assert any('for d' in e.code and 'break' in e.code for e in pu.exercises)
    assert '复杂度' in pu.exercises[0].scoring[-1].criterion
    for plan, profile in ((pa, a), (pb, b), (pu, u)):
        validate_grounding(plan, profile)
        assert sum(s.minutes for s in plan.segments) == 45
        assert curriculum_risks(plan) == []
        assert len(plan.examples) == 2 and len(plan.exercises) == 3
        assert all(sum(s.points for s in e.scoring) == 100 for e in plan.exercises)


@pytest.mark.parametrize('change', ['time', 'levels', 'scores', 'ids', 'reference'])
def test_lesson_structure_rejects_invalid(change):
    value = suggested_plan(parse_profile(A, 'text', '初中', '初二')).model_dump()
    if change == 'time':
        value['segments'][0]['minutes'] += 1
    elif change == 'levels':
        value['exercises'][1]['level'] = '基础'
    elif change == 'scores':
        value['exercises'][0]['scoring'][0]['points'] += 1
    elif change == 'ids':
        value['exercises'][0]['id'] = value['examples'][0]['id']
    else:
        value['misconceptions'][0]['exercise_ids'] = ['missing']
    with pytest.raises(ValidationError):
        LessonPlan.model_validate(value)


def test_wrong_evidence_and_unmarked_prediction_rejected():
    p = parse_profile(A, 'text', '初中', '初二')
    plan = suggested_plan(p)
    plan.misconceptions[2].evidence_ids = ['fact-infinite_loop']
    with pytest.raises(AppError, match='同类'):
        validate_grounding(plan, p)
    plan = suggested_plan(p)
    plan.misconceptions[2].basis = 'observed'
    with pytest.raises(AppError, match='预测'):
        validate_grounding(plan, p)


def test_curriculum_risk_is_not_code_pass():
    p = parse_profile(A, 'text', '初中', '初二')
    plan = suggested_plan(p)
    plan.exercises[2].code = 'for i in range(3):\n    for j in range(3):\n        print(j)\n'
    assert curriculum_risks(plan)[0]['item_id'] == 'exercise-3'


def test_zero_and_unknown_submission_do_not_invent_remedial_group():
    b = suggested_plan(parse_profile(B, 'csv', '初中', '初二'))
    unknown = suggested_plan(parse_profile('3人死循环', 'text', '初中', '初二'))
    assert '给未交者补交机会' not in b.segments[0].activity
    assert '不安排补交' in b.segments[0].activity
    assert '未知' in unknown.segments[0].activity and '未交为0' not in unknown.segments[0].activity


def test_university_scored_reasoning_needs_reference_solution():
    plan = suggested_plan(parse_profile(A, 'text', '大学', '大一'))
    assert curriculum_risks(plan) == []
    plan.exercises[1].explanation = '先确定不变量与终止条件，再分析复杂度。'
    risks = curriculum_risks(plan)
    assert any(r['item_id'] == 'exercise-2' and '参考解' in r['reason'] for r in risks)


def test_revise_reject_restore_and_history(setup_agent):
    agent, store, session, root, view = prepare(setup_agent)
    sid, lid = session['id'], view['lesson_id']
    before = view['plan']['segments'][0]
    with store.tx():
        agent.education.review(session, lid, ReviewItem(expected_revision=1, item_id=before['id'], decision='reject', note='诊断表述需要修改'))
    assert agent.education.view(sid, lid)['items'][before['id']]['review_status'] == 'REJECTED'
    replacement = {**before, 'activity': before['activity'] + '教师逐人核对提交障碍。'}
    with store.tx():
        revised = agent.education.revise(session, lid, ReviseItem(expected_revision=1, item_id=before['id'], replacement=replacement, reason='按教师要求调整'))
    assert revised['revision'] == 2
    assert revised['items'][before['id']]['review_status'] == 'PENDING'
    assert revised['bindings'] == view['bindings']  # 只改环节不重跑无关代码。
    with store.tx():
        restored = agent.education.revise(session, lid, ReviseItem(expected_revision=2, item_id=before['id'], replacement=before, reason='恢复旧环节为新版本'))
    assert restored['revision'] == 3 and restored['plan']['segments'][0] == before
    assert len(store.find('lessons', sid)) == 3 and len(store.find('education_reviews', sid)) == 1
    assert sorted(p.name for p in root.iterdir()) == ['fixture.md']
    with pytest.raises(AppError):
        agent.education.export(sid, lid)


def test_task_switch_or_item_deletion_has_no_side_effects(setup_agent):
    agent, store, session, _, view = prepare(setup_agent)
    before = dumps({t: store.find(t, session['id']) for t in ('lessons', 'drafts', 'test_specs', 'repairs')})
    value = json.loads(dumps(view['plan']))
    value['examples'][0]['task_id'] = 'sum'
    with pytest.raises(AppError, match='换题'):
        agent.education.propose(session, value, *view['profile_ref'], 1, 'model')
    value = json.loads(dumps(view['plan']))
    value['examples'][0]['id'] = 'replacement-id'
    with pytest.raises(AppError, match='稳定ID'):
        agent.education.propose(session, value, *view['profile_ref'], 1, 'model')
    assert before == dumps({t: store.find(t, session['id']) for t in ('lessons', 'drafts', 'test_specs', 'repairs')})


async def test_runner_unavailable_retains_attempt_and_blocks_delivery(setup_agent):
    agent, store, session, _, view = prepare(setup_agent)
    with pytest.raises(AppError, match='Runner'):
        await agent.education.verify(session['id'], view['lesson_id'], 1)
    assert store.find('education_attempts', session['id'])[0]['error']['code'] == 'RUNNER_UNAVAILABLE'
    assert all(d['verification_status'] == 'NOT_TESTED' for d in store.find('drafts', session['id']))
    with pytest.raises(AppError):
        agent.education.review(session, view['lesson_id'], ReviewItem(expected_revision=1, item_id='example-1', decision='accept', note='不能伪造审核'))


def test_profile_revision_invalidate_candidate_and_reviews(setup_agent):
    agent, store, session, _, view = prepare(setup_agent)
    with store.tx():
        agent.education.import_profile(session, B, 'csv')
    assert agent.education.view(session['id'], view['lesson_id'])['profile_stale']
    with pytest.raises(AppError, match='最新'):
        agent.education.propose(session, view['plan'], *view['profile_ref'], 1)
    with pytest.raises(AppError, match='旧依据'):
        agent.education.review(session, view['lesson_id'], ReviewItem(expected_revision=1,
            item_id='goal-1', decision='accept', note='旧班情应失效'))


def test_generic_patch_cannot_desynchronize_education_binding(setup_agent):
    agent, store, session, root, view = prepare(setup_agent)
    draft = store.get('drafts', view['bindings']['example-1'])
    result = agent.registry.execute({'id': uid(), 'run_id': 'test', 'name': 'propose_patch',
        'arguments': dumps({'path': draft['path'], 'content': 'print(0)', 'base_hash': None})},
        session, agent.workspace(session))
    assert not result['ok'] and result['error']['code'] == 'EDUCATION_ITEM_REQUIRED'
    assert len(store.find('drafts', session['id'])) == 5


async def test_educational_contract_cannot_be_replaced_with_subset(setup_agent):
    from app.verification.models import TestCase as Case
    agent, store, session, _, view = prepare(setup_agent)
    draft = store.get('drafts', view['bindings']['exercise-1'])
    with store.tx():
        agent.verification.freeze(session['id'], draft['path'], [Case(id='n=0', input='0\n', expected='')])
    with pytest.raises(AppError, match='删减'):
        await agent.education.verify(session['id'], view['lesson_id'], 1)
    assert not agent.education.view(session['id'], view['lesson_id'])['candidate_ready']


def test_education_auto_repair_limit_cannot_reset_by_new_plan(setup_agent):
    # 合成策略状态，不作为代码运行证据；真实Runner另测错误与修复。
    agent, store, session, _, view = prepare(setup_agent)
    sid = session['id']
    did = view['bindings']['exercise-1']
    draft = store.get('drafts', did)
    with store.tx():
        store.put('repairs', {'id': agent.verification.repair_key(sid, draft['path']),
            'session_id': sid, 'path': draft['path'], 'count': 2, 'failed': True,
            'failed_hashes': [draft['content_hash']]})
    value = json.loads(dumps(view['plan']))
    value['exercises'][0]['code'] += '# another attempt\n'
    before = dumps(store.find('drafts', sid))
    with pytest.raises(AppError) as error:
        agent.education.propose(session, value, *view['profile_ref'], 1, 'model')
    assert error.value.code == 'REPAIR_LIMIT'
    with pytest.raises(AppError) as error:
        agent.education.propose(session, value, *view['profile_ref'], 0, 'model')
    assert error.value.code == 'REVISION_CONFLICT'
    assert before == dumps(store.find('drafts', sid))


def test_full_education_version_history_survives_store_restart(setup_agent):
    from app.storage import Store
    agent, store, session, _, view = prepare(setup_agent)
    segment = view['plan']['segments'][0]
    with store.tx():
        updated = agent.education.revise(session, view['lesson_id'], ReviseItem(expected_revision=1,
            item_id=segment['id'], replacement={**segment, 'activity': '用出口小题诊断提交原因。'}, reason='教师修订'))
    path = agent.settings.yunyun_data_dir / 'state.sqlite3'
    reopened = Store(path)
    try:
        assert reopened.find('lessons', session['id']) == store.find('lessons', session['id'])
        assert reopened.find('class_profiles', session['id']) == store.find('class_profiles', session['id'])
        assert reopened.get('lessons', updated['id'])['parent_id'] == view['id']
    finally:
        reopened.close()


async def test_agent_format_failure_repair_is_recorded(setup_agent):
    def valid(messages):
        data = next(json.loads(m['content'])['data'] for m in messages if m['role'] == 'tool' and json.loads(m['content'])['ok'])
        return reply(('propose_lesson', {'profile_id': data['profile']['id'], 'profile_revision': 1,
                                       'base_revision': 0, 'plan': data['suggested_plan']}))
    provider = ScriptedProvider(reply(('get_education_context', {})),
        reply(('propose_lesson', {'profile_id': 'invalid', 'profile_revision': 1, 'base_revision': 0, 'plan': {}})),
        valid, reply(content='草稿已生成；代码未测试，仍须审核。'))
    agent, store, session, _ = setup_agent(provider)
    with store.tx():
        agent.education.import_profile(session, A, 'text')
    run = agent.new_run(session['id'], '按班情生成循环课', 0, uid())
    await agent.run(run['id'])
    assert store.get('runs', run['id'])['status'] == 'COMPLETED'
    attempts = store.find('education_attempts', session['id'])
    assert attempts[0]['error']['code'] == 'INVALID_LESSON'
    assert len(store.find('lessons', session['id'])) == 1
    assert store.events(session['id'])[-1]['payload']['delivery_status'] == 'EDUCATION_VALIDATION_FAILED'


def test_education_current_turn_compaction_preserves_raw_history_and_errors(setup_agent):
    agent, store, session, _, view = prepare(setup_agent)
    sid = session['id']
    profile = agent.education.profile(sid)
    user = {'role': 'user', 'content': '请按班情备课，保留失败。'}
    context_call, bad_call, good_call = uid(), uid(), uid()
    plan = view['plan']
    bad_plan = {**plan, 'stage': '初二'}
    messages = [user]
    for call_id, name, args, result in [
        (context_call, 'get_education_context', {}, {'ok': True, 'data': agent.education.context(sid)}),
        (bad_call, 'propose_lesson', {'plan': bad_plan}, {'ok': False, 'error': {'code': 'INVALID_LESSON'}}),
        (good_call, 'propose_lesson', {'plan': plan}, {'ok': True, 'data': {'lesson_id': view['lesson_id']}}),
    ]:
        messages += [{'role': 'assistant', 'content': None, 'tool_calls': [{'id': call_id,
            'type': 'function', 'function': {'name': name, 'arguments': dumps(args)}}]},
            {'role': 'tool', 'tool_call_id': call_id, 'content': dumps(result)}]
        store.put('calls', {'id': call_id, 'session_id': sid, 'run_id': 'fixture',
                           'name': name, 'status': 'DONE', 'result': result})
    for message in messages:
        store.message(sid, 'fixture', message)
    raw = dumps(store.messages(sid))
    assert len(raw.encode()) > 24000
    compacted = agent.context(session)
    assert compacted[-3:] == [user, *messages[-2:]]  # 最新成功提案的协议不能丢失。
    assert any(view['lesson_id'] in m.get('content', '') for m in compacted if m['role'] == 'system')
    assert agent.education.view(sid, view['lesson_id'])['plan'] == plan  # 全文仍可取回。
    assert len(dumps(compacted).encode()) < len(raw.encode())
    assert any('INVALID_LESSON' in m.get('content', '') for m in compacted if m['role'] == 'system')
    assert any(profile.source_hash in m.get('content', '') for m in compacted if m['role'] == 'system')
    assert dumps(store.messages(sid)) == raw


@pytest.mark.parametrize('legacy', [True, False], ids=['legacy-window', 'rich-plan'])
def test_single_saved_lesson_compacts_below_old_threshold(setup_agent, legacy):
    agent, store, session, _, view = prepare(setup_agent)
    sid, call_id, context_id = session['id'], uid(), uid()
    # 单份完整提案加模板结果：真实失败历史为22538字节，低于旧24000阈值。
    store.message(sid, 'fixture', {'role': 'user', 'content': '生成后按固定用例真实验证。'})
    store.message(sid, 'fixture', {'role': 'assistant', 'content': None, 'tool_calls': [{
        'id': context_id, 'type': 'function', 'function': {'name': 'get_education_context', 'arguments': '{}'}}]})
    context_data = agent.education.context(sid)
    wire_plan = json.loads(dumps(view['plan']))
    if legacy:
        wire_plan.pop('overview', None)
        for segment in wire_plan['segments']:
            for field in ('teacher_actions', 'student_actions', 'assessment'):
                segment.pop(field, None)
        context_data['suggested_plan'] = wire_plan
    context_result = {'ok': True, 'data': context_data}
    store.message(sid, 'fixture', {'role': 'tool', 'tool_call_id': context_id, 'content': dumps(context_result)})
    store.put('calls', {'id': context_id, 'session_id': sid, 'run_id': 'fixture',
                       'name': 'get_education_context', 'status': 'DONE', 'result': context_result})
    store.message(sid, 'fixture', {'role': 'assistant', 'content': None, 'tool_calls': [{
        'id': call_id, 'type': 'function', 'function': {'name': 'propose_lesson',
        'arguments': dumps({'plan': wire_plan, 'profile_id': view['profile_ref'][0],
                           'profile_revision': 1, 'base_revision': 0})}}]})
    result = {'ok': True, 'data': {'lesson_id': view['lesson_id']}}
    store.message(sid, 'fixture', {'role': 'tool', 'tool_call_id': call_id, 'content': dumps(result)})
    store.put('calls', {'id': call_id, 'session_id': sid, 'run_id': 'fixture',
                       'name': 'propose_lesson', 'status': 'DONE', 'result': result})
    raw = dumps(store.messages(sid))
    if legacy:
        assert 16000 < len(raw.encode()) < 24000
    else:
        assert len(raw.encode()) > 24000
    context = agent.context(session)
    assert len(dumps(context).encode()) < len(raw.encode())
    assert context[-3:] == [store.messages(sid)[0], *store.messages(sid)[-2:]]
    assert dumps(store.messages(sid)) == raw


def test_education_compaction_preserves_current_file_evidence_as_tool_data(setup_agent):
    agent, store, session, root, view = prepare(setup_agent)
    sid = session['id']
    marker = uid()
    (root / 'fixture.md').write_text('现场核验标记：' + marker)
    user = {'role': 'user', 'content': '读取fixture.md后备课，并复述核验标记。'}
    store.message(sid, 'fixture', user)
    read_call = {'id': uid(), 'run_id': 'fixture', 'name': 'read_file',
                 'arguments': dumps({'path': 'fixture.md'})}
    result = agent.registry.execute(read_call, session, agent.workspace(session))
    assert result['ok'] and marker in result['data']['content']
    read_messages = [
        {'role': 'assistant', 'content': None, 'tool_calls': [{
            'id': read_call['id'], 'type': 'function', 'function': {
                'name': 'read_file', 'arguments': read_call['arguments']}}]},
        {'role': 'tool', 'tool_call_id': read_call['id'], 'content': dumps(result)},
    ]
    for message in read_messages:
        store.message(sid, 'fixture', message)
    store.put('calls', {**read_call, 'session_id': sid, 'status': 'DONE', 'result': result})
    for name, args, data in [
        ('get_education_context', {}, agent.education.context(sid)),
        ('propose_lesson', {'plan': view['plan']}, {'lesson_id': view['lesson_id']}),
    ]:
        call_id = uid()
        store.message(sid, 'fixture', {'role': 'assistant', 'content': None, 'tool_calls': [{
            'id': call_id, 'type': 'function', 'function': {'name': name, 'arguments': dumps(args)}}]})
        result = {'ok': True, 'data': data}
        store.message(sid, 'fixture', {'role': 'tool', 'tool_call_id': call_id, 'content': dumps(result)})
        store.put('calls', {'id': call_id, 'session_id': sid, 'name': name,
                           'status': 'DONE', 'result': result})
    raw = dumps(store.messages(sid))
    assert len(raw.encode()) > 16000
    compacted = agent.context(session)
    assert all(message in compacted for message in read_messages)
    assert not any(marker in (m.get('content') or '') for m in compacted if m['role'] == 'system')
    assert dumps(store.messages(sid)) == raw
