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


class LocalDirectory(StrictModel):
    path: str = Field(min_length=1, max_length=4096)


class LocalOpen(StrictModel):
    target: Literal['read', 'folder']


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

    def bind_directory(value):
        from pathlib import Path
        if agent.settings.yunyun_mode != 'pc':
            raise AppError('LOCAL_ONLY', '只能在本机工作台选择教学目录。', 403)
        root = Path(value).expanduser()
        if not root.is_absolute():
            raise AppError('WORKSPACE_DENIED', '请填写教学目录的完整路径。', 422)
        if root.is_symlink() or not root.is_dir():
            raise AppError('WORKSPACE_DENIED', '请选择已存在的真实教学目录。', 409)
        root = root.resolve()
        data = agent.settings.yunyun_data_dir.resolve()
        if data == root or data.is_relative_to(root):
            raise AppError('WORKSPACE_DENIED', '教学目录不能包含应用运行数据，请在项目目录外选择。', 403)
        agent.settings.yunyun_workspace = root
        return root.name

    @app.post('/api/local-workspace/select')
    async def select_directory(request: Request, body: LocalDirectory):
        return result(request, {'workspace_name': bind_directory(body.path)})

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
        return result(request, {'workspace_name': bind_directory(selected.stdout.strip())})

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

    async def local_package(request, sid, lid):
        from pathlib import Path
        if agent.settings.yunyun_mode != 'pc':
            raise AppError('LOCAL_ONLY', '此入口仅供本机工作台使用。', 403)
        value = session(request, sid)
        await refresh(sid)
        # 复用下载的完整验证/审批/文件Hash闸口，不复制或再次写入任何文件。
        delivery.archive(value, lid)
        workspace = agent.workspace(value)
        relative = f'published/{lid}/开始阅读.html'
        workspace.read(relative)
        target = workspace.root / relative
        if target.resolve(strict=True) != target.absolute():
            raise AppError('PATH_DENIED', '交付目录已变化，请重新核对工作区。', 409)
        return {'directory': str(target.parent), 'entry': str(target),
                'relative_directory': str(Path(relative).parent)}

    @app.get('/api/sessions/{sid}/lessons/{lid}/local-package')
    async def local_package_location(request: Request, sid: str, lid: str):
        return result(request, await local_package(request, sid, lid))

    @app.post('/api/sessions/{sid}/lessons/{lid}/local-package/open')
    async def open_local_package(request: Request, sid: str, lid: str, body: LocalOpen):
        if sys.platform != 'darwin':
            raise AppError('LOCAL_ONLY', '当前平台请按显示的保存路径打开教案。', 403)
        location = await local_package(request, sid, lid)
        # 路径只由已审批教案和当前会话推导，不接受调用者传入路径或命令。
        command = ['/usr/bin/open', *(['-R'] if body.target == 'folder' else []), location['entry']]
        try:
            opened = await asyncio.to_thread(subprocess.run, command, capture_output=True,
                                            text=True, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise AppError('LOCAL_OPEN_FAILED', '未能打开，请使用显示的保存路径手动打开；文件已保留。', 503) from None
        if opened.returncode:
            raise AppError('LOCAL_OPEN_FAILED', '未能打开，请使用显示的保存路径手动打开；文件已保留。', 503)
        return result(request, {'opened': body.target, **location})
