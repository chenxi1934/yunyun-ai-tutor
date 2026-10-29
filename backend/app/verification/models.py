"""可信 stdin/stdout 契约；期望值始终留在候选执行环境之外。"""
from typing import Literal

from pydantic import Field, model_validator

from app.domain import StrictModel

Status = Literal['PASS', 'SYNTAX_ERROR', 'ASSERTION_ERROR', 'OUTPUT_MISMATCH',
                 'RUNTIME_ERROR', 'TIMEOUT', 'RESOURCE_LIMIT', 'OUTPUT_LIMIT',
                 'RUNNER_ERROR', 'INTERRUPTED', 'NOT_TESTED', 'STALE']


class TestCase(StrictModel):
    id: str = Field(min_length=1, max_length=64)
    input: str = Field(max_length=8192)
    expected: str = Field(max_length=8192)


class TestSpec(StrictModel):
    id: str
    session_id: str
    path: str
    revision: int = Field(ge=1)
    cases: list[TestCase] = Field(min_length=1, max_length=12)
    source: Literal['teacher', 'baseline']
    created_at: str
    content_hash: str

    @model_validator(mode='after')
    def unique_cases(self):
        if len({c.id for c in self.cases}) != len(self.cases):
            raise ValueError('用例 ID 不能重复')
        return self


class FreezeTests(StrictModel):
    path: str = Field(min_length=1, max_length=300)
    expected_revision: int = Field(ge=0)
    # 固定基准与教师自定义二选一；该接口不注册为 Agent 工具。
    baseline: Literal['sum_1_to_n'] | None = None
    cases: list[TestCase] | None = Field(default=None, min_length=1, max_length=12)

    @model_validator(mode='after')
    def exactly_one_source(self):
        if (self.baseline is None) == (self.cases is None):
            raise ValueError('请选择固定基准或教师测试用例')
        if self.cases and len({c.id for c in self.cases}) != len(self.cases):
            raise ValueError('用例 ID 不能重复')
        return self


class ExecutionRequest(StrictModel):
    job_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    code: str = Field(max_length=65536)
    input: str = Field(max_length=8192)


class ExecutionResult(StrictModel):
    status: Status
    stdout: str = ''
    stderr: str = ''
    exit_code: int | None = None
    duration_ms: float = Field(ge=0)
    error: str | None = None
    evidence: dict
    runtime_digest: str
    runner_policy_hash: str


class CaseResult(TestCase):
    actual: str
    stdout: str
    stderr: str
    exit_code: int | None
    duration_ms: float
    status: Status
    error: str | None
    evidence: dict


class VerificationReport(StrictModel):
    id: str
    session_id: str
    draft_id: str
    path: str
    code_hash: str
    test_spec_revision: str
    test_spec_hash: str
    runtime_digest: str
    runner_policy_hash: str
    fingerprint: str
    status: Status
    cases: list[CaseResult]
    created_at: str
    evidence_ref: str
