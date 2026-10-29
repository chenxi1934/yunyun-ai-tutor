import asyncio
import time

from app.domain import AppError, dumps, now, sha, uid
from app.storage import Store
from app.verification.models import CaseResult, TestCase, TestSpec, VerificationReport
from app.workspaces import is_python_path

BASELINES = {'sum_1_to_n': [TestCase(id=f'n={n}', input=f'{n}\n', expected=f'{v}\n')
                               for n, v in ((0, 0), (1, 1), (5, 15))]}


def fingerprint(code_hash, spec_hash, identity):
    return sha(dumps({'code_hash': code_hash, 'test_spec_hash': spec_hash,
                     'runtime_digest': identity['runtime_digest'],
                     'runner_policy_hash': identity['runner_policy_hash']}))


class VerificationService:
    def __init__(self, store: Store, runner):
        self.store, self.runner = store, runner
        self.identity = None

    def draft(self, sid, did):
        draft = self.store.get('drafts', did)
        if draft['session_id'] != sid:
            raise AppError('NOT_FOUND', '草稿不存在或不属于当前会话。', 404)
        if not is_python_path(draft['path']) or draft['operation'] != 'write':
            raise AppError('NOT_PYTHON_DRAFT', '只能验证 Python 代码草稿。', 422)
        return draft

    def latest_spec(self, sid, path):
        specs = [s for s in self.store.find('test_specs', sid) if s['path'] == path]
        if not specs:
            raise AppError('TEST_SPEC_REQUIRED', '请教师先冻结该代码文件的测试规格。', 409)
        return specs[-1]

    def freeze(self, sid, path, cases, baseline=None):
        # 只由教师 API / 固定基准调用；Agent 不持有该能力。
        existing = [s for s in self.store.find('test_specs', sid) if s['path'] == path]
        cases = BASELINES[baseline] if baseline else cases
        canonical = [c.model_dump() for c in cases]
        spec = TestSpec(id=uid(), session_id=sid, path=path, revision=len(existing) + 1,
                        cases=cases, source='baseline' if baseline else 'teacher',
                        created_at=now(), content_hash=sha(dumps({'path': path, 'cases': canonical})))
        self.store.put('test_specs', spec.model_dump())
        self.invalidate(sid, path)
        self.store.event(sid, None, 'test_spec.frozen', {'path': path, 'test_spec_revision': spec.id,
                                                      'content_hash': spec.content_hash})
        return spec.model_dump()

    def invalidate(self, sid, path):
        for draft in self.store.find('drafts', sid):
            if draft['path'] == path:
                if draft['verification_status'] != 'NOT_TESTED':
                    draft['verification_status'] = 'STALE'
                draft['status'] = 'DRAFT'
                self.store.put('drafts', draft)
        for approval in self.store.find('approvals', sid):
            draft = self.store.get('drafts', approval['draft_id'])
            if draft['path'] == path and approval['status'] == 'PENDING':
                approval['status'] = 'STALE'
                self.store.put('approvals', approval)

    def repair_key(self, sid, path):
        return sha(sid + ':' + path)

    def repair_guard(self, sid, path, code_hash):
        records = [r for r in self.store.find('repairs', sid) if r['path'] == path]
        if not records or not records[-1]['failed']:
            return
        record = records[-1]
        if code_hash in record['failed_hashes']:
            raise AppError('NO_PROGRESS', '重复提交已失败的代码 Hash，停止自动修复。', 409)
        if record['count'] >= 2:
            raise AppError('REPAIR_LIMIT', '该代码已用完两次自动修复，不能交付。', 409)
        record['count'] += 1
        self.store.put('repairs', record)

    def refresh(self, sid, identity):
        self.identity = identity
        for draft in self.store.find('drafts', sid):
            if draft['verification_status'] == 'PASS' and not self.current_pass(draft, identity):
                self.invalidate(sid, draft['path'])

    def current_pass(self, draft, identity=None):
        identity = identity or self.identity
        if not identity or not identity.get('ready') or draft['verification_status'] != 'PASS':
            return False
        latest = [d for d in self.store.find('drafts', draft['session_id']) if d['path'] == draft['path']][-1]
        if latest['id'] != draft['id'] or sha(draft['content']) != draft['content_hash']:
            return False
        reports = [r for r in self.store.find('reports', draft['session_id']) if r['draft_id'] == draft['id']]
        if not reports:
            return False
        spec = self.latest_spec(draft['session_id'], draft['path'])
        report = reports[-1]
        expected_fingerprint = fingerprint(draft['content_hash'], spec['content_hash'], identity)
        return (report['status'] == 'PASS' and report['fingerprint'] == expected_fingerprint
                and report['test_spec_revision'] == spec['id']
                and [{k: c[k] for k in ('id', 'input', 'expected')} for c in report['cases']] == spec['cases']
                and all(c['status'] == 'PASS' and c['exit_code'] == 0
                        and c['actual'] == c['expected'] and c['evidence'].get('cleanup')
                        for c in report['cases']))

    def report_status(self, report, identity):
        draft = self.store.get('drafts', report['draft_id'])
        if draft.get('report_id') != report['id'] or draft['verification_status'] == 'STALE':
            return 'STALE'
        if report['status'] == 'PASS' and not self.current_pass(draft, identity):
            return 'STALE'
        return report['status']

    def delivery_candidates(self, sid):
        latest = {d['path']: d for d in self.store.find('drafts', sid) if is_python_path(d['path'])}
        if not latest or any(d['operation'] != 'write' or not self.current_pass(d)
                             for d in latest.values()):
            raise AppError('VERIFICATION_REQUIRED', '存在失败、过期或漏测代码，不能进入可交付候选。', 409)
        return list(latest.values())

    async def prepare(self, sid, did, spec_id):
        identity = await self.runner.identity()
        draft = self.draft(sid, did)
        spec = self.latest_spec(sid, draft['path'])
        if spec['id'] != spec_id:
            raise AppError('STALE_TEST_SPEC', '必须使用教师冻结的最新测试规格。', 409)
        latest = [d for d in self.store.find('drafts', sid) if d['path'] == draft['path']][-1]
        if latest['id'] != did:
            raise AppError('STALE_DRAFT', '只能验证最新代码版本。', 409)
        if sha(draft['content']) != draft['content_hash']:
            raise AppError('CODE_HASH_MISMATCH', '代码快照 Hash 不一致。', 409)
        previous = [r for r in self.store.find('reports', sid) if r['draft_id'] == did]
        if previous and (previous[-1]['fingerprint'] == fingerprint(draft['content_hash'], spec['content_hash'], identity)
                         and previous[-1]['status'] not in {'RUNNER_ERROR', 'INTERRUPTED', 'PASS'}):
            raise AppError('NO_PROGRESS', '代码和测试均未改变，停止重复执行失败版本。', 409)
        from app.verification.models import ExecutionRequest
        results = []
        started = time.monotonic()
        for case in spec['cases']:
            try:
                remaining = 30 - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError
                execution = await asyncio.wait_for(self.runner.execute(ExecutionRequest(
                    job_id=uid(), code=draft['content'], input=case['input'])), remaining)
                if (execution.runtime_digest != identity['runtime_digest']
                        or execution.runner_policy_hash != identity['runner_policy_hash']):
                    raise AppError('RUNNER_CHANGED', '执行期间运行时或策略变化，请重测。', 503)
                status, error = execution.status, execution.error
                if status == 'PASS':
                    if execution.exit_code != 0 or not execution.evidence.get('cleanup'):
                        status, error = 'RUNNER_ERROR', '执行证据不完整'
                    elif execution.stdout != case['expected']:
                        status, error = 'OUTPUT_MISMATCH', '实际输出与冻结期望不匹配（精确比较）'
                result = CaseResult(**case, actual=execution.stdout, stdout=execution.stdout,
                    stderr=execution.stderr, exit_code=execution.exit_code,
                    duration_ms=execution.duration_ms, status=status, error=error,
                    evidence=execution.evidence)
            except (AppError, TimeoutError) as exc:
                result = CaseResult(**case, actual='', stdout='', stderr='', exit_code=None,
                    duration_ms=0, status='TIMEOUT' if isinstance(exc, TimeoutError) else 'RUNNER_ERROR',
                    error='整套代码验证超过 30 秒' if isinstance(exc, TimeoutError) else exc.message,
                    evidence={'executed': False})
            results.append(result)
        status = next((r.status for r in results if r.status != 'PASS'), 'PASS')
        report = VerificationReport(id=uid(), session_id=sid, draft_id=did, path=draft['path'],
            code_hash=draft['content_hash'], test_spec_revision=spec_id,
            test_spec_hash=spec['content_hash'], runtime_digest=identity['runtime_digest'],
            runner_policy_hash=identity['runner_policy_hash'],
            fingerprint=fingerprint(draft['content_hash'], spec['content_hash'], identity),
            status=status, cases=results, created_at=now(), evidence_ref='')
        report.evidence_ref = 'verification_report:' + report.id
        return report.model_dump()

    def commit(self, report):
        draft = self.draft(report['session_id'], report['draft_id'])
        identity = {'ready': True, 'runtime_digest': report['runtime_digest'],
                    'runner_policy_hash': report['runner_policy_hash']}
        spec = self.latest_spec(draft['session_id'], draft['path'])
        latest = [d for d in self.store.find('drafts', draft['session_id']) if d['path'] == draft['path']][-1]
        if (latest['id'] != draft['id'] or spec['id'] != report['test_spec_revision']
                or report['fingerprint'] != fingerprint(sha(draft['content']), spec['content_hash'], identity)):
            raise AppError('STALE_VERIFICATION', '代码或测试已变化，丢弃迟到报告。', 409)
        self.identity = identity
        self.store.put('reports', report)
        draft['verification_status'] = report['status']
        draft['report_id'] = report['id']
        draft['status'] = 'PENDING_REVIEW' if report['status'] == 'PASS' else 'VALIDATION_FAILED'
        self.store.put('drafts', draft)
        records = [r for r in self.store.find('repairs', draft['session_id']) if r['path'] == draft['path']]
        record = records[-1] if records else {'id': self.repair_key(draft['session_id'], draft['path']),
            'session_id': draft['session_id'], 'path': draft['path'], 'count': 0, 'failed_hashes': []}
        record['failed'] = report['status'] != 'PASS'
        if record['failed'] and draft['content_hash'] not in record['failed_hashes']:
            record['failed_hashes'].append(draft['content_hash'])
        self.store.put('repairs', record)
        self.store.event(draft['session_id'], draft['run_id'], 'verification.completed', report)
        return report
