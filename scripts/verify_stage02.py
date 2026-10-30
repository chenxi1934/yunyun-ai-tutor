"""阶段02验收：真实HTTP服务、真实百炼工具往返与进程重启；不打开浏览器。"""
import argparse
import hashlib
import os
import platform
import re
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from app.config import PROJECT_ROOT, Settings
from app.domain import dumps, now, sha, uid
from app.storage import Store


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def launch(command, env, url, log):
    process = subprocess.Popen(command, cwd=PROJECT_ROOT, env=env, stdout=log, stderr=log,
                               start_new_session=True)
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("服务进程提前退出，请检查验收日志。")
        try:
            if httpx.get(url, timeout=1).status_code == 200:
                return process
        except httpx.RequestError:
            pass
        time.sleep(.1)
    os.killpg(process.pid, signal.SIGTERM)
    process.wait(timeout=10)
    raise RuntimeError("服务启动超时。")


def stop(process, hard=False):
    if process and process.poll() is None:
        os.killpg(process.pid, signal.SIGKILL if hard else signal.SIGTERM)
        process.wait(timeout=10)


def frontend(client):
    page = client.get("/")
    require(page.status_code == 200 and '<html lang="zh-CN">' in page.text, "前端HTML不可用。")
    assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', page.text)
    require(len(assets) >= 2, "前端没有构建后的JS/CSS入口。")
    evidence = []
    for path in assets:
        response = client.get(path)
        require(response.status_code == 200 and response.content, "静态资源不可用：" + path)
        evidence.append({"path": path, "http": response.status_code,
                         "sha256": hashlib.sha256(response.content).hexdigest()})
    return {"html_http": 200, "assets": evidence}


def wait_run(client, sid, rid):
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        snapshot = client.get(f"/api/sessions/{sid}").json()
        run = next(r for r in snapshot["runs"] if r["id"] == rid)
        if run["status"] in {"COMPLETED", "FAILED", "STOPPED", "WAITING_APPROVAL", "INTERRUPTED"}:
            return snapshot, run
        time.sleep(.15)
    raise RuntimeError("真实模型任务等待超时，不能判定通过。")


def send(client, sid, text, revision):
    response = client.post(f"/api/sessions/{sid}/messages", json={"content": text,
                           "expected_revision": revision, "idempotency_key": uid()})
    response.raise_for_status()
    return response.json()["run_id"]


