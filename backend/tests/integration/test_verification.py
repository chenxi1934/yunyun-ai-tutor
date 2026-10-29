"""必须指向真实受限容器 Manager；没有配置即失败，不使用执行 Mock 或 skip。"""
import asyncio
import json
import os
from pathlib import Path

import pytest
from app.domain import AppError, dumps, sha, uid
from app.verification.models import ExecutionRequest
from app.verification.models import TestCase as Case
from app.verification.runner import RemoteRunner
from conftest import ScriptedProvider, reply

GOOD = 'n=int(input())\nprint(sum(range(1,n+1)))\n'
BAD = 'n=int(input())\nprint(sum(range(1,n)))\n'


@pytest.fixture
def real_runner():
    return RemoteRunner(Path(os.environ['YUNYUN_TEST_RUNNER_SOCKET']),
                        os.environ['YUNYUN_TEST_RUNNER_TOKEN'])


def draft(agent, session, code, path='sum.py'):
    call = {'id': uid(), 'run_id': 'verification-test', 'name': 'propose_patch',
            'arguments': dumps({'path': path, 'content': code, 'base_hash': None})}
    with agent.store.tx():
        result = agent.registry.execute(call, session, agent.workspace(session))
    assert result['ok'], result
    return result['data']['draft_id']


async def verify(agent, session, did, spec):
    report = await agent.verification.prepare(session['id'], did, spec['id'])
    with agent.store.tx():
        agent.verification.commit(report)
    return report


def fixture(setup_agent, real_runner):
    agent, store, session, root = setup_agent(ScriptedProvider())
    agent.verification.runner = real_runner
    with store.tx():
        spec = agent.verification.freeze(session['id'], 'sum.py', None, 'sum_1_to_n')
    return agent, store, session, root, spec


@pytest.mark.parametrize('code,status', [
    (GOOD, 'PASS'),
    ('for n in range(2)\n print(n)', 'SYNTAX_ERROR'),
    ('print("PASS")', 'OUTPUT_MISMATCH'),
    ('while True: pass', 'TIMEOUT'),
    (BAD, 'OUTPUT_MISMATCH'),
    ('print(1/0)', 'RUNTIME_ERROR'),
    ('assert False, "lesson assertion"', 'ASSERTION_ERROR'),
    ('print("x"*70000)', 'OUTPUT_LIMIT'),
    ('import sys\nsys.stderr.write("x"*70000)', 'OUTPUT_LIMIT'),
    ('a=bytearray(300*1024*1024)', 'RESOURCE_LIMIT'),
])
async def test_real_cases(setup_agent, real_runner, code, status, record_property):
    agent, store, session, _, spec = fixture(setup_agent, real_runner)
    did = draft(agent, session, code)
    report = await verify(agent, session, did, spec)
    record_property('report', dumps(report))
    assert report['status'] == status, report
    assert [c['id'] for c in report['cases']] == ['n=0', 'n=1', 'n=5']
    assert report['code_hash'] == sha(code)
    assert all(c['evidence']['cleanup'] for c in report['cases'])
    if status == 'PASS':
        assert [c['actual'] for c in report['cases']] == ['0\n', '1\n', '15\n']
        assert store.get('drafts', did)['status'] == 'PENDING_REVIEW'
        assert agent.verification.delivery_candidates(session['id'])[0]['id'] == did
    else:
        assert store.get('drafts', did)['status'] == 'VALIDATION_FAILED'
        with pytest.raises(AppError, match='不能进入可交付候选'):
            agent.verification.delivery_candidates(session['id'])
    if code == BAD:
        failed = [c for c in report['cases'] if c['status'] != 'PASS']
        assert [(c['id'], c['expected'], c['actual']) for c in failed] == [
            ('n=1', '1\n', '0\n'), ('n=5', '15\n', '10\n')]
    if status == 'TIMEOUT':
        assert all(c['duration_ms'] < 6000 for c in report['cases'])
    if status in {'SYNTAX_ERROR', 'RUNTIME_ERROR', 'ASSERTION_ERROR'}:
        assert all(c['stderr'] and c['exit_code'] != 0 for c in report['cases'])


