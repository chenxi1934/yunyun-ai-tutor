import asyncio
import secrets
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.agent import Agent
from app.config import PROJECT_ROOT, Settings
from app.delivery_api import register_delivery
from app.demo_gateway import register_demo_gateway
from app.domain import AppError, Decision, NewMessage, NewSession, Resume, dumps, sha, uid
from app.education.api import register_education
from app.providers import Provider
from app.storage import Store
from app.verification.models import FreezeTests
from app.workspaces import is_python_path


def create_app(settings: Settings | None = None, provider: Provider | None = None) -> FastAPI:
    settings = settings or Settings()
    if settings.yunyun_mode == "pc" and not settings.yunyun_local_token.get_secret_value():
        raise ValueError("PC模式须通过启动入口生成本机能力口令。")
    store = Store(settings.yunyun_data_dir / "state.sqlite3")
    agent = Agent(settings, store, provider)
    tasks: dict[str, asyncio.Task] = {}
    execution_lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app):
        store.recover()
        agent.delivery.recover()
        yield
        for task in tasks.values():
            task.cancel()
        await asyncio.gather(*tasks.values(), return_exceptions=True)
        store.close()

    app = FastAPI(title="耘耘AI助教", version="0.2.0", lifespan=lifespan)
    app.state.store, app.state.agent, app.state.tasks = store, agent, tasks
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.yunyun_hosts.split(","))

    def failure(error: AppError, request_id: str):
        return JSONResponse({"request_id": request_id, "error": error.payload()},
                            status_code=error.status)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        request.state.request_id = uid()
        if request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD"}:
            origin = request.headers.get("origin")
            if origin and urlsplit(origin).netloc != request.headers.get("host"):
                return failure(AppError("ORIGIN_DENIED", "拒绝跨站操作。", 403), request.state.request_id)
            if settings.yunyun_mode == "pc":
                expected = "Bearer " + settings.yunyun_local_token.get_secret_value()
                if not secrets.compare_digest(request.headers.get("authorization", ""), expected):
                    return failure(AppError("LOCAL_AUTH_REQUIRED", "请从本机启动入口打开工作台。", 403),
                                   request.state.request_id)
            try:
                size = int(request.headers.get("content-length", "0"))
            except ValueError:
                size = 999999
            if request.url.path.endswith('/class-profiles/upload'):
                limit = 1048576
            else:
                limit = 1052672 if '/class-profiles' in request.url.path else 262144
            if size > limit:
                return failure(AppError("REQUEST_TOO_LARGE", "请求内容过大。", 413), request.state.request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(AppError)
    async def app_error(request: Request, error: AppError):
        return failure(error, request.state.request_id)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        return failure(AppError("INVALID_REQUEST", "请求字段不符合协议，请检查输入。", 422),
                       request.state.request_id)

    def owner(request: Request) -> str:
        cookie = request.cookies.get("yunyun_client", "")
        if len(cookie) != 64 or any(c not in "0123456789abcdef" for c in cookie):
            raise AppError("SESSION_REQUIRED", "请先连接工作台。", 401)
        return sha(cookie)

    def session(request: Request, sid: str) -> dict:
        value = store.get("sessions", sid)
        if value["owner"] != owner(request):
            raise AppError("NOT_FOUND", "资源不存在或不属于当前会话。", 404)
        return value

    def resource(request: Request, table: str, identity: str) -> dict:
        value = store.get(table, identity)
        session(request, value["session_id"])
        return value

    def result(request: Request, data: dict) -> dict:
        return {"request_id": request.state.request_id, **data}

    def schedule(run: dict):
        rid = run["id"]
        async def execute():
            async with execution_lock:
                await agent.run(rid)

        if run["status"] == "READY" and (rid not in tasks or tasks[rid].done()):
            tasks[rid] = asyncio.create_task(execute())

    register_education(app, agent, session, result, execution_lock)
    register_delivery(app, agent, session, result, execution_lock)
    register_demo_gateway(app, agent, execution_lock)

    @app.get("/api/health")
    async def health(request: Request):
        return result(request, {"status": "ok", "version": "0.2.0"})

    async def runner_identity():
        try:
            return await agent.verification.runner.identity()
        except AppError:
            return None

    @app.get("/api/runtime")
    async def runtime(request: Request):
        identity = await runner_identity()
        remote = settings.yunyun_mode == 'pc' and bool(settings.desktop_gateway_url)
        return result(request, {"mode": settings.yunyun_mode, "provider": settings.llm_provider,
                                "model": (identity or {}).get('model', settings.llm_model) if remote else
                                         "MOCK_LLM" if settings.llm_provider == "mock" else settings.llm_model,
                                "mock": (identity or {}).get('mock', False) if remote else settings.llm_provider == "mock",
                                "key_configured": (identity or {}).get('model_ready', False) if remote else bool(settings.dashscope_api_key.get_secret_value()),
                                "runner": "ISOLATED" if identity else "UNAVAILABLE", "publish": "AVAILABLE", "workspace_name": settings.yunyun_workspace.name if settings.yunyun_workspace else None})

    @app.post("/api/client")
    async def client(request: Request):
        token = request.cookies.get("yunyun_client", "")
        if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
            token = secrets.token_hex(32)
        response = JSONResponse(result(request, {"connected": True}))
        response.set_cookie("yunyun_client", token, httponly=True, samesite="strict",
                            secure=settings.yunyun_secure_cookie, max_age=604800)
        return response

    @app.get("/api/sessions")
    async def list_sessions(request: Request):
        identity = owner(request)
        values = [{k: v for k, v in s.items() if k != "owner"}
                  for s in store.find("sessions") if s["owner"] == identity]
        return result(request, {"sessions": values})

    @app.post("/api/sessions", status_code=201)
    async def new_session(request: Request, body: NewSession):
        value = agent.create_session(owner(request), body.model_dump())
        return result(request, {"session": {k: v for k, v in value.items() if k != "owner"}})

    @app.get("/api/sessions/{sid}")
    async def snapshot(request: Request, sid: str):
        value = session(request, sid)
        identity = await runner_identity()
        with store.tx():
            agent.verification.refresh(sid, identity)
        return result(request, {"session": {k: v for k, v in value.items() if k != "owner"},
                                "messages": store.messages(sid), "runs": store.find("runs", sid),
                                "tool_calls": store.find("calls", sid),
                                "drafts": store.find("drafts", sid),
                                "approvals": store.find("approvals", sid),
                                "commits": store.find("commits", sid),
                                "profiles": agent.education.profiles(sid),
                                "lessons": [agent.education.view(sid, lid) for lid in dict.fromkeys(r["lesson_id"] for r in store.find("lessons", sid))],
                                "workspace_name": "示例教学工作区" if value["mode"] == "web" else agent.workspace(value).root.name,
                                "test_specs": store.find("test_specs", sid),
                                "verification_reports": [{**r, "effective_status": agent.verification.report_status(r, identity)}
                                                         for r in store.find("reports", sid)],
                                "usage": store.find("usage", sid),
                                "event_cursor": store.cursor(sid)})

    @app.post("/api/sessions/{sid}/test-specs", status_code=201)
    async def freeze_tests(request: Request, sid: str, body: FreezeTests):
        value = session(request, sid)
        # 使用同一工作区路径策略，测试规格永不由模型工具写入。
        agent.workspace(value).parts(body.path)
        if not is_python_path(body.path):
            raise AppError("NOT_PYTHON_DRAFT", "测试规格只能绑定 Python 文件。", 422)
        with store.tx():
            current = store.get("sessions", sid)
            if current["revision"] != body.expected_revision:
                raise AppError("REVISION_CONFLICT", "会话已更新，请刷新。", 409)
            if any(r["status"] in {"READY", "RUNNING", "WAITING_APPROVAL"} for r in store.find("runs", sid)):
                raise AppError("RUN_ACTIVE", "请先停止当前任务，再冻结新的测试规格。", 409)
            spec = agent.verification.freeze(sid, body.path, body.cases, body.baseline)
            current["revision"] += 1
            store.put("sessions", current)
        return result(request, {"test_spec": spec})

    @app.get("/api/verification-reports/{report_id}")
    async def verification_report(request: Request, report_id: str):
        report = resource(request, "reports", report_id)
        identity = await runner_identity()
        with store.tx():
            agent.verification.refresh(report["session_id"], identity)
        effective = agent.verification.report_status(report, identity)
        return result(request, {"report": report, "effective_status": effective})

    @app.get("/api/workspaces/{wid}/files")
    async def files(request: Request, wid: str):
        ws = resource(request, "workspaces", wid)
        value = session(request, ws["session_id"])
        return result(request, {"files": agent.workspace(value).list_files()})

    @app.get("/api/workspaces/{wid}/file")
    async def read_file(request: Request, wid: str, path: str):
        ws = resource(request, "workspaces", wid)
        value = session(request, ws["session_id"])
        return result(request, agent.workspace(value).read(path))

    @app.post("/api/sessions/{sid}/messages", status_code=202)
    async def message(request: Request, sid: str, body: NewMessage):
        session(request, sid)
        run = agent.new_run(sid, body.content, body.expected_revision, body.idempotency_key)
        schedule(run)
        return result(request, {"run_id": run["id"]})

    @app.post("/api/sessions/{sid}/resume", status_code=202)
    async def resume(request: Request, sid: str, body: Resume):
        session(request, sid)
        run = agent.prepare_resume(sid, body.expected_revision)
        schedule(run)
        return result(request, {"run_id": run["id"]})

    @app.post("/api/runs/{rid}/cancel")
    async def cancel(request: Request, rid: str):
        resource(request, "runs", rid)
        agent.stop(rid, "STOPPED", {"code": "USER_CANCELLED", "message": "教师已停止任务。"})
        if rid in tasks:
            tasks[rid].cancel()
        return result(request, {"status": "STOPPED"})

    @app.post("/api/approvals/{aid}/decision")
    async def decide(request: Request, aid: str, body: Decision):
        approval = resource(request, "approvals", aid)
        try:
            identity = await agent.verification.runner.identity()
        except AppError:
            identity = None
        with store.tx():
            agent.verification.refresh(approval['session_id'], identity)
        approval = agent.reject(aid, body.expected_revision, body.decision == "approve")
        return result(request, {"status": approval['status'], "formal_file_changed": approval['status'] == 'COMMITTED'})

    @app.get("/api/sessions/{sid}/events")
    async def events(request: Request, sid: str, after: int = 0, follow: bool = True):
        session(request, sid)
        try:
            cursor = max(0, after, int(request.headers.get("last-event-id", "0")))
        except ValueError:
            raise AppError("INVALID_CURSOR", "事件游标必须是整数。", 422) from None

        async def stream():
            nonlocal cursor
            heartbeat = 0
            while True:
                batch = store.events(sid, cursor)
                for event in batch:
                    cursor = event["event_id"]
                    yield f"id: {cursor}\nevent: agent\ndata: {dumps(event)}\n\n"
                if not follow or await request.is_disconnected():
                    return
                heartbeat += 1
                if heartbeat >= 50:
                    yield ": heartbeat\n\n"
                    heartbeat = 0
                await asyncio.sleep(0.2)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"X-Accel-Buffering": "no"})

    dist = PROJECT_ROOT / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app