def verify_mode(settings, mode, evidence_dir, identity, startup_only=False):
    result = {"mode": mode, "mock": False, "checks": {}, "started_at": now()}
    process = None
    sid = None
    with tempfile.TemporaryDirectory(prefix="yunyun-stage02-acceptance-") as temporary:
        teacher = Path(temporary) / "teacher"
        teacher.mkdir()
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        capability = secrets.token_urlsafe(32)
        env = {**os.environ, "LLM_PROVIDER": "bailian", "YUNYUN_MODE": mode,
               "YUNYUN_WORKSPACE": str(teacher), "YUNYUN_LOCAL_TOKEN": capability,
               "YUNYUN_DATA_DIR": str(settings.yunyun_data_dir.resolve())}
        command = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                   "--port", str(port), "--no-access-log"]
        log_path = evidence_dir / f"stage02-acceptance-{mode}-{identity}.log"
        with log_path.open("w") as log, httpx.Client(base_url=base, timeout=10,
                                                   headers={"Authorization": "Bearer " + capability}) as client:
            try:
                process = launch(command, env, base + "/api/health", log)
                result["backend_pid"] = process.pid
                result["frontend"] = frontend(client)
                runtime = client.get("/api/runtime").json()
                require(runtime["provider"] == "bailian" and runtime["mock"] is False, "禁止用Mock完成验收。")
                result["runtime"] = runtime
                result["checks"]["1"] = "PASS"
                if startup_only:
                    result["status"] = "PASS"
                    return result
                require(runtime["key_configured"], "真实模型密钥未配置。")
                client.post("/api/client", json={}).raise_for_status()
                response = client.post("/api/sessions", json={"topic": "阶段02真实HTTP验收"})
                response.raise_for_status()
                session = response.json()["session"]
                sid, wid = session["id"], session["workspace_id"]
                store = Store(settings.yunyun_data_dir / "state.sqlite3")
                workspace = Path(store.get("workspaces", wid)["root"])
                store.close()
                marker, phrase = "MARKER-" + uid(), "PHRASE-" + uid()
                fixture = f"合成验收数据\n随机标记：{marker}\n随机短语：{phrase}\n"
                (workspace / "fixture.md").write_text(fixture, encoding="utf-8")
                outside = workspace.parent / f"outside-{identity}.md"
                outside.write_text("outside-workspace-sentinel", encoding="utf-8")
                (workspace / "linked.md").symlink_to(outside)
                os.link(outside, workspace / "hard.md")
                (workspace / "bad.md").write_bytes(b"\xff")
                result["path_checks"] = []
                for path in ["../" + outside.name, str(outside), "folder\\file.md", ".env", "linked.md", "hard.md"]:
                    denied = client.get(f"/api/workspaces/{wid}/file", params={"path": path})
                    require(denied.status_code == 403 and denied.json()["error"]["code"] == "PATH_DENIED",
                            "工作区边界没有拒绝路径：" + path)
                    require("outside-workspace-sentinel" not in denied.text, "越界文件内容泄露。")
                    result["path_checks"].append({"path": path, "http": 403, "code": "PATH_DENIED"})
                result["checks"]["6"] = "PASS"
                bad = client.get(f"/api/workspaces/{wid}/file", params={"path": "bad.md"})
                require(bad.status_code == 422 and bad.json()["error"]["code"] == "ENCODING_ERROR", "读取异常未明确报错。")
                result["file_error"] = {"http": bad.status_code, "error": bad.json()["error"]}
                rid = send(client, sid, "请先列举工作区，再真实读取 fixture.md。"
                           "根据文件中两个随机字段为 notes.md 提出草稿，完整保留随机标记和随机短语。"
                           "不要请求正式变更，不要运行代码。最终回复也原样复述这两个字段。", 0)
                before, run = wait_run(client, sid, rid)
                require(run["status"] == "COMPLETED", "真实模型首轮未完成：" + dumps(run.get("error")))
                calls = before["tool_calls"]
                names = [c["name"] for c in calls]
                require(all(name in names for name in ["list_files", "read_file", "propose_patch"]), "缺少必要原生工具调用。")
                read_calls = [c for c in calls if c["name"] == "read_file" and c["result"]["ok"]
                              and c["result"]["data"].get("path") == "fixture.md"]
                require(read_calls and read_calls[0]["result"]["data"]["hash"] == sha(fixture), "工具未真实读取当前fixture。")
                call_id = read_calls[0]["id"]
                messages = before["messages"]
                tool_index = next(i for i, m in enumerate(messages) if m.get("tool_call_id") == call_id)
                require(marker in messages[tool_index]["content"] and phrase in messages[tool_index]["content"], "tool消息没有真实结果。")
                continuations = [c for m in messages[tool_index + 1:] if m["role"] == "assistant"
                                 for c in m.get("tool_calls", []) if c["function"]["name"] == "propose_patch"]
                require(any(marker in c["function"]["arguments"] and phrase in c["function"]["arguments"]
                            for c in continuations), "模型没有根据回传结果提出后续草稿。")
                require(marker in messages[-1]["content"] and phrase in messages[-1]["content"], "最终回复没有使用真实工具结果。")
                require(before["drafts"] and marker in before["drafts"][-1]["content"], "草稿未持久化。")
                require(not (workspace / "notes.md").exists(), "未经审批已改正式文件。")
                result["checks"].update({"2": "PASS", "3": "PASS", "4": "PASS", "5": "PASS"})
                result["fixture_hash"] = sha(fixture)
                result["read_call_id"] = call_id
                result["first_turn"] = before
                rid = send(client, sid, "请为上一轮 notes.md 的最新草稿调用 request_publish 请求正式变更，"
                           "不要再生成草稿。教师若拒绝，只确认拒绝、正式文件未改变并复述此前的随机标记和短语，"
                           "不再次请求发布。", before["session"]["revision"])
                paused, run = wait_run(client, sid, rid)
                require(run["status"] == "WAITING_APPROVAL" and paused["approvals"], "未在真实审批检查点暂停。")
                original_pid = process.pid
                stop(process, hard=True)
                process = launch(command, env, base + "/api/health", log)
                restored = client.get(f"/api/sessions/{sid}").json()
                for key in ["session", "messages", "runs", "tool_calls", "drafts", "approvals", "usage"]:
                    require(restored[key] == paused[key], "服务重启未完整恢复：" + key)
                result["restart"] = {"previous_pid": original_pid, "new_pid": process.pid,
                                     "restored_fields": ["session", "messages", "runs", "tool_calls", "drafts", "approvals", "usage"]}
                aid = restored["approvals"][-1]["id"]
                refused = client.post(f"/api/approvals/{aid}/decision", json={"decision": "approve", "expected_revision": restored["session"]["revision"]})
                require(refused.status_code == 409 and refused.json()["error"]["code"] == "PUBLISH_NOT_READY", "阶段02不应允许正式发布。")
                client.post(f"/api/approvals/{aid}/decision", json={"decision": "reject", "expected_revision": restored["session"]["revision"]}).raise_for_status()
                rejected = client.get(f"/api/sessions/{sid}").json()
                client.post(f"/api/sessions/{sid}/resume", json={"expected_revision": rejected["session"]["revision"]}).raise_for_status()
                final, run = wait_run(client, sid, rid)
                require(run["status"] == "COMPLETED", "拒绝后真实模型未恢复完成：" + dumps(run.get("error")))
                require(marker in final["messages"][-1]["content"] and phrase in final["messages"][-1]["content"], "重启后模型未保持上下文。")
                require(len(final["drafts"]) == len(before["drafts"]) and not (workspace / "notes.md").exists(), "恢复产生重复草稿或正式写入。")
                tool_ids = [m["tool_call_id"] for m in final["messages"] if m["role"] == "tool"]
                require(len(tool_ids) == len(set(tool_ids)) == len(final["tool_calls"]), "工具结果丢失或被重复回填。")
                result["checks"]["7"] = "PASS"
                result["final_snapshot"] = final
                result["estimated_and_reserved_cny"] = sum((u["cny"] or 0) for u in final["usage"])
                result["sse_http"] = client.get(f"/api/sessions/{sid}/events?follow=false").status_code
                result["status"] = "PASS"
            except Exception as error:
                result["status"], result["error"] = "FAIL", str(error)
                if sid and process and process.poll() is None:
                    snapshot = client.get(f"/api/sessions/{sid}").json()
                    result["failure_snapshot"] = snapshot
                    if snapshot.get("runs"):
                        client.post(f"/api/runs/{snapshot['runs'][-1]['id']}/cancel", json={})
            finally:
                stop(process)
    result["finished_at"] = now()
    return result


