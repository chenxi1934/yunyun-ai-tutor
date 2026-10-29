import difflib
from dataclasses import dataclass

from pydantic import ValidationError

from app.domain import (
    AppError,
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
from app.storage import Store
from app.workspaces import Workspace


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
    ToolSpec("list_files", "列出已授权工作区的教学文本文件。", ListFiles, "L0"),
    ToolSpec("read_file", "读取工作区相对路径，返回真实内容和 SHA256。", ReadFile, "L0"),
    ToolSpec("read_draft", "按草稿ID读取当前会话的持久化草稿正文和版本。"
             "续改草稿或历史裁剪后使用本工具；read_file只读取正式文件。", ReadDraft, "L0"),
    ToolSpec("propose_patch", "提出文件完整新内容或删除草稿，base_hash 须匹配实际文件；"
             "新建用 null。仅保存草稿，不改正式文件。", ProposePatch, "L1"),
    ToolSpec("run_python_tests", "请求执行某草稿的固定版本测试。阶段02执行器尚未接通，"
             "会明确返回 NOT_TESTED；禁止自报通过。", RunPythonTests, "L2"),
    ToolSpec("request_publish", "为草稿创建正式变更待审批并暂停；此工具不能批准或写入。"
             "阶段02正式提交尚未开放。", RequestPublish, "L3"),
)


def schemas() -> list[dict]:
    return [{"type": "function", "function": {"name": s.name, "description": s.description,
             "parameters": s.arguments.model_json_schema()}} for s in SPECS]


class Registry:
    def __init__(self, store: Store):
        self.store = store

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
            return self.error_result(call, error)

    def _draft(self, draft_id: str, sid: str) -> dict:
        draft = self.store.get("drafts", draft_id)
        if draft["session_id"] != sid:
            raise AppError("NOT_FOUND", "草稿不存在或不属于当前会话。", 404)
        return draft

    def _handle(self, name, args, call: dict, session: dict, ws: Workspace, prepared=None) -> dict:
        sid, rid = session["id"], call["run_id"]
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
            self.store.put("drafts", draft)
            self.store.event(sid, rid, "artifact.revised", {"draft_id": draft["id"],
                             "path": draft["path"], "revision": draft["revision"],
                             "status": "DRAFT", "verification_status": "NOT_TESTED"})
            return {"draft_id": draft["id"], "path": draft["path"], "diff": draft["diff"],
                    "content_hash": draft["content_hash"], "status": "DRAFT",
                    "verification_status": "NOT_TESTED", "formal_file_changed": False}
        if name == "run_python_tests":
            draft = self._draft(args.draft_id, sid)
            if not draft["path"].endswith(".py") or draft["operation"] != "write":
                raise AppError("NOT_PYTHON_DRAFT", "只能验证 Python 代码草稿。", 422)
            raise AppError("RUNNER_UNAVAILABLE", "NOT_TESTED：隔离执行器将在阶段03接入；"
                           "本次未运行代码，不存在通过报告。", 503)
        if name == "request_publish":
            draft = self._draft(args.draft_id, sid)
            current = prepared["file"] if prepared is not None else ws.read(draft["path"], allow_missing=True)
            if current["hash"] != draft["base_hash"]:
                raise AppError("REVISION_CONFLICT", "正式文件已变化，需重新生成草稿。", 409)
            latest = [d for d in self.store.find("drafts", sid) if d["path"] == draft["path"]][-1]
            if latest["id"] != draft["id"]:
                raise AppError("STALE_DRAFT", "已有新草稿，请审核最新版本。", 409)
            approval = {"id": uid(), "session_id": sid, "run_id": rid, "call_id": call["id"],
                        "draft_id": draft["id"], "status": "PENDING", "created_at": now(),
                        "content_hash": draft["content_hash"], "base_hash": draft["base_hash"]}
            self.store.put("approvals", approval)
            self.store.event(sid, rid, "approval.requested", approval)
            return {"status": "WAITING_APPROVAL", "approval_id": approval["id"],
                    "formal_file_changed": False}
        raise AppError("TOOL_NOT_ALLOWED", "工具不在白名单内。", 403)
