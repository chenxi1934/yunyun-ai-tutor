"""教师专用提交服务。审批快照、持久日志与文件操作均不暴露为模型工具。"""
import io
import zipfile

from app.domain import AppError, dumps, now, sha, uid
from app.tools import Registry
from app.workspaces import is_python_path


class DeliveryService:
    def __init__(self, agent):
        self.agent, self.store = agent, agent.store

    def recover(self):
        with self.store.tx():
            for approval in self.store.find('approvals'):
                if approval['status'] != 'COMMITTED' or not approval.get('call_id'):
                    continue
                call = self.store.get('calls', approval['call_id'])
                if call['status'] == 'DONE':
                    continue
                self.agent._finish_call(call, {'call_id': call['id'], 'ok': True,
                    'data': {'commit_id': approval['commit_id'], 'formal_file_changed': True}, 'error': None})
                run = self.store.get('runs', approval['run_id'])
                run['status'] = 'INTERRUPTED'
                self.store.put('runs', run)
                session = self.store.get('sessions', approval['session_id'])
                session['revision'] += 1
                self.store.put('sessions', session)

    def ensure_reconciled(self, session):
        workspace = self.store.get('workspaces', session['workspace_id'])
        for commit in self.store.find('commits'):
            if commit['status'] not in {'APPLYING', 'ROLLING_BACK', 'INTERRUPTED'}:
                continue
            other = self.store.get('sessions', commit['session_id'])
            target = self.store.get('workspaces', other['workspace_id'])
            if target['identity'] == workspace['identity']:
                raise AppError('RECOVERY_REQUIRED', '该工作区有未解决的提交中断，请先对账恢复。', 409,
                               details={'commit_id': commit['id']})

    def idle(self, sid, allowed_run=None):
        if any(r['status'] in {'READY', 'RUNNING'} and r['id'] != allowed_run
               for r in self.store.find('runs', sid)):
            raise AppError('RUN_ACTIVE', '请等待或停止正在执行的任务。', 409)

    def gate(self, session, approval):
        sid = session['id']
        self.ensure_reconciled(session)
        self.idle(sid, approval.get('run_id'))
        if approval.get('lesson_id'):
            view = self.agent.education.view(sid, approval['lesson_id'])
            if (view['revision'] != approval['lesson_revision'] or
                    view['content_hash'] != approval['lesson_hash'] or not view['delivery_ready']):
                raise AppError('EDUCATION_REVIEW_REQUIRED', '教案已变化或尚未完成当前验证与逐项审核。', 409)
        elif self.store.find('lessons', sid):
            latest = self.store.find('lessons', sid)[-1]
            if not self.agent.education.view(sid, latest['lesson_id'])['delivery_ready']:
                raise AppError('EDUCATION_REVIEW_REQUIRED', '须先完成当前教案审核。', 409)
        latest = {d['path']: d for d in self.store.find('drafts', sid)}
        if any(is_python_path(d['path']) for d in latest.values()):
            self.agent.verification.delivery_candidates(sid)
        for did in approval.get('draft_ids', []):
            draft = self.store.get('drafts', did)
            if latest[draft['path']]['id'] != did:
                raise AppError('STALE_DRAFT', '草稿已有新版本，请重新审核。', 409)
        for entry in approval['entries']:
            if is_python_path(entry['path']) and entry['content'] is not None:
                if not any(d['content_hash'] == entry['content_hash'] and
                           self.agent.verification.current_pass(d) for d in latest.values()
                           if is_python_path(d['path']) and d['operation'] == 'write'):
                    raise AppError('VERIFICATION_REQUIRED', '待写入代码没有当前版本的真实通过证据。', 409)
            if entry['content'] is not None and sha(entry['content']) != entry['content_hash']:
                raise AppError('HASH_MISMATCH', '审批快照不一致。', 409)

    def prepare(self, session, files, *, originals=None, modes=None, **metadata):
        sid = session['id']
        self.ensure_reconciled(session)
        self.idle(sid, metadata.get('run_id'))
        ws = self.agent.workspace(session)
        entries = []
        for path, content in files.items():
            current = originals[path] if originals is not None else ws.read(path, allow_missing=True)
            if content is None and current['hash'] is None:
                raise AppError('FILE_NOT_FOUND', '待删除文件不存在。', 404)
            if content is not None and len(content.encode('utf-8')) > ws.max_bytes:
                raise AppError('FILE_TOO_LARGE', '教案文件过大，请缩小产出。', 413)
            entries.append({'path': path, 'content': content, 'content_hash': sha(content) if content is not None else None,
                'before': current['content'] if current['hash'] is not None else None,
                'before_mode': current.get('mode'), 'base_mode': current.get('mode'),
                'content_mode': (modes or {}).get(path, current.get('mode') if current.get('mode') is not None else 0o600) if content is not None else None,
                'base_hash': current['hash'], 'operation': 'delete' if content is None else 'write',
                'diff': Registry._diff(path, current['content'], content or '')})
        approval = {'id': uid(), 'session_id': sid, 'run_id': None, 'call_id': None,
                    'draft_id': None, 'draft_ids': [], 'status': 'PENDING', 'entries': entries,
                    'created_at': now(), **metadata}
        approval['snapshot_hash'] = sha(dumps(entries))
        self.gate(session, approval)
        self.store.put('approvals', approval)
        self.store.event(sid, None, 'approval.requested', {'approval_id': approval['id'],
                         'snapshot_hash': approval['snapshot_hash'], 'paths': list(files)})
        return approval

    def prepare_draft(self, session, did, *, original=None, **metadata):
        draft = self.store.get('drafts', did)
        if draft['session_id'] != session['id']:
            raise AppError('NOT_FOUND', '草稿不属于当前会话。', 404)
        original = original if original is not None else self.agent.workspace(session).read(draft['path'], allow_missing=True)
        if original['hash'] != draft['base_hash']:
            raise AppError('REVISION_CONFLICT', '正式文件已变化，请重新生成草稿。', 409)
        return self.prepare(session, {draft['path']: None if draft['operation'] == 'delete' else draft['content']},
                            originals={draft['path']: original}, draft_id=did, draft_ids=[did], **metadata)

    def hydrate(self, session, approval):
        # 阶段02原生request_publish审批在接受时仍核对它保存的精确Hash。
        if 'entries' in approval:
            return approval
        draft = self.store.get('drafts', approval['draft_id'])
        if draft['content_hash'] != approval['content_hash']:
            raise AppError('HASH_MISMATCH', '待审草稿Hash已变化。', 409)
        current = self.agent.workspace(session).read(draft['path'], allow_missing=True)
        if current['hash'] != approval['base_hash']:
            raise AppError('REVISION_CONFLICT', '正式文件已变化。', 409)
        content = None if draft['operation'] == 'delete' else draft['content']
        approval['entries'] = [{'path': draft['path'], 'content': content,
            'content_hash': sha(content) if content is not None else None, 'before': current['content'] if current['hash'] else None,
            'before_mode': current.get('mode'), 'base_mode': current.get('mode'),
            'content_mode': current.get('mode') if current.get('mode') is not None else 0o600,
            'base_hash': current['hash'], 'operation': draft['operation'], 'diff': draft['diff']}]
        approval['snapshot_hash'] = sha(dumps(approval['entries']))
        approval['draft_ids'] = [draft['id']]
        return approval

    def decide(self, aid, revision, approve):
        with self.store.lock:
            approval = self.store.get('approvals', aid)
            session = self.store.get('sessions', approval['session_id'])
            if session['revision'] != revision:
                raise AppError('REVISION_CONFLICT', '会话已变化，请刷新后审核。', 409)
            if approval['status'] == 'INTERRUPTED':
                raise AppError('RECOVERY_REQUIRED', '该审批写入中断，请从提交记录先对账恢复。', 409)
            if approval['status'] != 'PENDING':
                # 幂等确认不重放真实写入。
                if approve and approval['status'] == 'COMMITTED':
                    return approval
                raise AppError('APPROVAL_DECIDED', '审批已处理或已过期。', 409)
            self.idle(session['id'])
            if approve:
                approval = self.hydrate(session, approval)
                self.gate(session, approval)
                if sha(dumps(approval['entries'])) != approval['snapshot_hash']:
                    raise AppError('HASH_MISMATCH', '审批内容已变化。', 409)
                self.commit(session, approval)
            with self.store.tx():
                approval['status'] = 'COMMITTED' if approve else 'REJECTED'
                self.store.put('approvals', approval)
                if approval.get('call_id'):
                    call = self.store.get('calls', approval['call_id'])
                    self.agent._finish_call(call, {'call_id': call['id'], 'ok': approve,
                        'data': {'commit_id': approval.get('commit_id'), 'formal_file_changed': approve} if approve else None,
                        'error': None if approve else {'code': 'APPROVAL_DENIED', 'message': '教师拒绝正式变更。', 'retryable': False}})
                    run = self.store.get('runs', approval['run_id'])
                    run['status'] = 'INTERRUPTED'
                    self.store.put('runs', run)
                session['revision'] += 1
                self.store.put('sessions', session)
                self.store.event(session['id'], approval.get('run_id'), 'approval.decided',
                    {'approval_id': aid, 'status': approval['status'], 'formal_file_changed': approve})
            return approval

    def commit(self, session, approval):
        self.ensure_reconciled(session)
        ws = self.agent.workspace(session)
        entries = [dict(entry) for entry in approval['entries']]
        for entry in entries:
            current = ws.read(entry['path'], allow_missing=True)
            if current['hash'] != entry['base_hash'] or (entry.get('base_mode') is not None and current.get('mode') != entry['base_mode']):
                raise AppError('REVISION_CONFLICT', '有文件已被外部修改，请重新审核Diff。', 409)
            # 旧审批未记录权限；提交日志补齐磁盘实况，不改变教师已确认的内容Hash。
            entry.setdefault('before_mode', current.get('mode'))
            entry.setdefault('base_mode', current.get('mode'))
            entry.setdefault('content_mode', (current.get('mode') if current.get('mode') is not None else 0o600) if entry['content'] is not None else None)
        commit = {'id': uid(), 'session_id': session['id'], 'approval_id': approval['id'],
            'status': 'APPLYING', 'created_at': now(), 'entries': entries,
            'lesson_id': approval.get('lesson_id'), 'lesson_revision': approval.get('lesson_revision'),
            'applied': []}
        with self.store.tx():
            self.store.put('commits', commit)
        try:
            for entry in commit['entries']:
                ws.replace(entry['path'], entry['content'], entry['base_hash'],
                           mode=entry.get('content_mode'), expected_mode=entry.get('base_mode'))
                commit['applied'].append(entry['path'])
                with self.store.tx():
                    self.store.put('commits', commit)
        except BaseException:
            with self.store.tx():
                self.store.interrupt_commit(commit)
            raise
        with self.store.tx():
            commit['status'] = 'COMMITTED'
            approval['commit_id'] = commit['id']
            # 和审批一并落库，进程在返回前中断也不会重复提交。
            approval['status'] = 'COMMITTED'
            self.store.put('approvals', approval)
            self.store.put('commits', commit)
            self.store.event(session['id'], None, 'workspace.committed',
                             {'commit_id': commit['id'], 'paths': commit['applied']})

    def inspect_recovery(self, session, cid):
        commit = self.store.get('commits', cid)
        if commit['session_id'] != session['id']:
            raise AppError('NOT_FOUND', '提交不属于当前会话。', 404)
        if commit['status'] != 'INTERRUPTED':
            raise AppError('RECOVERY_NOT_REQUIRED', '该提交没有待处理的中断。', 409)
        ws, entries = self.agent.workspace(session), []
        for entry in commit['entries']:
            try:
                current = ws.read(entry['path'], allow_missing=True)
                before = current['hash'] == entry['base_hash'] and (
                    entry.get('before_mode') is None or current.get('mode') == entry['before_mode'])
                after = current['hash'] == entry['content_hash'] and (
                    entry.get('content_mode') is None or current.get('mode') == entry['content_mode'])
                state = 'UNCHANGED' if before and after else 'BEFORE' if before else 'AFTER' if after else 'CONFLICT'
                item = {'path': entry['path'], 'state': state, 'current_hash': current['hash'],
                        'current_mode': current.get('mode'), 'before_hash': entry['base_hash'],
                        'before_mode': entry.get('before_mode'), 'after_hash': entry['content_hash'],
                        'after_mode': entry.get('content_mode'),
                        'rollback_diff': Registry._diff(entry['path'], current['content'], entry['before'] or '')}
            except AppError as error:
                item = {'path': entry['path'], 'state': 'CONFLICT', 'error': error.payload()}
            entries.append(item)
        return {'commit_id': cid, 'snapshot_hash': sha(dumps(entries)), 'entries': entries,
                'can_accept': all(e['state'] in {'AFTER', 'UNCHANGED'} for e in entries),
                'can_reject': all(e['state'] in {'BEFORE', 'UNCHANGED'} for e in entries),
                'can_rollback': all(e['state'] != 'CONFLICT' for e in entries)}

    def reconcile(self, session, cid, revision, snapshot_hash, decision):
        with self.store.lock:
            session = self.store.get('sessions', session['id'])
            if session['revision'] != revision:
                raise AppError('REVISION_CONFLICT', '会话已变化，请重新对账。', 409)
            self.idle(session['id'])
            inspection = self.inspect_recovery(session, cid)
            if inspection['snapshot_hash'] != snapshot_hash:
                raise AppError('RECOVERY_CONFLICT', '文件现状已变化，请重新查看对账Diff。', 409)
            allowed = {'accept': 'can_accept', 'reject': 'can_reject', 'rollback': 'can_rollback'}
            if decision not in allowed or not inspection[allowed[decision]]:
                raise AppError('RECOVERY_CONFLICT', '文件状态不满足该操作；未知外部修改须先人工核对，未自动覆盖。', 409)
            commit = self.store.get('commits', cid)
            if decision == 'rollback':
                commit['status'] = 'ROLLING_BACK'
                commit['recovery_snapshot_hash'] = snapshot_hash
                commit['recovery_applied'] = []
                with self.store.tx():
                    self.store.put('commits', commit)
                try:
                    ws = self.agent.workspace(session)
                    for entry, observed in zip(commit['entries'], inspection['entries'], strict=True):
                        if observed['state'] != 'AFTER':
                            continue
                        ws.replace(entry['path'], entry['before'], observed['current_hash'],
                                   mode=entry['before_mode'] if entry.get('before_mode') is not None else 0o600,
                                   expected_mode=observed.get('current_mode'))
                        commit['recovery_applied'].append(entry['path'])
                        with self.store.tx():
                            self.store.put('commits', commit)
                except BaseException:
                    with self.store.tx():
                        self.store.interrupt_commit(commit)
                    raise
            with self.store.tx():
                approval = self.store.get('approvals', commit['approval_id'])
                accepted = decision == 'accept'
                commit['status'] = 'COMMITTED' if accepted else 'ROLLED_BACK' if decision == 'rollback' else 'REJECTED'
                commit['reconciled_at'], commit['reconciliation'] = now(), decision
                if accepted:
                    commit['applied'] = [e['path'] for e in commit['entries']]
                approval['status'] = 'COMMITTED' if accepted else 'REJECTED'
                approval['commit_id'] = cid
                self.store.put('commits', commit)
                self.store.put('approvals', approval)
                if approval.get('call_id'):
                    call = self.store.get('calls', approval['call_id'])
                    if call['status'] != 'DONE':
                        self.agent._finish_call(call, {'call_id': call['id'], 'ok': accepted,
                            'data': {'commit_id': cid, 'reconciled': True, 'formal_file_changed': True} if accepted else None,
                            'error': None if accepted else {'code': 'APPROVAL_DENIED', 'message': '教师对账后拒绝提交，已保留或恢复原文件。', 'retryable': False}})
                    run = self.store.get('runs', approval['run_id'])
                    if run['status'] not in {'STOPPED', 'COMPLETED'}:
                        run['status'], run['error'] = 'INTERRUPTED', None
                        self.store.put('runs', run)
                session['revision'] += 1
                self.store.put('sessions', session)
                self.store.event(session['id'], approval.get('run_id'), 'workspace.reconciled',
                                 {'commit_id': cid, 'decision': decision, 'status': commit['status']})
            return commit

    def restore(self, session, commit):
        if commit['session_id'] != session['id']:
            raise AppError('NOT_FOUND', '版本不属于当前会话。', 404)
        ws = self.agent.workspace(session)
        files = {e['path']: e['before'] for e in commit['entries']
                 if e['before'] is not None or ws.read(e['path'], allow_missing=True)['hash'] is not None}
        if not files:
            raise AppError('NO_CHANGES', '没有需要回退的文件。', 409)
        approval = self.prepare(session, files, modes={e['path']: e.get('before_mode') if e.get('before_mode') is not None else 0o600 for e in commit['entries']},
                                restore_of=commit['id'])
        for entry in approval['entries']:
            if is_python_path(entry['path']) and entry['content'] is not None:
                drafts = self.store.find('drafts', session['id'])
                if not any(d['content_hash'] == entry['content_hash'] and
                           self.agent.verification.current_pass(d) for d in drafts if d['operation'] == 'write'):
                    raise AppError('RESTORE_CODE_REQUIRES_DRAFT', '历史代码须先恢复为教学项目新草稿，重新验证和审核后交付。', 409)
        return approval

    def archive(self, session, lid):
        self.ensure_reconciled(session)
        view = self.agent.education.view(session['id'], lid)
        if not view['delivery_ready']:
            raise AppError('EDUCATION_REVIEW_REQUIRED', '当前教案尚未完成验证或审核。', 409)
        commits = [c for c in self.store.find('commits', session['id']) if c['status'] == 'COMMITTED'
                   and c.get('lesson_id') == lid and c.get('lesson_revision') == view['revision']]
        if not commits:
            raise AppError('COMMIT_REQUIRED', '请先查看文件Diff并确认正式交付。', 409)
        commit = commits[-1]
        ws, buffer = self.agent.workspace(session), io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('delivery-receipt.json', dumps({'kind': 'teacher_reviewed_package',
                'commit_id': commit['id'], 'lesson_id': lid, 'lesson_revision': view['revision'],
                'committed_at': commit['created_at'], 'formal_file_changed': True,
                'files': {e['path']: e['content_hash'] for e in commit['entries']}}))
            for entry in commit['entries']:
                current = ws.read(entry['path'])
                if current['hash'] != entry['content_hash']:
                    raise AppError('REVISION_CONFLICT', '交付文件已被外部修改，请重新交付。', 409)
                archive.writestr(entry['path'].split('/', 2)[-1], current['content'])
        return buffer.getvalue()