def verify_provider_failure(settings, evidence_dir, identity):
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    # 端口保持绑定且不listen，真实httpx连接必然失败；不启动伪模型服务。
    with socket.socket() as closed, (evidence_dir / f"stage02-acceptance-failure-{identity}.log").open("w") as log:
        closed.bind(("127.0.0.1", 0))
        env = {**os.environ, "LLM_PROVIDER": "bailian", "YUNYUN_MODE": "web",
               "YUNYUN_DATA_DIR": str(settings.yunyun_data_dir.resolve()),
               "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost",
               "DASHSCOPE_BASE_URL": f"http://127.0.0.1:{closed.getsockname()[1]}/compatible-mode/v1"}
        command = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"]
        process = launch(command, env, base + "/api/health", log)
        try:
            with httpx.Client(base_url=base, timeout=10) as client:
                client.post("/api/client", json={}).raise_for_status()
                session = client.post("/api/sessions", json={"topic": "阶段02连接失败验收"}).json()["session"]
                rid = send(client, session["id"], "检查模型连接失败是否明确返回错误。", 0)
                snapshot, run = wait_run(client, session["id"], rid)
                require(run["status"] == "FAILED" and run["error"]["code"] == "PROVIDER_UNAVAILABLE",
                        "模型断连没有按预期报错：" + dumps({"status": run["status"], "error": run["error"]}))
                require(snapshot["session"]["mock"] is False and not snapshot["tool_calls"], "失败后发生Mock降级或伪工具执行。")
                return {"status": "PASS", "mock": False, "fault": "real_connection_refused", "snapshot": snapshot}
        finally:
            stop(process)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--startup-only", action="store_true", help="只验容器内真实服务/静态资源，无需密钥、不调用模型")
    args = parser.parse_args()
    settings = Settings()
    if not args.startup_only:
        require(settings.llm_provider == "bailian" and settings.dashscope_api_key.get_secret_value(), "必须配置真实百炼Provider及Key。")
    evidence_dir = Path(os.environ.get("YUNYUN_EVIDENCE_DIR", PROJECT_ROOT / ".runtime"))
    evidence_dir.mkdir(parents=True, exist_ok=True)
    identity = uid()[:12]
    store = Store(settings.yunyun_data_dir / "state.sqlite3")
    require(not any(r["status"] in {"READY", "RUNNING", "WAITING_APPROVAL", "INTERRUPTED"} for r in store.find("runs")), "现有实例有未结束任务，停止验收以免影响既有会话。")
    store.close()
    report = {"started_at": now(), "mock": False, "browser_tested": False,
              "python": platform.python_version(), "platform": platform.system() + " " + platform.machine(), "modes": []}
    for mode in (["web"] if args.startup_only else ["pc", "web"]):
        result = verify_mode(settings, mode, evidence_dir, identity, args.startup_only)
        report["modes"].append(result)
        if not args.startup_only:
            print(dumps({"mode": mode, "status": result["status"], "checks": result["checks"], "error": result.get("error")}), flush=True)
        # 后续探针失败也保留此前已完成的真实验收，避免只剩终端输出。
        location = evidence_dir / f"stage02-acceptance-{identity}.json"
        partial = dumps(report)
        if settings.dashscope_api_key.get_secret_value():
            partial = partial.replace(settings.dashscope_api_key.get_secret_value(), "[REDACTED]")
        location.write_text(partial, encoding="utf-8")
        if result["status"] != "PASS":
            break
    if not args.startup_only and all(r["status"] == "PASS" for r in report["modes"]):
        try:
            report["failure_check"] = verify_provider_failure(settings, evidence_dir, identity)
        except Exception as error:
            report["failure_check"] = {"status": "FAIL", "error": str(error)}
    passed = all(r["status"] == "PASS" for r in report["modes"])
    passed = passed and (args.startup_only or report.get("failure_check", {}).get("status") == "PASS")
    report["status"] = "PASS" if passed else "FAIL"
    report["finished_at"] = now()
    location = evidence_dir / f"stage02-acceptance-{identity}.json"
    serialized = dumps(report)
    key = settings.dashscope_api_key.get_secret_value()
    if key:
        serialized = serialized.replace(key, "[REDACTED]")
    location.write_text(serialized, encoding="utf-8")
    if args.startup_only:
        print(serialized)
    else:
        print(dumps({"status": report["status"], "evidence": str(location), "mock": False}), flush=True)
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
