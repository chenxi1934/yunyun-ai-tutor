"""阶段04专项验收：同题两班真实生成，再用同班情切换大学。不会代教师审核。"""
import asyncio
import json
import os
import re
from pathlib import Path

import httpx
from app.agent import Agent
from app.config import PROJECT_ROOT, Settings
from app.domain import dumps, now, sha, uid
from app.education.catalog import contract
from app.education.models import LessonPlan
from app.education.rules import suggested_plan, validate_grounding
from app.providers import BailianProvider
from app.storage import Store
from app.verification.runner import RemoteRunner
from verify_stage03 import main


class TLSForwardProvider(BailianProvider):
    """仅测试路由：SSH转发TLS字节，证书/SNI仍由本机验证官方API，Key不交给SSH宿主。"""
    def __init__(self, settings, socket):
        super().__init__(settings)
        self.socket = socket

    async def complete(self, messages, tools, max_tokens):
        provider = BailianProvider(self.settings, transport=httpx.AsyncHTTPTransport(uds=self.socket))
        return await provider.complete(messages, tools, max_tokens)


def check_lesson(agent, session, data):
    """核对服务端结构、真实逐case结果与独立固定契约，不信任模型自称PASS。"""
    view = data['lesson']
    plan = LessonPlan.model_validate(view['plan'])
    profile = agent.education.profile(session['id'])
    validate_grounding(plan, profile)
    assert sum(s.minutes for s in plan.segments) == 45
    assert 2 <= len(plan.examples) <= 3
    assert {e.level for e in plan.exercises} == {'基础', '进阶', '挑战'}
    assert all(sum(s.points for s in e.scoring) == 100 for e in plan.exercises)
    assert data['run']['status'] == 'COMPLETED', data['run']
    assert view['candidate_ready'] and not view['delivery_ready'], view['curriculum_risks']
    assert view['teacher_review_status'] == 'PENDING'
    baseline = suggested_plan(profile)
    baseline_segments = {s.id: s.activity for s in baseline.segments}
    baseline_examples = {e.id: e.explanation for e in baseline.examples}
    assert sum(s.activity != baseline_segments.get(s.id) for s in plan.segments) >= 2
    assert sum(e.explanation != baseline_examples.get(e.id) for e in plan.examples) >= 2
    cases_count, execution = 0, []
    for item in [*plan.examples, *plan.exercises]:
        did = view['bindings'][item.id]
        report = [r for r in data['reports'] if r['draft_id'] == did][-1]
        spec = view['items'][item.id]['test_spec']
        assert report['status'] == 'PASS' and view['items'][item.id]['current_pass']
        assert report['code_hash'] == sha(item.code)
        assert report['test_spec_revision'] == spec['id']
        assert report['test_spec_hash'] == spec['content_hash']
        trusted = contract(item.task_id)['cases']
        assert [{k: c[k] for k in ('id', 'input', 'expected')} for c in report['cases']] == trusted
        assert all(c['status'] == 'PASS' and c['actual'] == c['expected'] and c['exit_code'] == 0
                   and c['evidence'].get('cleanup') and c['duration_ms'] > 0 for c in report['cases'])
        cases_count += len(report['cases'])
        execution.append({'item_id': item.id, 'task_id': item.task_id, 'report_id': report['id'],
                          'code_hash': report['code_hash'], 'test_spec_hash': report['test_spec_hash'],
                          'runtime_digest': report['runtime_digest'], 'policy_hash': report['runner_policy_hash'],
                          'cases': report['cases']})
    for m in plan.misconceptions:
        assert m.trigger and m.cause and m.teaching_intervention and m.exercise_ids
        assert m.cause_status == 'hypothesis'
        assert (m.basis == 'observed') == bool(m.evidence_ids)
    return {'status': 'PASS', 'case_count': cases_count, 'program_count': len(execution),
            'execution': execution, 'teacher_review_status': 'PENDING'}


