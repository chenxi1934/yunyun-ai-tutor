import asyncio
import threading
import time
from dataclasses import replace

import pytest
from app import tools
from app.workspaces import Workspace
from conftest import ScriptedProvider, reply


async def test_slow_read_uses_declared_timeout_and_keeps_heartbeat_responsive(setup_agent, monkeypatch, record_property):
    real_read = Workspace.read
    finished = threading.Event()

    def slow_read(self, *args, **kwargs):
        try:
            time.sleep(5.1)
            return real_read(self, *args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(Workspace, "read", slow_read)
    provider = ScriptedProvider(reply(("read_file", {"path": "fixture.md"})), reply(content="不应继续。"))
    agent, store, session, _ = setup_agent(provider)
    run = agent.new_run(session["id"], "读取文件", 0, "request-0001")
    heartbeat = []
    started = time.monotonic()

    async def beat():
        await asyncio.sleep(.01)
        heartbeat.append(time.monotonic() - started)

    await asyncio.gather(agent.run(run["id"]), beat())
    record_property("tool_terminal_seconds", time.monotonic() - started)
    record_property("heartbeat_seconds", heartbeat[0])
    state = store.get("runs", run["id"])
    call = store.find("calls", session["id"])[0]
    assert state["status"] == "FAILED" and state["error"]["code"] == "TOOL_TIMEOUT"
    assert not call["result"]["ok"] and call["result"]["error"]["code"] == "TOOL_TIMEOUT"
    assert heartbeat[0] < .5
    assert await asyncio.to_thread(finished.wait, 1)
    assert store.get("calls", call["id"]) == call, "迟到的读取成功结果不得替换超时结果。"
    assert len(provider.requests) == 1


async def test_file_preparation_keeps_its_own_timeout(setup_agent, monkeypatch):
    real_read = Workspace.read
    release, finished = threading.Event(), threading.Event()

    def slow_read(self, *args, **kwargs):
        try:
            release.wait(2)
            return real_read(self, *args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(Workspace, "read", slow_read)
    agent, store, session, root = setup_agent(ScriptedProvider(reply(("propose_patch", {
        "path": "late.md", "content": "late draft", "base_hash": None}))))
    monkeypatch.setattr(tools, 'SPECS', tuple(replace(spec, timeout_seconds=.08)
                        if spec.name == 'propose_patch' else spec for spec in tools.SPECS))
    run = agent.new_run(session["id"], "提出草稿", 0, "request-0001")
    started = time.monotonic()
    try:
        await agent.run(run["id"])
        assert time.monotonic() - started < .5
        state = store.get("runs", run["id"])
        assert state["status"] == "FAILED" and state["error"]["code"] == "TOOL_TIMEOUT"
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)
    assert store.find("drafts", session["id"]) == []
    assert not (root / "late.md").exists()


@pytest.mark.parametrize("name", ["propose_patch", "request_publish"])
async def test_tool_timeout_never_commits_late_draft_or_approval(setup_agent, monkeypatch, name):
    provider = ScriptedProvider(reply(("propose_patch", {"path": "late.md", "content": "original draft", "base_hash": None})),
                                reply(content="已保存。"))
    agent, store, session, _ = setup_agent(provider)
    first = agent.new_run(session["id"], "创建原草稿", 0, "request-0001")
    await agent.run(first["id"])
    original_drafts = store.find("drafts", session["id"])
    assert len(original_drafts) == 1
    args = ({"draft_id": original_drafts[0]["id"]} if name == "request_publish" else
            {"path": "late.md", "content": "must not persist", "base_hash": None})
    provider.responses.append(reply((name, args)))
    monkeypatch.setattr(tools, "SPECS", tuple(replace(spec, timeout_seconds=.05)
                        if spec.name == name else spec for spec in tools.SPECS))
    real_read = Workspace.read
    release, finished = threading.Event(), threading.Event()

    def slow_read(self, *args, **kwargs):
        try:
            release.wait(2)
            return real_read(self, *args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(Workspace, "read", slow_read)
    second = agent.new_run(session["id"], "测试超时", 1, "request-0002")
    try:
        await agent.run(second["id"])
        state = store.get("runs", second["id"])
        assert state["status"] == "FAILED" and state["error"]["code"] == "TOOL_TIMEOUT"
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)
    assert store.find("drafts", session["id"]) == original_drafts
    assert store.find("approvals", session["id"]) == []
