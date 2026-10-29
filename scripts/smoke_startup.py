"""实际启动/停止API进程，验证PC入口、静态前端与Web恢复；不打开浏览器，不消费API。"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from app.agent import Agent
from app.config import PROJECT_ROOT, Settings
from app.domain import ModelReply, ToolCall, dumps, uid
from app.storage import Store


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start(command, env, url, log):
    process = subprocess.Popen(command, cwd=PROJECT_ROOT, env=env, stdout=log, stderr=log)
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("服务启动失败，请查看 .runtime/smoke-startup.log")
        try:
            if httpx.get(url + "/api/health", timeout=1).status_code == 200:
                return process
        except httpx.RequestError:
            pass
        time.sleep(.1)
    process.terminate()
    process.wait(timeout=10)
    raise RuntimeError("服务启动超时")


def stop(process):
    process.terminate()
    process.wait(timeout=10)


class ApprovalProbeProvider:
    """显著测试Mock：控制审批检查点；文件/数据库操作仍真实执行。"""
    async def complete(self, messages, tools, max_tokens):
        result = None
        if messages[-1]["role"] == "tool":
            result = json.loads(messages[-1]["content"])
        if result is None:
            calls = [ToolCall(id=uid(), name="propose_patch", arguments=dumps({
                "path": "probe-note.md", "content": "MOCK_LLM process recovery fixture", "base_hash": None}))]
        else:
            calls = [ToolCall(id=uid(), name="request_publish", arguments=dumps({
                "draft_id": result["data"]["draft_id"]})),
                     ToolCall(id=uid(), name="read_file", arguments=dumps({"path": "README.md"}))]
        return ModelReply(tool_calls=calls, finish_reason="tool_calls", input_tokens=0,
                          output_tokens=0, model="MOCK_LLM")


def main():
    runtime = Path(os.environ.get("YUNYUN_EVIDENCE_DIR", PROJECT_ROOT / ".runtime"))
    runtime.mkdir(exist_ok=True)
    evidence = {"mock": True, "browser_tested": False}
    with tempfile.TemporaryDirectory(prefix="yunyun-startup-") as temporary, (runtime / "smoke-startup.log").open("w") as log:
        root = Path(temporary)
        teacher = root / "teacher"
        teacher.mkdir()
        (teacher / "readme.md").write_text("PC本地真实目录", encoding="utf-8")
        env = {**os.environ, "LLM_PROVIDER": "mock", "YUNYUN_DATA_DIR": str(root / "state")}
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        process = start([sys.executable, "-m", "app.launch", "--workspace", str(teacher),
                         "--no-browser", "--port", str(port)], env, base, log)
        try:
            evidence["pc_health"] = httpx.get(base + "/api/health").json()["status"] == "ok"
            evidence["pc_frontend"] = '<html lang="zh-CN">' in httpx.get(base + "/").text
            evidence["pc_no_token_denied"] = httpx.post(base + "/api/client", json={}).status_code == 403
        finally:
            stop(process)
        env["YUNYUN_MODE"] = "web"
        command = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                   "--port", str(port), "--no-access-log"]
        process = start(command, env, base, log)
        with httpx.Client(base_url=base, timeout=5) as client:
            try:
                client.post("/api/client", json={}).raise_for_status()
                session = client.post("/api/sessions", json={}).json()["session"]
                sid = session["id"]
                evidence["web_frontend"] = '<html lang="zh-CN">' in client.get("/").text
                client.post(f"/api/sessions/{sid}/messages", json={"content": "MOCK_LLM：读取工作区。",
                            "expected_revision": 0, "idempotency_key": uid()}).raise_for_status()
                for _ in range(100):
                    snapshot = client.get(f"/api/sessions/{sid}").json()
                    if snapshot["runs"][-1]["status"] == "COMPLETED":
                        break
                    time.sleep(.05)
                assert snapshot["runs"][-1]["status"] == "COMPLETED"
                evidence["real_file_tools_with_mock_llm"] = len(snapshot["tool_calls"]) == 2
                cookie = client.cookies.get("yunyun_client")
            finally:
                stop(process)
            configured = Settings(_env_file=None, llm_provider="mock", yunyun_mode="web",
                                  yunyun_data_dir=root / "state")
            store = Store(root / "state" / "state.sqlite3")
            agent = Agent(configured, store, ApprovalProbeProvider())
            run = agent.new_run(sid, "MOCK_LLM：恢复审批检查点", 1, uid())
            asyncio.run(agent.run(run["id"]))
            before = {"messages": store.messages(sid), "drafts": store.find("drafts", sid),
                      "approvals": store.find("approvals", sid), "usage": store.find("usage", sid),
                      "workspace": store.get("workspaces", session["workspace_id"])}
            assert store.get("runs", run["id"])["status"] == "WAITING_APPROVAL"
            store.close()
            process = start(command, env, base, log)
            try:
                assert client.cookies.get("yunyun_client") == cookie
                snapshot = client.get(f"/api/sessions/{sid}").json()
                evidence["restart_state_restored"] = all(snapshot[k] == before[k] for k in ["messages", "drafts", "approvals", "usage"])
                aid = snapshot["approvals"][0]["id"]
                response = client.post(f"/api/approvals/{aid}/decision", json={"decision": "reject", "expected_revision": 2})
                response.raise_for_status()
                client.post(f"/api/sessions/{sid}/resume", json={"expected_revision": 3}).raise_for_status()
                for _ in range(100):
                    final = client.get(f"/api/sessions/{sid}").json()
                    if final["runs"][-1]["status"] == "COMPLETED":
                        break
                    time.sleep(.05)
                evidence["resume_without_duplicate_draft"] = len(final["drafts"]) == 1 and final["runs"][-1]["status"] == "COMPLETED"
                evidence["rejected_formal_file_unchanged"] = not (Path(before["workspace"]["root"]) / "probe-note.md").exists()
                stream = client.get(f"/api/sessions/{sid}/events?follow=false")
                evidence["sse_replay"] = stream.status_code == 200 and "event: agent" in stream.text
            finally:
                stop(process)
        env.update(LLM_PROVIDER="bailian", DASHSCOPE_API_KEY="", YUNYUN_DATA_DIR=str(root / "error-state"))
        process = start(command, env, base, log)
        try:
            with httpx.Client(base_url=base, timeout=5) as client:
                client.post("/api/client", json={}).raise_for_status()
                session = client.post("/api/sessions", json={}).json()["session"]
                sid = session["id"]
                client.post(f"/api/sessions/{sid}/messages", json={"content": "缺失密钥故障探针",
                            "expected_revision": 0, "idempotency_key": uid()}).raise_for_status()
                for _ in range(100):
                    state = client.get(f"/api/sessions/{sid}").json()
                    if state["runs"][-1]["status"] == "FAILED":
                        break
                    time.sleep(.05)
                evidence["missing_key_fails_without_mock"] = (state["runs"][-1]["status"] == "FAILED" and
                    state["runs"][-1]["error"]["code"] == "API_KEY_MISSING" and not state["session"]["mock"])
        finally:
            stop(process)
    checks = [value for key, value in evidence.items() if key not in {"mock", "browser_tested"}]
    evidence["status"] = "PASS" if all(checks) else "FAIL"
    (runtime / "smoke-startup.json").write_text(dumps(evidence), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    if evidence["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
