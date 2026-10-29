import asyncio
import difflib
from dataclasses import dataclass

from pydantic import ValidationError

from app.domain import (
    AppError,
    GetVerification,
    ListFiles,
    ProposePatch,
    ReadDraft,
    ReadFile,
    RequestPublish,
    RunPythonTests,
    StrictModel,
    dumps,
    now,
    sha,
    uid,
)
from app.education.models import (
    EducationContext,
    ProposeLesson,
    ReadLesson,
    ReviseLessonItem,
    VerifyLesson,
)
from app.storage import Store
from app.verification.service import VerificationService
from app.workspaces import Workspace, is_python_path


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    arguments: type[StrictModel]
    permission: str
    version: str = "1"
    timeout_seconds: int = 5
    allowed_modes: tuple = ("pc", "web")
    idempotency: str = "persisted_call_id"


SPECS = (
    ToolSpec('get_education_context', '读取已导入班情、策略、固定任务契约和完整建议结构。建议不是测试/审核证据。', EducationContext, 'L0'),
    ToolSpec('propose_lesson', '保存完整教案JSON；plan字段严格遵循get_education_context的suggested_plan结构。不能自报验证/审核。', ProposeLesson, 'L1'),
    ToolSpec('read_lesson', '按教案ID读取当前完整结构、逐项审核状态和全部代码验证关联。', ReadLesson, 'L0'),
    ToolSpec('revise_lesson_item', '保持ID修订单个教学项目，replacement为该项目完整对象。旧记录保留，必要验证/审核失效。', ReviseLessonItem, 'L1'),
    ToolSpec('verify_lesson', '真实验证教案中全部示例和参考解，固定测试不可修改，逐项保留失败。', VerifyLesson, 'L2', timeout_seconds=175),
    ToolSpec("list_files", "列出已授权工作区的教学文本文件。", ListFiles, "L0"),
    ToolSpec("read_file", "读取工作区相对路径，返回真实内容和 SHA256。", ReadFile, "L0"),
    ToolSpec("read_draft", "按草稿ID读取当前会话的持久化草稿正文和版本。"
             "续改草稿或历史裁剪后使用本工具；read_file只读取正式文件。", ReadDraft, "L0"),
    ToolSpec("propose_patch", "提出文件完整新内容或删除草稿，base_hash 须匹配实际文件；"
             "base_hash是正式文件Hash，不是草稿content_hash；新建文件未落盘时，首次和续改都用null。"
             "仅保存草稿，不改正式文件。", ProposePatch, "L1"),
    ToolSpec("get_verification", "用于独立代码草稿：读取冻结规格与真实报告，不能改测试。整份教案请用verify_lesson批量验证。",
             GetVerification, "L0"),
    ToolSpec("run_python_tests", "用于独立代码草稿；完整教案使用verify_lesson。真实执行草稿及教师冻结规格，失败返回逐用例日志。"
             "只允许修复代码，不能改测试；最多两次修复。", RunPythonTests, "L2", timeout_seconds=35),
    ToolSpec("request_publish", "为草稿创建正式变更待审批并暂停；此工具不能批准或写入。"
             "正式提交尚未开放。", RequestPublish, "L3"),
)


def schemas() -> list[dict]:
    return [{"type": "function", "function": {"name": s.name, "description": s.description,
             "parameters": s.arguments.model_json_schema()}} for s in SPECS]


