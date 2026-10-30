import json

import pytest
from app.domain import AppError, dumps, sha
from app.education.catalog import TASKS
from app.education.models import LessonPlan, ReviewItem, ReviseItem
from app.education.profiles import parse_profile, request_profile_text
from app.education.render import render_files
from app.education.rules import suggested_plan
from conftest import ScriptedProvider

A = '全班40人，5人未交、3人while死循环，刚学完条件语句。'


def prepared(setup_agent, text=A):
    agent, store, session, root = setup_agent(ScriptedProvider())
    with store.tx():
        profile = agent.education.import_profile(session, text, 'text')
        view = agent.education.propose(session, suggested_plan(agent.education.profile(session['id'])),
                                       profile['id'], profile['revision'], 0)
    return agent, store, session, root, view


def test_plain_request_initializes_unknown_profile_without_demo_facts(setup_agent):
    agent, _, session, _ = setup_agent(ScriptedProvider())
    config = agent._config()
    run = agent.new_run(session['id'], '请备一节循环课，讨论n=-1的输入限制。', 0, 'unknown-profile-1')
    profile = agent.education.profile(session['id'])
    assert profile.facts == [] and profile.class_size is None
    assert any('不能当作0人' in value for value in profile.unknowns)
    assert run['config'] == config


@pytest.mark.parametrize('format,text', [
    ('text', '全班40人，刚学完条件语句。'),
    ('json', '{"class_size":40,"facts":[]}'),
    ('json', '{"prior_knowledge":["条件语句"],"facts":[]}'),
])
def test_known_context_without_problem_counts_keeps_all_observations_unknown(format, text):
    profile = parse_profile(text, format, '初中', '初二')
    assert profile.facts == []
    assert len([unknown for unknown in profile.unknowns if '不能当作0人' in unknown]) == 3
    assert profile.class_size == 40 or profile.prior_knowledge == ['条件语句']


@pytest.mark.parametrize('text', [A, '班上有40名学生，5名学生未交，3位学生while死循环，已学过条件语句。'])
def test_request_extracts_class_observations_before_agent_runs(setup_agent, text):
    agent, store, session, _ = setup_agent(ScriptedProvider())
    agent.new_run(session['id'], text + '请生成45分钟教案。', 0, 'request-profile-1')
    profile = agent.education.profile(session['id'])
    assert profile.class_size == 40
    assert {f.type: f.count for f in profile.facts} == {'not_submitted': 5, 'infinite_loop': 3}
    assert profile.prior_knowledge == ['条件语句']
    assert profile.sources[0].origin == 'request'
    assert len(store.find('runs', session['id'])) == 1
    for fact in profile.facts:
        start, end = map(int, fact.source_ref.removeprefix('text:').split('-'))
        assert str(fact.count) in text[start:end]


def test_request_supplements_existing_data_without_summing_students(setup_agent):
    agent, store, session, _, _ = prepared(setup_agent)
    agent.new_run(session['id'], '另有8人边界错误，请加强边界对比。', 0, 'request-profile-2')
    profile = agent.education.profile(session['id'])
    assert profile.revision == 2
    assert {f.type: f.count for f in profile.facts} == {'not_submitted': 5, 'infinite_loop': 3, 'boundary_error': 8}
    assert all(f.denominator == 40 for f in profile.facts)
    assert any('不能直接相加' in item for item in profile.unknowns)
    assert len(store.find('class_profiles', session['id'])) == 2


def test_conflicting_request_is_atomic_and_creates_no_run(setup_agent):
    agent, store, session, _, _ = prepared(setup_agent)
    before = {name: dumps(store.find(name, session['id'])) for name in ('class_profiles', 'runs', 'usage', 'sessions')}
    with pytest.raises(AppError, match='冲突') as error:
        agent.new_run(session['id'], '3人未交，请调整教案。', 0, 'request-profile-conflict')
    assert error.value.code == 'CLASS_PROFILE_CONFLICT'
    assert before == {name: dumps(store.find(name, session['id'])) for name in before}
    assert store.messages(session['id']) == []


