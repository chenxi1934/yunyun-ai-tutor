"""仅在专用可信宿主运行，使用权限 0600 Unix socket；不导入 app.api。"""
import asyncio
import os
import secrets
from contextlib import asynccontextmanager

from app.verification.models import ExecutionRequest
from fastapi import FastAPI, HTTPException, Request

from runner.docker_runner import DockerRunner


def create_manager(runner: DockerRunner, token: str) -> FastAPI:
    if len(token) < 32:
        raise ValueError('Manager 需要至少 32 字符的私有鉴权 token')

    @asynccontextmanager
    async def lifespan(app):
        await runner.startup()
        yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    busy = asyncio.Lock()
    jobs = {}

    @app.middleware('http')
    async def auth(request, call_next):
        from fastapi.responses import JSONResponse
        if not secrets.compare_digest(request.headers.get('authorization', ''), 'Bearer ' + token):
            return JSONResponse({'error': 'RUNNER_AUTH'}, status_code=403)
        if int(request.headers.get('content-length', '0')) > 300000:
            return JSONResponse({'error': 'REQUEST_TOO_LARGE'}, status_code=413)
        return await call_next(request)

    @app.get('/identity')
    async def identity():
        return {**runner.identity(), 'active_jobs': list(jobs)}

    @app.delete('/execute/{job_id}')
    async def cancel(job_id: str):
        task = jobs.get(job_id)
        if task:
            if not task.done() and not task.cancelling():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        return {'cancelled': job_id, 'cleanup_complete': runner.healthy}

    @app.post('/execute')
    async def execute(body: ExecutionRequest, request: Request):
        if busy.locked():
            raise HTTPException(429, 'RUNNER_BUSY')
        async with busy:
            task = asyncio.create_task(runner.execute(body))
            jobs[body.job_id] = task
            try:
                while not task.done():
                    if await request.is_disconnected():
                        if not task.cancelling():
                            task.cancel()
                        raise HTTPException(499, '执行请求已断开')
                    await asyncio.sleep(.05)
                return (await task).model_dump()
            finally:
                if not task.done() and not task.cancelling():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                jobs.pop(body.job_id, None)

    return app


def main():
    import uvicorn
    os.umask(0o177)
    app = create_manager(DockerRunner(os.environ['RUNNER_IMAGE']), os.environ['RUNNER_TOKEN'])
    uvicorn.run(app, uds=os.environ['RUNNER_SOCKET'], access_log=False)


if __name__ == '__main__':
    main()