def comparison(scenarios):
    a, b, university = [scenarios[k]['lesson'] for k in ('junior_A', 'junior_B', 'university_A')]
    pa, pb, pu = [v['plan'] for v in (a, b, university)]
    assert {f['type']: f['count'] for f in a['profile']['facts']} == {'not_submitted': 5, 'infinite_loop': 3}
    assert {f['type']: f['count'] for f in b['profile']['facts']} == {
        'not_submitted': 0, 'infinite_loop': 0, 'boundary_error': 8}
    assert a['profile']['prior_knowledge'] == b['profile']['prior_knowledge'] == ['条件语句']
    assert a['profile']['class_size'] == b['profile']['class_size'] == 40
    assert any('交集未知' in unknown for unknown in a['profile']['unknowns'])
    assert not re.search(r'(?:8|八)\s*(?:个|名)?\s*(?:人|学生)', dumps(pa)), 'A班不能把5+3当作8个不同学生'
    assert [s['minutes'] for s in pa['segments']] != [s['minutes'] for s in pb['segments']]
    assert ([i['task_id'] for i in pa['examples']] != [i['task_id'] for i in pb['examples']]
            or [e['scoring'] for e in pa['exercises']] != [e['scoring'] for e in pb['exercises']])
    assert pa['goals'] != pu['goals']
    assert [e['task_id'] for e in pa['exercises']] != [e['task_id'] for e in pu['exercises']]
    assert all('复杂度' in dumps(e['scoring']) and '终止' in dumps(e['scoring']) for e in pu['exercises'])
    return {'topic': '循环结构', 'class_profiles': {k: v['lesson']['profile'] for k, v in scenarios.items()},
        'overlap': 'unknown', 'unique_affected_students': None,
        'segments': {k: v['lesson']['plan']['segments'] for k, v in scenarios.items()},
        'examples': {k: [{'id': e['id'], 'task_id': e['task_id'], 'explanation': e['explanation']}
                         for e in v['lesson']['plan']['examples']] for k, v in scenarios.items()},
        'exercises': {k: [{key: e[key] for key in ('id', 'level', 'task_id', 'prompt', 'scaffolding', 'scoring')}
                          for e in v['lesson']['plan']['exercises']] for k, v in scenarios.items()},
        'goals': {k: v['lesson']['plan']['goals'] for k, v in scenarios.items()},
        'misconceptions': {k: v['lesson']['plan']['misconceptions'] for k, v in scenarios.items()}}