async def test_code_spec_runtime_policy_changes_invalidate(setup_agent, real_runner, record_property):
    agent, store, session, _, spec = fixture(setup_agent, real_runner)
    did = draft(agent, session, GOOD)
    await verify(agent, session, did, spec)
    identity = await real_runner.identity()
    assert agent.verification.current_pass(store.get('drafts', did), identity)
    for field in ('runtime_digest', 'runner_policy_hash'):
        assert not agent.verification.current_pass(store.get('drafts', did),
                                                  {**identity, field: 'changed'})
    with store.tx():
        newer = agent.verification.freeze(session['id'], 'sum.py',
                                         [Case(id='n=2', input='2\n', expected='3\n')])
    assert store.get('drafts', did)['verification_status'] == 'STALE'
    with pytest.raises(AppError, match='最新测试规格'):
        await agent.verification.prepare(session['id'], did, spec['id'])
    await verify(agent, session, did, newer)
    new_id = draft(agent, session, GOOD + '# teacher edit\n')
    assert store.get('drafts', did)['verification_status'] == 'STALE'
    assert store.get('drafts', new_id)['verification_status'] == 'NOT_TESTED'
    with pytest.raises(AppError):
        agent.verification.delivery_candidates(session['id'])
    assert len(store.find('reports')) == 2
    record_property('invalidation', dumps({'old_draft': store.get('drafts', did),
        'new_draft': store.get('drafts', new_id), 'reports': store.find('reports')}))


async def test_agent_repairs_with_real_errors_same_spec(setup_agent, real_runner, record_property):
    def test_latest(messages):
        did = json.loads(messages[-1]['content'])['data']['draft_id']
        return reply(('run_python_tests', {'draft_id': did, 'test_spec_revision': spec['id']}))

    def fix(messages):
        report = json.loads(messages[-1]['content'])['data']
        assert report['status'] == 'OUTPUT_MISMATCH'
        assert report['cases'][2]['actual'] == '10\n'
        return reply(('propose_patch', {'path': 'sum.py', 'content': GOOD, 'base_hash': None}))

    provider = ScriptedProvider(reply(('propose_patch', {'path': 'sum.py', 'content': BAD, 'base_hash': None})),
        test_latest, fix, test_latest, reply(content='当前固定用例通过，请教师审核。'))
    agent, store, session, root = setup_agent(provider)
    agent.verification.runner = real_runner
    with store.tx():
        spec = agent.verification.freeze(session['id'], 'sum.py', None, 'sum_1_to_n')
    run = agent.new_run(session['id'], '验证并修复累加代码', 0, 'repair-test-01')
    await agent.run(run['id'])
    reports = store.find('reports')
    record_property('reports', dumps(reports))
    assert [r['status'] for r in reports] == ['OUTPUT_MISMATCH', 'PASS']
    assert len({r['test_spec_hash'] for r in reports}) == 1
    assert len({r['test_spec_revision'] for r in reports}) == 1
    assert len({r['code_hash'] for r in reports}) == 2
    drafts = store.find('drafts')
    assert drafts[0]['verification_status'] == 'STALE'
    assert '-print(sum(range(1,n)))' in drafts[1]['repair_diff']
    assert '+print(sum(range(1,n+1)))' in drafts[1]['repair_diff']
    assert store.find('repairs')[0]['count'] == 1
    assert store.get('runs', run['id'])['status'] == 'COMPLETED'
    assert not (root / 'sum.py').exists()


async def test_unrepairable_stops_after_two_and_survives_restart(setup_agent, real_runner):
    from app.agent import Agent
    from app.storage import Store

    agent, store, session, _, spec = fixture(setup_agent, real_runner)
    for index in range(3):
        did = draft(agent, session, BAD + f'# attempt {index}\n')
        report = await verify(agent, session, did, spec)
        assert report['status'] == 'OUTPUT_MISMATCH'
    assert store.find('repairs')[0]['count'] == 2
    store.close()
    reopened = Store(agent.settings.yunyun_data_dir / 'state.sqlite3')
    restored = Agent(agent.settings, reopened, ScriptedProvider(
        reply(('propose_patch', {'path': 'sum.py', 'content': GOOD, 'base_hash': None})) ))
    restored.verification.runner = real_runner
    run = restored.new_run(session['id'], '继续修复', 0, 'repair-exhausted')
    await restored.run(run['id'])
    result = reopened.get('runs', run['id'])
    assert result['status'] == 'STOPPED' and result['error']['code'] == 'REPAIR_LIMIT'
    assert len(reopened.find('drafts')) == 3
    with pytest.raises(AppError):
        restored.verification.delivery_candidates(session['id'])
    reopened.close()


