import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def uid() -> str:
    return uuid4().hex


def now() -> str:
    return datetime.now(UTC).isoformat()


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, retryable: bool = False,
                 details: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.status, self.retryable = code, message, status, retryable
        self.details = details

    def payload(self) -> dict:
        value = {"code": self.code, "message": self.message, "retryable": self.retryable}
        if self.details:
            value["details"] = self.details
        return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ListFiles(StrictModel):
    pass


class ReadFile(StrictModel):
    path: str = Field(min_length=1, max_length=300)


class ReadDraft(StrictModel):
    draft_id: str = Field(min_length=1, max_length=64)


class ProposePatch(ReadFile):
    content: str = Field(max_length=65536)
    base_hash: str | None
    operation: Literal["write", "delete"] = "write"


class RunPythonTests(StrictModel):
    draft_id: str = Field(min_length=1, max_length=64)
    test_spec_revision: str = Field(min_length=1, max_length=64)


class RequestPublish(StrictModel):
    draft_id: str = Field(min_length=1, max_length=64)


class ToolCall(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=100)
    arguments: str = Field(max_length=100000)

    def wire(self) -> dict:
        return {"id": self.id, "type": "function", "function": {
            "name": self.name, "arguments": self.arguments}}


class ModelReply(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=24)
    finish_reason: str = "stop"
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    model: str
    request_id: str | None = None

    def message(self) -> dict:
        msg: dict = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = [call.wire() for call in self.tool_calls]
        return msg


class NewSession(StrictModel):
    stage: Literal["初中", "大学"] = "初中"
    grade: str = Field(default="初二", max_length=30)
    topic: str = Field(default="循环结构", max_length=100)


class NewMessage(StrictModel):
    content: str = Field(min_length=1, max_length=12000)
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=100)


class Resume(StrictModel):
    expected_revision: int = Field(ge=0)


class Decision(StrictModel):
    decision: Literal["reject", "approve"]
    expected_revision: int = Field(ge=0)