def test_repeated_same_observation_does_not_stale_existing_lesson(setup_agent):
    agent, store, session, _, view = prepared(setup_agent)
    agent.new_run(session['id'], '5人未交，请补充学习支架。', 0, 'request-profile-same')
    assert agent.education.profile(session['id']).revision == 1
    assert not agent.education.view(session['id'], view['lesson_id'])['profile_stale']
    assert len(store.find('class_profiles', session['id'])) == 1


@pytest.mark.parametrize('text', ['如果全班40人，5人未交，请讨论可能的原因。', '例如5人未交、3人死循环，只是一个假设。', '题目中全班40人，5人未交。'])
def test_hypothetical_request_is_not_recorded_as_observed_data(text):
    assert request_profile_text(text) is None


def test_negative_task_input_does_not_invalidate_real_class_counts():
    text = '全班40人，5人未交；请讨论n=-1时为什么不满足题目输入要求。'
    extracted = request_profile_text(text)
    profile = parse_profile(extracted, 'text', '初中', '初二')
    assert profile.facts[0].count == 5 and profile.class_size == 40


@pytest.mark.parametrize('text', ['-3人未交', '1.5人未交', '约5人未交', '全班-40人，5人未交', '全班约40人，5人未交', '全班40.5人，5人未交'])
def test_ambiguous_counts_in_request_are_not_silently_made_exact(text):
    extracted = request_profile_text(text)
    with pytest.raises(AppError):
        parse_profile(extracted, 'text', '初中', '初二', allow_empty=True)


def test_negative_prior_knowledge_is_not_claimed_as_mastered():
    profile = parse_profile('5人未交，没有学过函数，刚学完条件语句。', 'text', '初中', '初二')
    assert profile.prior_knowledge == ['条件语句']


def test_instruction_negation_does_not_erase_a_later_observed_clause():
    text = request_profile_text('不要增加超纲题目，全班40人，5人未交。')
    profile = parse_profile(text, 'text', '初中', '初二')
    assert profile.class_size == 40 and profile.facts[0].count == 5


def test_upload_supplement_retains_sources_and_drops_personal_columns(setup_agent):
    agent, _, session, _, _ = prepared(setup_agent)
    raw = 'type,count,student_id,name\nboundary_error,8,synthetic-id,合成姓名\n'.encode()
    value = agent.education.import_profile(session, raw.decode(), 'csv', source=raw, mode='supplement', origin='upload')
    assert len(value['facts']) == 3
    assert next(f for f in value['facts'] if f['type'] == 'boundary_error')['source_hash'] == sha(raw.decode())
    assert value['sources'][-1]['source_hash'] == sha(raw.decode())
    assert 'synthetic-id' not in dumps(value) and '合成姓名' not in dumps(value)


def test_known_denominator_can_complete_an_unknown_one(setup_agent):
    agent, _, session, _ = setup_agent(ScriptedProvider())
    agent.education.import_profile(session, '3人死循环', 'text')
    value = agent.education.import_profile(session,
        '{"facts":[{"type":"infinite_loop","count":3,"denominator":40}]}', 'json', mode='supplement')
    assert value['facts'][0]['denominator'] == 40
    assert value['class_size'] is None


def test_supplement_conflicts_preserve_old_data_and_explicit_replace_keeps_history(setup_agent):
    agent, store, session, _, _ = prepared(setup_agent)
    original = dumps(agent.education.profile(session['id']).model_dump())
    with pytest.raises(AppError):
        agent.education.import_profile(session, '全班35人，2人未交', 'text', mode='supplement')
    assert dumps(agent.education.profile(session['id']).model_dump()) == original
    value = agent.education.import_profile(session, '2人未交', 'text', mode='replace')
    assert len(value['facts']) == 1 and value['facts'][0]['count'] == 2
    assert value['revision'] == 2
    assert len(store.find('class_profiles', session['id'])) == 2


