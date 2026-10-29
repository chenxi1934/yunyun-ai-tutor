from contextlib import contextmanager

from fastapi import Request

from app.domain import AppError, dumps
from app.education.models import (
    ImportProfile,
    LessonRevision,
    ProposeLesson,
    ReviewItem,
    ReviseItem,
)


def register_education(app, agent, session, result, execution_lock):
    store, education = agent.store, agent.education

    @contextmanager
    def mutation(request, sid, expected_revision=None):
        with store.tx():
            value = session(request, sid)
            if execution_lock.locked() or any(r['status'] in {'READY', 'RUNNING', 'WAITING_APPROVAL'}
                                             for r in store.find('runs', sid)):
                raise AppError('RUN_ACTIVE', '请先等待验证完成或停止当前任务。', 409)
            if expected_revision is not None and value['revision'] != expected_revision:
                raise AppError('REVISION_CONFLICT', '会话已变化，请刷新。', 409)
            yield value
            value['revision'] += 1
            store.put('sessions', value)

    async def refresh(sid):
        try:
            identity = await agent.verification.runner.identity()
        except AppError:
            identity = None
        with store.tx():
            agent.verification.refresh(sid, identity)

    @app.post('/api/sessions/{sid}/class-profiles', status_code=201)
    async def import_profile(request: Request, sid: str, body: ImportProfile):
        with mutation(request, sid, body.expected_revision) as value:
            profile = education.import_profile(value, body.content, body.format)
        return result(request, {'profile': profile})

    @app.post('/api/sessions/{sid}/class-profiles/upload', status_code=201)
    async def upload_profile(request: Request, sid: str, format: str, expected_revision: int):
        session(request, sid)
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > 1048576:
                raise AppError('REQUEST_TOO_LARGE', '上传上限为1 MiB。', 413)
        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise AppError('ENCODING_ERROR', '班情文件须为UTF-8。', 422) from None
        if format not in {'json', 'csv'}:
            raise AppError('INVALID_CLASS_DATA', '文件上传支持JSON或CSV。', 422)
        with mutation(request, sid, expected_revision) as value:
            profile = education.import_profile(value, text, format)
        return result(request, {'profile': profile})

    @app.get('/api/sessions/{sid}/education-context')
    async def context(request: Request, sid: str):
        session(request, sid)
        return result(request, education.context(sid))

    @app.post('/api/sessions/{sid}/lessons', status_code=201)
    async def propose(request: Request, sid: str, body: ProposeLesson):
        with mutation(request, sid) as value:
            view = education.propose(value, body.plan, body.profile_id, body.profile_revision, body.base_revision)
        return result(request, {'lesson': view})

    @app.get('/api/sessions/{sid}/lessons/{lid}')
    async def read(request: Request, sid: str, lid: str):
        session(request, sid)
        await refresh(sid)
        return result(request, {'lesson': education.view(sid, lid),
            'history': [r for r in store.find('lessons', sid) if r['lesson_id'] == lid],
            'reviews': [r for r in store.find('education_reviews', sid) if r['lesson_id'] == lid],
            'attempts': [r for r in store.find('education_attempts', sid) if r.get('lesson_id') == lid]})

    @app.patch('/api/sessions/{sid}/lessons/{lid}/items')
    async def revise(request: Request, sid: str, lid: str, body: ReviseItem):
        with mutation(request, sid) as value:
            view = education.revise(value, lid, body)
        return result(request, {'lesson': view})

    @app.post('/api/sessions/{sid}/lessons/{lid}/reviews')
    async def review(request: Request, sid: str, lid: str, body: ReviewItem):
        session(request, sid)
        await refresh(sid)
        with mutation(request, sid) as value:
            view = education.review(value, lid, body)
        return result(request, {'lesson': view})

    @app.post('/api/sessions/{sid}/lessons/{lid}/verify')
    async def verify(request: Request, sid: str, lid: str, body: LessonRevision):
        with mutation(request, sid):
            education.expect(education.latest(sid, lid), body.expected_revision)
        async with execution_lock:
            await refresh(sid)
            view = await education.verify(sid, lid, body.expected_revision)
        return result(request, {'lesson': view})

    @app.get('/api/sessions/{sid}/lessons/{lid}/export')
    async def export(request: Request, sid: str, lid: str):
        session(request, sid)
        await refresh(sid)
        return result(request, education.export(sid, lid))

    @app.get('/api/sessions/{sid}/lessons/{lid}/json')
    async def json_document(request: Request, sid: str, lid: str):
        from fastapi.responses import Response
        session(request, sid)
        await refresh(sid)
        return Response(dumps(education.view(sid, lid)), media_type='application/json',
                        headers={'Content-Disposition': 'attachment; filename="lesson-draft.json"'})