async def test_all_artifacts_gate_cannot_hide_failed_answer(setup_agent, real_runner):
    agent, store, session, _, spec = fixture(setup_agent, real_runner)
    did = draft(agent, session, GOOD)
    await verify(agent, session, did, spec)
    draft(agent, session, 'print("not tested")', 'challenge_answer.py')
    with pytest.raises(AppError):
        agent.verification.delivery_candidates(session['id'])
    call = {'id': uid(), 'run_id': 'test', 'name': 'request_publish',
            'arguments': dumps({'draft_id': did})}
    prepared = await agent.registry.prepare_async(call, session, agent.workspace(session))
    with store.tx():
        result = agent.registry.execute(call, session, agent.workspace(session), prepared=prepared)
    assert result['error']['code'] == 'VERIFICATION_REQUIRED'
    assert store.find('approvals') == []


async def test_real_isolation_network_files_commands_pids(real_runner, record_property):
    code = '''import os,socket,subprocess,json
r={'uid':os.getuid(), 'env_key':os.getenv('DASHSCOPE_API_KEY'),
   'socket':os.path.exists('/var/run/docker.sock'), 'app':os.path.exists('/app'),
   'root':os.path.exists('/root/.ssh'), 'escape':os.path.exists('/tmp/../../app/.env')}
try:
 open('/etc/lesson-escape','w').write('bad'); r['write']='allowed'
except OSError: r['write']='denied'
try:
 socket.create_connection(('1.1.1.1',80),.1); r['network']='allowed'
except OSError: r['network']='denied'
r['cpu_max']=open('/sys/fs/cgroup/cpu.max').read().strip()
r['memory_max']=open('/sys/fs/cgroup/memory.max').read().strip()
r['pids_max']=open('/sys/fs/cgroup/pids.max').read().strip()
r['swap_max']=open('/sys/fs/cgroup/memory.swap.max').read().strip()
r['command']=subprocess.check_output(['python','-I','-c','print(7)']).decode().strip()
try:
 for i in range(40):
  if os.fork()==0:
   import signal
   signal.pause()
 r['pids']='unlimited'
except OSError: r['pids']='limited'
print(json.dumps(r,sort_keys=True))
'''
    result = await real_runner.execute(ExecutionRequest(job_id=uid(), code=code, input=''))
    record_property('isolation', result.model_dump_json())
    assert result.status == 'PASS', result
    actual = json.loads(result.stdout)
    assert actual == {'uid': 10001, 'env_key': None, 'socket': False, 'app': False,
                      'root': False, 'escape': False, 'write': 'denied', 'network': 'denied',
                      'command': '7', 'pids': 'limited', 'cpu_max': '50000 100000',
                      'memory_max': '134217728', 'pids_max': '32', 'swap_max': '0'}
    assert result.evidence['cleanup']
    # 上一用例的派生进程必须随整个容器回收；下一作业正常。
    next_result = await real_runner.execute(ExecutionRequest(job_id=uid(), code='print(42)', input=''))
    assert next_result.stdout == '42\n' and next_result.status == 'PASS'


async def test_timeout_descendants_and_client_cancel(real_runner):
    code = "import subprocess\nsubprocess.Popen(['python','-c','while True: pass'])\nwhile True: pass"
    result = await real_runner.execute(ExecutionRequest(job_id=uid(), code=code, input=''))
    assert result.status == 'TIMEOUT' and result.evidence['cleanup']
    task = asyncio.create_task(real_runner.execute(ExecutionRequest(job_id=uid(), code=code, input='')))
    await asyncio.sleep(.8)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(.8)
    result = await real_runner.execute(ExecutionRequest(job_id=uid(), code='print(9)', input=''))
    assert result.status == 'PASS' and result.stdout == '9\n'


async def test_no_progress_cannot_retest_unchanged_failure(setup_agent, real_runner):
    agent, store, session, _, spec = fixture(setup_agent, real_runner)
    did = draft(agent, session, BAD)
    await verify(agent, session, did, spec)
    with pytest.raises(AppError) as error:
        await agent.verification.prepare(session['id'], did, spec['id'])
    assert error.value.code == 'NO_PROGRESS'
    assert len(store.find('reports')) == 1