class Registry:
    def __init__(self, store: Store, verification: VerificationService | None = None, education=None):
        self.store = store
        self.verification = verification
        self.education = education

    @staticmethod
    def timeout_seconds(name: str) -> float:
        return next((s.timeout_seconds for s in SPECS if s.name == name), 5)

    @staticmethod
    def _arguments(call: dict, session: dict):
        spec = next((s for s in SPECS if s.name == call["name"]), None)
        if not spec:
            raise AppError("TOOL_NOT_ALLOWED", "工具不在白名单内。", 403)
        if session["mode"] not in spec.allowed_modes:
            raise AppError("POLICY_DENIED", "当前模式不能使用该工具。", 403)
        return spec, spec.arguments.model_validate_json(call["arguments"])

    @staticmethod
    def _result(call: dict, data=None, error=None) -> dict:
        result = {"call_id": call["id"], "ok": error is None, "data": data, "error": error,
                  "evidence_ref": "tool_call:" + call["id"]}
        result["content_hash"] = sha(dumps(result))
        return result

    def error_result(self, call: dict, error: AppError | ValidationError) -> dict:
        payload = (error.payload() if isinstance(error, AppError) else
                   {"code": "INVALID_TOOL_ARGUMENTS", "message": "工具参数不符合协议。",
                    "retryable": False})
        return self._result(call, error=payload)

    @staticmethod
    def _diff(path: str, original: str, content: str) -> str:
        return "".join(difflib.unified_diff(original.splitlines(keepends=True),
                       content.splitlines(keepends=True), fromfile=path, tofile=path + "（草稿）"))

    def begin(self, call, session):
        if call["name"] != "run_python_tests" or not self.verification:
            return
        try:
            _, args = self._arguments(call, session)
            draft = self.verification.draft(session["id"], args.draft_id)
        except (AppError, ValidationError):
            return
        self.verification.invalidate(session["id"], draft["path"])
        draft["verification_status"], draft["status"] = "NOT_TESTED", "DRAFT"
        self.store.put("drafts", draft)
        self.store.event(session["id"], call["run_id"], "verification.started",
                         {"draft_id": draft["id"]})

    async def prepare_async(self, call, session, workspace):
        try:
            spec, args = self._arguments(call, session)
            if spec.name == 'verify_lesson':
                return {'education_verified': await self.education.verify(session['id'], args.lesson_id, args.expected_revision)}
            if spec.name in {"run_python_tests", "get_verification", "request_publish", "read_lesson"} and self.verification:
                if spec.name == "run_python_tests":
                    return {"report": await self.verification.prepare(
                        session["id"], args.draft_id, args.test_spec_revision)}
                try:
                    identity = await self.verification.runner.identity()
                except AppError:
                    identity = None
                # 只读准备，状态刷新在主循环提交阶段进行。
                prepared = await asyncio.to_thread(self.prepare, call, session, workspace)
                prepared["runner_identity"] = identity
                return prepared
            return await asyncio.to_thread(self.prepare, call, session, workspace)
        except (AppError, ValidationError) as error:
            return {"error_result": self.error_result(call, error)}

    def prepare(self, call: dict, session: dict, workspace: Workspace) -> dict:
        """后台只读准备；不写草稿/审批/事件，超时或取消后可安全丢弃结果。"""
        try:
            spec, args = self._arguments(call, session)
            if spec.name == "list_files":
                return {"files": workspace.list_files()}
            if spec.name == "read_file":
                return {"file": workspace.read(args.path)}
            if spec.name == "propose_patch":
                original = workspace.read(args.path, allow_missing=True)
                return {"file": original, "diff": self._diff(args.path, original["content"], args.content)}
            if spec.name == "request_publish":
                draft = self._draft(args.draft_id, session["id"])
                return {"file": workspace.read(draft["path"], allow_missing=True)}
            return {}
        except (ValidationError, AppError) as error:
            return {"error_result": self.error_result(call, error)}

    def execute(self, call: dict, session: dict, workspace: Workspace, *, prepared=None) -> dict:
        if prepared is not None and "error_result" in prepared:
            return prepared["error_result"]
        try:
            spec, args = self._arguments(call, session)
            data = self._handle(spec.name, args, call, session, workspace, prepared)
            return self._result(call, data=data)
        except (ValidationError, AppError) as error:
            if call['name'] in {'propose_lesson', 'revise_lesson_item', 'verify_lesson'}:
                self.store.put('education_attempts', {'id': uid(), 'session_id': session['id'],
                    'call_id': call['id'], 'run_id': call['run_id'], 'tool': call['name'],
                    'arguments': call['arguments'], 'error': self.error_result(call, error)['error'], 'created_at': now()})
            return self.error_result(call, error)

    def _draft(self, draft_id: str, sid: str) -> dict:
        draft = self.store.get("drafts", draft_id)
        if draft["session_id"] != sid:
            raise AppError("NOT_FOUND", "草稿不存在或不属于当前会话。", 404)
        return draft

    def _handle(self, name, args, call: dict, session: dict, ws: Workspace, prepared=None) -> dict:
        sid, rid = session["id"], call["run_id"]
        if self.verification and prepared and "runner_identity" in prepared:
            self.verification.refresh(sid, prepared["runner_identity"])
        if name == 'get_education_context':
            return self.education.context(sid)
        if name == 'propose_lesson':
            return self.education.tool_result(self.education.propose(session, args.plan, args.profile_id,
                args.profile_revision, args.base_revision, rid))
        if name == 'read_lesson':
            return self.education.view(sid, args.lesson_id)
        if name == 'revise_lesson_item':
            return self.education.tool_result(self.education.revise(session, args.lesson_id, args, rid))
        if name == 'verify_lesson':
            if not prepared or 'education_verified' not in prepared:
                raise AppError('RUNNER_UNAVAILABLE', '教案尚未真实验证。', 503)
            return self.education.tool_result(prepared['education_verified'])
        if name == "get_verification":
            draft = self.verification.draft(sid, args.draft_id)
            spec = self.verification.latest_spec(sid, draft["path"])
            return {"draft_id": draft["id"], "verification_status": draft["verification_status"],
                    "test_spec": spec, "reports": [r for r in self.store.find("reports", sid)
                                                    if r["draft_id"] == draft["id"]]}

        if name == "list_files":
            return prepared if prepared is not None else {"files": ws.list_files()}
        if name == "read_file":
            return prepared["file"] if prepared is not None else ws.read(args.path)
        if name == "read_draft":
            draft = self._draft(args.draft_id, sid)
            return {"draft_id": draft["id"], **{key: draft[key] for key in (
                "path", "content", "content_hash", "base_hash", "revision", "parent_id",
                "operation", "status", "verification_status", "mock")}}
        if name == "propose_patch":
            if any(args.path == self.store.get('drafts', did)['path']
                   for lesson in self.store.find('lessons', sid) for did in lesson['bindings'].values()):
                raise AppError('EDUCATION_ITEM_REQUIRED', '教案关联代码须用revise_lesson_item修订，保留结构与验证绑定。', 409)
            original = prepared["file"] if prepared is not None else ws.read(args.path, allow_missing=True)
            if original["hash"] != args.base_hash:
                raise AppError("REVISION_CONFLICT", "文件已变化，请重新读取后提出草稿。", 409)
            if len(args.content.encode("utf-8")) > 65536:
                raise AppError("FILE_TOO_LARGE", "草稿超过 64 KiB 上限。", 413)
            if args.operation == "delete" and (original["hash"] is None or args.content):
                raise AppError("INVALID_DELETE", "删除草稿须指向现有文件且内容为空。", 422)
            existing = [d for d in self.store.find("drafts", sid) if d["path"] == args.path]
            draft = {"id": uid(), "session_id": sid, "run_id": rid, "call_id": call["id"],
                     "path": args.path, "base_hash": args.base_hash, "content": args.content,
                     "content_hash": sha(args.content), "operation": args.operation,
                     "revision": len(existing) + 1,
                     "parent_id": existing[-1]["id"] if existing else None,
                     "status": "DRAFT", "verification_status": "NOT_TESTED",
                     "mock": session["mock"], "created_at": now(),
                     "diff": prepared["diff"] if prepared is not None else self._diff(
                         args.path, original["content"], args.content)}
            if self.verification:
                self.verification.repair_guard(sid, args.path, draft["content_hash"])
                self.verification.invalidate(sid, args.path)
            draft["repair_diff"] = self._diff(args.path, existing[-1]["content"], args.content) if existing and is_python_path(args.path) else None
            self.store.put("drafts", draft)
            self.store.event(sid, rid, "artifact.revised", {"draft_id": draft["id"],
                             "path": draft["path"], "revision": draft["revision"],
                             "status": "DRAFT", "verification_status": "NOT_TESTED"})
            return {"draft_id": draft["id"], "path": draft["path"], "diff": draft["diff"],
                    "content_hash": draft["content_hash"], "status": "DRAFT",
                    "verification_status": "NOT_TESTED", "formal_file_changed": False}
        if name == "run_python_tests":
            if not self.verification or not prepared or "report" not in prepared:
                raise AppError("RUNNER_UNAVAILABLE", "NOT_TESTED：隔离执行器不可用。", 503)
            return self.verification.commit(prepared["report"])
        if name == "request_publish":
            draft = self._draft(args.draft_id, sid)
            lessons = self.store.find('lessons', sid)
            if lessons and not self.education.view(sid, lessons[-1]['lesson_id'])['delivery_ready']:
                raise AppError('EDUCATION_REVIEW_REQUIRED', '教育产物须完成代码验证和教师逐项审核。', 409)
            current = prepared["file"] if prepared is not None else ws.read(draft["path"], allow_missing=True)
            if current["hash"] != draft["base_hash"]:
                raise AppError("REVISION_CONFLICT", "正式文件已变化，需重新生成草稿。", 409)
            latest = [d for d in self.store.find("drafts", sid) if d["path"] == draft["path"]][-1]
            if latest["id"] != draft["id"]:
                raise AppError("STALE_DRAFT", "已有新草稿，请审核最新版本。", 409)
            if any(is_python_path(d["path"]) for d in self.store.find("drafts", sid)):
                self.verification.delivery_candidates(sid)
                if is_python_path(draft["path"]) and not self.verification.current_pass(draft):
                    raise AppError("VERIFICATION_REQUIRED", "代码尚未通过当前规格，不能审核交付。", 409)
            approval = {"id": uid(), "session_id": sid, "run_id": rid, "call_id": call["id"],
                        "draft_id": draft["id"], "status": "PENDING", "created_at": now(),
                        "content_hash": draft["content_hash"], "base_hash": draft["base_hash"]}
            self.store.put("approvals", approval)
            self.store.event(sid, rid, "approval.requested", approval)
            return {"status": "WAITING_APPROVAL", "approval_id": approval["id"],
                    "formal_file_changed": False}
        raise AppError("TOOL_NOT_ALLOWED", "工具不在白名单内。", 403)