def test_rich_overview_and_process_are_reviewable_and_code_contracts_unchanged(setup_agent):
    _, _, _, _, view = prepared(setup_agent)
    plan = LessonPlan.model_validate(view['plan'])
    assert {item.kind for item in plan.overview} == {'content', 'learners', 'focus'}
    assert all(len(item.content) > 100 for item in plan.overview)
    assert all(segment.teacher_actions and segment.student_actions and segment.assessment for segment in plan.segments)
    assert len(view['items']) == len(plan.items()) == 19
    assert all(view['items'][item.id]['review_status'] == 'PENDING' for item in plan.overview)
    assert sum(item.minutes for item in plan.segments) == 45
    for item in [*plan.examples, *plan.exercises]:
        assert item.code == TASKS[item.task_id][2]


def test_analysis_edit_invalidates_review_but_keeps_bound_code_and_old_rejection(setup_agent):
    agent, store, session, _, view = prepared(setup_agent)
    sid, lid = session['id'], view['lesson_id']
    with store.tx():
        agent.education.review(session, lid, ReviewItem(expected_revision=1, item_id='goal-1', decision='accept', note='合成教师审核'))
        rejected = agent.education.review(session, lid, ReviewItem(expected_revision=1, item_id='analysis-focus', decision='reject', note='需要更具体的边界干预'))
    assert rejected['items']['analysis-focus']['review_status'] == 'REJECTED'
    assert rejected['items']['analysis-focus']['review_note'] == '需要更具体的边界干预'
    item = {**view['plan']['overview'][2], 'content': view['plan']['overview'][2]['content'] + '\n补充：用出口反馈安排下一课。'}
    with store.tx():
        revised = agent.education.revise(session, lid, ReviseItem(expected_revision=1, item_id=item['id'], replacement=item, reason='按教师要求补充'))
    assert revised['bindings'] == view['bindings']
    assert all(state['review_status'] == 'PENDING' for state in revised['items'].values())
    assert len(store.find('education_reviews', sid)) == 2
    assert len(store.find('lessons', sid)) == 2
    with pytest.raises(AppError):
        agent.education.export(sid, lid)


def test_old_lesson_read_is_unchanged_and_new_version_can_add_analysis(setup_agent):
    agent, store, session, _, view = prepared(setup_agent)
    record = agent.education.latest(session['id'], view['lesson_id'])
    old = json.loads(dumps(record))
    for item in old['plan'].pop('overview'):
        old['item_revisions'].pop(item['id'])
    for segment in old['plan']['segments']:
        for key in ('teacher_actions', 'student_actions', 'assessment'):
            segment.pop(key)
    old['content_hash'] = sha(dumps(old['plan']))
    with store.tx():
        store.put('lessons', old)
    assert len(agent.education.view(session['id'], view['lesson_id'])['items']) == 16
    assert store.get('lessons', old['id']) == old
    goal = {**old['plan']['goals'][0], 'criterion': old['plan']['goals'][0]['criterion'] + '补充边界说明。'}
    with store.tx():
        edited = agent.education.revise(session, view['lesson_id'], ReviseItem(expected_revision=1,
            item_id=goal['id'], replacement=goal, reason='修订旧版教学目标'))
    assert edited['revision'] == 2 and edited['plan']['overview'] == []
    assert edited['bindings'] == view['bindings']
    with store.tx():
        updated = agent.education.propose(session, suggested_plan(agent.education.profile(session['id'])), *view['profile_ref'], 2)
    assert updated['revision'] == 3 and len(updated['items']) == 19
    assert updated['bindings'] == view['bindings']
    assert store.get('lessons', old['id']) == old


def test_markdown_export_keeps_structure_and_readable_references(setup_agent):
    _, _, _, _, view = prepared(setup_agent)
    # 只验证渲染格式，不调用导出闸口，不作为教师审核或真实执行证据。
    files = render_files(view, [])['files']
    text = files['lesson.md']
    for section in ('一、教学内容分析', '二、学情分析', '三、教学目标', '四、教学重点、难点与解决策略', '五、教学过程'):
        assert section in text
    assert '教师活动' in text and '达成检查与反馈' in text
    assert 'fact-' not in text and "['exercise-" not in text
    assert '正偶数求和' in text and 'while死循环：3人' in text
    assert len([name for name in files if name.endswith('.py')]) == 5
    assert 'overview' in json.loads(files['lesson.json'])['plan']