async def test_latest_report_only_and_cross_owner_api(setup_agent, real_runner):
    import httpx
    from app.api import create_app

    agent, store, session, _, spec = fixture(setup_agent, real_runner)
    did = draft(agent, session, GOOD)
    first = await verify(agent, session, did, spec)
    second = await verify(agent, session, did, spec)
    identity = await real_runner.identity()
    assert agent.verification.report_status(first, identity) == 'STALE'
    assert agent.verification.report_status(second, identity) == 'PASS'
    from pydantic import SecretStr
    app = create_app(agent.settings.model_copy(update={
        'yunyun_local_token': SecretStr('capability-token')}), ScriptedProvider())
    # 同一真实SQLite，API使用私有Runner；由实际cookie创建资源归属。
    app.state.agent.verification.runner = real_runner
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://testserver',
                                 headers={'authorization': 'Bearer capability-token'}) as client:
        await client.post('/api/client')
        from app.domain import sha
        with store.tx():
            stored = store.get('sessions', session['id'])
            stored['owner'] = sha(client.cookies['yunyun_client'])
            store.put('sessions', stored)
        response = await client.get('/api/verification-reports/' + first['id'])
        assert response.status_code == 200 and response.json()['effective_status'] == 'STALE'
        snapshot = (await client.get('/api/sessions/' + session['id'])).json()
        assert [r['effective_status'] for r in snapshot['verification_reports']] == ['STALE', 'PASS']
        client.cookies.clear()
        await client.post('/api/client')
        assert (await client.get('/api/verification-reports/' + second['id'])).status_code == 404
    app.state.store.close()


async def test_agent_stops_immediately_after_second_failed_repair(setup_agent, real_runner, record_property):
    def test_latest(messages):
        did = json.loads(messages[-1]['content'])['data']['draft_id']
        return reply(('run_python_tests', {'draft_id': did, 'test_spec_revision': spec['id']}))

    def patch(index):
        return reply(('propose_patch', {'path': 'sum.py', 'content': BAD + f'# repair {index}\n',
                                         'base_hash': None}))
    provider = ScriptedProvider(patch(0), test_latest, patch(1), test_latest, patch(2), test_latest)
    agent, store, session, _ = setup_agent(provider)
    agent.verification.runner = real_runner
    with store.tx():
        spec = agent.verification.freeze(session['id'], 'sum.py', None, 'sum_1_to_n')
    run = agent.new_run(session['id'], '持续尝试修复', 0, 'two-fail-repairs')
    await agent.run(run['id'])
    assert len(provider.requests) == 6
    assert len(store.find('reports')) == 3
    assert store.get('runs', run['id'])['status'] == 'STOPPED'
    assert store.get('runs', run['id'])['error']['code'] == 'REPAIR_LIMIT'
    assert not provider.responses
    record_property('unrepairable', dumps({'run': store.get('runs', run['id']),
        'reports': store.find('reports'), 'repairs': store.find('repairs')}))
    assert store.find('repairs')[0]['count'] == 2
    with pytest.raises(AppError):
        agent.verification.delivery_candidates(session['id'])


@pytest.mark.parametrize('read_code', [
    'import sys\nn=int(sys.stdin.buffer.readline())',
    'import os\nn=int(os.read(0,64))',
    "import subprocess,sys\nn=int(subprocess.check_output([sys.executable,'-I','-c',"
    "'import sys;print(sys.stdin.readline().strip())']))",
])
async def test_normal_loop_uses_real_stdin(setup_agent, real_runner, read_code, record_property):
    agent, _, session, _, spec = fixture(setup_agent, real_runner)
    code = read_code + '\ntotal=0\nfor i in range(1,n+1): total+=i\nprint(total)\n'
    report = await verify(agent, session, draft(agent, session, code), spec)
    record_property('report', dumps(report))
    assert report['status'] == 'PASS', report
    assert [c['actual'] for c in report['cases']] == ['0\n', '1\n', '15\n']


async def test_correct_output_followed_by_exception_cannot_pass(setup_agent, real_runner, record_property):
    agent, _, session, _, spec = fixture(setup_agent, real_runner)
    code = GOOD + 'raise RuntimeError("after-correct-output")\n'
    report = await verify(agent, session, draft(agent, session, code), spec)
    record_property('report', dumps(report))
    assert report['status'] == 'RUNTIME_ERROR'
    assert [c['actual'] for c in report['cases']] == ['0\n', '1\n', '15\n']
    assert all(c['exit_code'] != 0 and 'after-correct-output' in c['stderr'] for c in report['cases'])
    with pytest.raises(AppError):
        agent.verification.delivery_candidates(session['id'])


async def test_zero_iteration_boundary_is_required(setup_agent, real_runner, record_property):
    agent, _, session, _, spec = fixture(setup_agent, real_runner)
    code = 'n=int(input())\nprint(1 if n==0 else sum(range(1,n+1)))\n'
    report = await verify(agent, session, draft(agent, session, code), spec)
    record_property('report', dumps(report))
    assert report['status'] == 'OUTPUT_MISMATCH'
    assert [(c['id'], c['expected'], c['actual']) for c in report['cases'] if c['status'] != 'PASS'] == [
        ('n=0', '0\n', '1\n')]
    assert [c['status'] for c in report['cases']] == ['OUTPUT_MISMATCH', 'PASS', 'PASS']


