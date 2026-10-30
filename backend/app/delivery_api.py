import asyncio
import subprocess
import sys
from typing import Literal

from fastapi import Request
from fastapi.responses import Response
from pydantic import Field

from app.domain import AppError, ProposePatch, StrictModel, dumps, uid


class Revision(StrictModel):
    expected_revision: int = Field(ge=0)


class DraftRequest(ProposePatch):
    expected_revision: int = Field(ge=0)


class DraftPublish(Revision):
    draft_id: str


class DraftRefresh(DraftPublish):
    current_hash: str | None


class Reconcile(Revision):
    snapshot_hash: str = Field(min_length=64, max_length=64)
    decision: Literal['accept', 'reject', 'rollback']


def register_delivery(app, agent, session, result, execution_lock):
    store, delivery = agent.store, agent.delivery

    def mutation(request, sid, revision):
        value = session(request, sid)
        if value['revision'] != revision:
            raise AppError('REVISION_CONFLICT', '会话已变化，请刷新。', 409)
        if execution_lock.locked():
            raise AppError('RUN_ACTIVE', '请先等待当前任务结束。', 409)
        delivery.idle(sid)
        return value

    def bump(value):
        value['revision'] += 1
        store.put('sessions', value)

    async def refresh(sid):
        try:
            identity = await agent.verification.runner.identity()
        except AppError:
            identity = None
        with store.tx():
            agent.verification.refresh(sid, identity)

    @app.post('/api/local-workspace/dialog')
    async def choose(request: Request):
        if agent.settings.yunyun_mode != 'pc' or sys.platform != 'darwin':
            raise AppError('LOCAL_ONLY', '此入口仅供macOS本机选择目录；其他平台使用启动参数。', 403)
        def dialog():
            return subprocess.run(['osascript', '-e', 'POSIX path of (choose folder with prompt "选择教师教学工作区")'],
                                  capture_output=True, text=True, timeout=120)
        try:
            selected = await asyncio.to_thread(dialog)
        except subprocess.TimeoutExpired:
            raise AppError('DIALOG_CANCELLED', '选择目录超时，请重试。', 409) from None
        if selected.returncode:
            raise AppError('DIALOG_CANCELLED', '已取消选择，原工作区保留。', 409)
        from pathlib import Path
        root = Path(selected.stdout.strip())
        if root.is_symlink() or not root.is_dir():
            raise AppError('WORKSPACE_DENIED', '请选择真实目录。', 403)
        data = agent.settings.yunyun_data_dir.resolve()
        if data == root.resolve() or data.is_relative_to(root.resolve()):
            raise AppError('WORKSPACE_DENIED', '工作区不能包含应用数据库。', 403)
        agent.settings.yunyun_workspace = root.resolve()
        return result(request, {'workspace_name': root.name})

    @app.post('/api/sessions/{sid}/drafts')
    async def draft(request: Request, sid: str, body: DraftRequest):
        with store.tx():
            value = mutation(request, sid, body.expected_revision)
            call = {'id': uid(), 'run_id': None, 'session_id': sid, 'name': 'propose_patch',
                    'arguments': dumps(body.model_dump(exclude={'expected_revision'}))}
            response = agent.registry.execute(call, value, agent.workspace(value))
            if not response['ok']:
                e = response['error']
                raise AppError(e['code'], e['message'], 409)
            bump(value)
        return result(request, response['data'])

    @app.post('/api/sessions/{sid}/publish-draft')
    async def publish_draft(request: Request, sid: str, body: DraftPublish):
        session(request, sid)
        await refresh(sid)
        with store.tx():
            value = mutation(request, sid, body.expected_revision)
            approval = delivery.prepare_draft(value, body.draft_id)
            bump(value)
        return result(request, {'approval': approval})

    @app.post('/api/sessions/{sid}/refresh-draft')
    async def refresh_draft(request: Request, sid: str, body: DraftRefresh):
        with store.tx():
            value = mutation(request, sid, body.expected_revision)
            draft = delivery.refresh_draft(value, body.draft_id, body.current_hash)
            bump(value)
        return result(request, draft)

    @app.post('/api/sessions/{sid}/lessons/{lid}/delivery')
    async def prepare_lesson(request: Request, sid: str, lid: str, body: Revision):
        session(request, sid)
        await refresh(sid)
        with store.tx():
            value = mutation(request, sid, body.expected_revision)
            view = agent.education.view(sid, lid)
            files = agent.education.export(sid, lid)['files']
            # 版本无关目标目录，重复交付会准确显示已有正式文件覆盖Diff。
            files = {f'published/{lid}/{p}': c for p, c in files.items()}
            approval = delivery.prepare(value, files, lesson_id=lid,
                lesson_revision=view['revision'], lesson_hash=view['content_hash'])
            bump(value)
        return result(request, {'approval': approval})

    @app.post('/api/sessions/{sid}/commits/{cid}/restore-draft')
    async def restore(request: Request, sid: str, cid: str, body: Revision):
        session(request, sid)
        await refresh(sid)
        with store.tx():
            value = mutation(request, sid, body.expected_revision)
            approval = delivery.restore(value, store.get('commits', cid))
            bump(value)
        return result(request, {'approval': approval})

    @app.get('/api/sessions/{sid}/commits/{cid}/recovery')
    async def inspect_recovery(request: Request, sid: str, cid: str):
        value = session(request, sid)
        return result(request, {'recovery': delivery.inspect_recovery(value, cid)})

    @app.post('/api/sessions/{sid}/commits/{cid}/recovery')
    async def reconcile(request: Request, sid: str, cid: str, body: Reconcile):
        value = session(request, sid)
        if execution_lock.locked():
            raise AppError('RUN_ACTIVE', '请等待当前操作结束。', 409)
        commit = delivery.reconcile(value, cid, body.expected_revision, body.snapshot_hash, body.decision)
        return result(request, {'commit': commit})

    @app.get('/api/sessions/{sid}/lessons/{lid}/package')
    async def package(request: Request, sid: str, lid: str):
        value = session(request, sid)
        await refresh(sid)
        content = delivery.archive(value, lid)
        return Response(content, media_type='application/zip',
                        headers={'Content-Disposition': 'attachment; filename="lesson-package.zip"'})