def live_acceptance(socket, token, output):
    async def run():
        settings = Settings(runner_socket=socket, runner_token=token, yunyun_mode='web')
        if settings.llm_provider != 'bailian':
            raise RuntimeError('专项验收必须使用真实百炼模型')
        a = json.loads((PROJECT_ROOT / 'backend/seeds/core/class_A.json').read_text())
        b = {'synthetic': True, 'class_size': 40, 'prior_knowledge': ['条件语句'], 'facts': [
            {'type': 'not_submitted', 'count': 0}, {'type': 'infinite_loop', 'count': 0},
            {'type': 'boundary_error', 'count': 8}]}
        scenarios = [('junior_A', '初中', '初二', a), ('junior_B', '初中', '初二', b),
                     ('university_A', '大学', '大一', a)]
        store = Store(settings.yunyun_data_dir / 'state.sqlite3')
        forward = os.environ.get('YUNYUN_ACCEPT_MODEL_SOCKET')
        bundle = {'timestamp': now(), 'status': 'FAIL', 'mock': False, 'synthetic_class_data': True,
                  'model_route': 'official HTTPS via SSH byte forwarding' if forward else 'direct official HTTPS',
                  'script_hash': sha(Path(__file__).read_text()), 'scenarios': {}}
        try:
            for key, stage, grade, source in scenarios:
                print(dumps({'scenario': key, 'status': 'GENERATING'}), flush=True)
                provider = TLSForwardProvider(settings, forward) if forward else None
                agent = Agent(settings, store, provider)
                agent.verification.runner = RemoteRunner(socket, token)
                session = agent.create_session('stage04-acceptance', {'stage': stage, 'grade': grade, 'topic': '循环结构'})
                with store.tx():
                    agent.education.import_profile(session, dumps(source), 'json')
                prompt = ('请根据已导入班情，为本会话学段生成45分钟《循环结构》完整教案。先读取get_education_context，'
                    '再用propose_lesson提交plan。顶层必须包含stage/topic/duration_minutes/prerequisites/goals/'
                    'segments/examples/exercises/misconceptions，stage必须取本会话显式学段。保留字段与稳定ID。'
                    '至少重新撰写两个环节activity（含教师提问与可观察回答）和两个示例explanation（含追踪问题与预期观察），'
                    '不要原样复制规则文案。任务、代码与固定用例可保留；评分点合计100分。教学安排由实际班情驱动，'
                    '区分观察、预测与病因假设；未知交集不得相加为不同学生人数。大学须有不变量、终止性、复杂度。'
                    '文字必须与代码一致：sum(n=5)循环体执行5次，第6次条件判断6<=5为假；'
                    'while每轮结束更新i后，不变量仍是total等于1到i-1的和。未交为0时不安排补交。'
                    '大学练习explanation须给出具体参考论证：不变量的初始化、保持、退出、终止性及复杂度，'
                    '可以保留规则提供的已复核参考说明，不能只写“先确定不变量再分析”。'
                    '随后调用verify_lesson真实验证全部示例和参考答案，失败仅修代码重测，不改冻结用例。'
                    '文字简洁，避免截断；最后说明真实验证结果及仍待教师教育审核，不请求正式发布。')
                active = agent.new_run(session['id'], prompt, 0, 'accept04-' + uid())
                await agent.run(active['id'])
                data = {'timestamp': now(), 'scenario': key, 'mock': False, 'class_data': source,
                    'model_route': bundle['model_route'],
                    'session_id': session['id'], 'run': store.get('runs', active['id']),
                    'profiles': store.find('class_profiles', session['id']),
                    'lessons': store.find('lessons', session['id']),
                    'reports': store.find('reports', session['id']), 'calls': store.find('calls', session['id']),
                    'attempts': store.find('education_attempts', session['id']),
                    'events': store.events(session['id']), 'messages': store.messages(session['id']),
                    'usage': store.find('usage', session['id'])}
                if data['lessons']:
                    data['lesson'] = agent.education.view(session['id'], data['lessons'][-1]['lesson_id'])
                path = output.with_name(output.stem + '-' + key + '.json')
                path.write_text(dumps(data), encoding='utf-8')
                bundle['scenarios'][key] = data
                output.write_text(dumps(bundle), encoding='utf-8')
                try:
                    data['checks'] = check_lesson(agent, session, data)
                    data['status'] = 'PASS'
                except (AssertionError, KeyError, ValueError) as error:
                    data['status'] = 'FAIL'
                    data['check_error'] = str(error)
                path.write_text(dumps(data), encoding='utf-8')
                output.write_text(dumps(bundle), encoding='utf-8')
                print(dumps({'scenario': key, 'status': data['status'],
                    'programs': data.get('checks', {}).get('program_count'),
                    'cases': data.get('checks', {}).get('case_count')}), flush=True)
            assert all(d['status'] == 'PASS' for d in bundle['scenarios'].values()), {
                k: d.get('check_error') for k, d in bundle['scenarios'].items() if d['status'] != 'PASS'}
            bundle['comparison'] = comparison(bundle['scenarios'])
            bundle['status'] = 'PASS'
            bundle['cny_estimate'] = sum(u['cny'] for d in bundle['scenarios'].values() for u in d['usage'])
            output.write_text(dumps(bundle), encoding='utf-8')
            output.with_name(output.stem + '-comparison.json').write_text(
                json.dumps(bundle['comparison'], ensure_ascii=False, indent=2), encoding='utf-8')
            return {'status': 'PASS', 'scenario_count': 3, 'cny_estimate': bundle['cny_estimate'],
                    'program_count': sum(d['checks']['program_count'] for d in bundle['scenarios'].values()),
                    'case_count': sum(d['checks']['case_count'] for d in bundle['scenarios'].values())}
        finally:
            store.close()
    return asyncio.run(run())


if __name__ == '__main__':
    main(['backend/tests/integration/test_education.py'], live_acceptance, 'stage04-acceptance')