async def test_manager_rejects_auth_and_execution_policy_overrides(real_runner, record_property):
    async with real_runner.client() as client:
        response = await client.get('/identity', headers={'Authorization': 'Bearer invalid-token'})
        assert response.status_code == 403
        body = {'job_id': uid(), 'code': 'print(0)', 'input': '', 'expected': '0',
                'image': 'evil', 'timeout_seconds': 600, 'mount': '/'}
        response = await client.post('/execute', json=body)
        assert response.status_code == 422
        identity = (await client.get('/identity')).json()
        assert identity['active_jobs'] == []
        record_property('policy_override_rejected', '403 authentication / 422 forbidden fields')


async def test_tmpfs_and_privilege_limits_are_observable(real_runner, record_property):
    code = """import os,json,resource
status=dict(line.split(':',1) for line in open('/proc/self/status') if ':' in line)
r={'cap_eff':status['CapEff'].strip(),'no_new_privs':status['NoNewPrivs'].strip(),
   'seccomp':status['Seccomp'].strip(),'nofile':list(resource.getrlimit(resource.RLIMIT_NOFILE)),
   'core':list(resource.getrlimit(resource.RLIMIT_CORE))}
try:
 with open('/tmp/fill','wb') as target:
  for i in range(20): target.write(b'x'*1048576); target.flush()
 r['tmp']='unlimited'
except OSError as e: r['tmp_errno']=e.errno
print(json.dumps(r,sort_keys=True))
"""
    result = await real_runner.execute(ExecutionRequest(job_id=uid(), code=code, input=''))
    record_property('privilege_limits', result.model_dump_json())
    assert result.status == 'PASS', result
    assert json.loads(result.stdout) == {'cap_eff': '0000000000000000', 'no_new_privs': '1',
        'seccomp': '2', 'nofile': [64, 64], 'core': [0, 0], 'tmp_errno': 28}
    assert result.evidence['cleanup']


@pytest.mark.parametrize('suffix', ['.py', '.PY', '.pY'])
async def test_python_suffixes_real_execution_and_publish_gate(
        setup_agent, real_runner, suffix, record_property):
    agent, store, session, _ = setup_agent(ScriptedProvider())
    agent.verification.runner = real_runner
    path = 'answer' + suffix
    with store.tx():
        spec = agent.verification.freeze(session['id'], path, None, 'sum_1_to_n')

    def publish(did):
        call = {'id': uid(), 'run_id': 'suffix-test', 'name': 'request_publish',
                'arguments': dumps({'draft_id': did})}
        with store.tx():
            result = agent.registry.execute(call, session, agent.workspace(session))
        assert not result['ok'], result
        assert result['error']['code'] == 'VERIFICATION_REQUIRED'
        assert store.find('approvals', session['id']) == []

    bad = draft(agent, session, 'raise RuntimeError("suffix must be verified")\n', path)
    publish(bad)
    assert store.find('reports', session['id']) == []
    failed = await verify(agent, session, bad, spec)
    assert failed['status'] == 'RUNTIME_ERROR'
    publish(bad)
    good = draft(agent, session, GOOD, path)
    passed = await verify(agent, session, good, spec)
    assert passed['status'] == 'PASS'
    assert agent.verification.delivery_candidates(session['id'])[0]['id'] == good
    assert passed['test_spec_hash'] == failed['test_spec_hash']
    edited = draft(agent, session, GOOD + '# edited after PASS\n', path)
    assert store.get('drafts', good)['verification_status'] == 'STALE'
    assert store.get('drafts', edited)['verification_status'] == 'NOT_TESTED'
    publish(edited)
    # 即便请求的是另一个已通过的小写文件，整组检查仍须包含该大写后缀草稿。
    with store.tx():
        other_spec = agent.verification.freeze(session['id'], 'other.py', None, 'sum_1_to_n')
    other = draft(agent, session, GOOD, 'other.py')
    await verify(agent, session, other, other_spec)
    publish(other)
    assert store.get('drafts', good)['repair_diff']
    record_property('suffix_gate', dumps({'suffix': suffix, 'failed': failed, 'passed': passed,
        'edited': store.get('drafts', edited), 'approvals': store.find('approvals', session['id'])}))
