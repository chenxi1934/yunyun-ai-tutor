import time

import pytest
from app.api import create_app
from app.config import Settings
from fastapi.testclient import TestClient
from pydantic import SecretStr


@pytest.fixture
def web_app(tmp_path):
    return create_app(Settings(_env_file=None, llm_provider="mock", yunyun_mode="web",
                               yunyun_data_dir=tmp_path / "state"))


def connect(client):
    assert client.post("/api/client", json={}).status_code == 200
    response = client.post("/api/sessions", json={})
    assert response.status_code == 201
    return response.json()["session"]


def test_api_flow_sse_replay_and_idempotency(web_app):
    with TestClient(web_app) as client:
        session = connect(client)
        assert client.get("/api/health").json()["status"] == "ok"
        assert client.get("/api/runtime").json()["mock"] is True
        data = {"content": "读取文件", "expected_revision": 0, "idempotency_key": "request-0001"}
        response = client.post(f'/api/sessions/{session["id"]}/messages', json=data)
        assert response.status_code == 202
        rid = response.json()["run_id"]
        for _ in range(100):
            state = client.get(f'/api/sessions/{session["id"]}').json()
            if state["runs"][-1]["status"] == "COMPLETED":
                break
            time.sleep(.01)
        assert state["runs"][-1]["status"] == "COMPLETED"
        assert state["tool_calls"][-1]["name"] == "read_file"
        assert client.post(f'/api/sessions/{session["id"]}/messages', json=data).json()["run_id"] == rid
        listing = client.get(f'/api/workspaces/{session["workspace_id"]}/files').json()["files"]
        assert len(listing) == 2
        assert client.get(f'/api/workspaces/{session["workspace_id"]}/file', params={"path": "../x.md"}).status_code == 403
        stream = client.get(f'/api/sessions/{session["id"]}/events?after=1&follow=false')
        assert stream.status_code == 200 and "event: agent" in stream.text and "id: 1\n" not in stream.text
        cursor = state["event_cursor"]
        assert client.get(f'/api/sessions/{session["id"]}/events?follow=false', headers={"Last-Event-ID": str(cursor)}).text == ""


def test_web_session_ownership_and_origin(web_app):
    with TestClient(web_app) as one:
        session = connect(one)
        one.cookies.clear()
        one.post("/api/client", json={})
        assert one.get(f'/api/sessions/{session["id"]}').status_code == 404
        assert one.get(f'/api/workspaces/{session["workspace_id"]}/files').status_code == 404
        assert one.post("/api/sessions", json={}, headers={"Origin": "https://evil.example"}).status_code == 403
        assert one.post("/api/sessions", json={"root_path": "/etc"}).status_code == 422


def test_pc_capability_and_host_boundary(tmp_path):
    workspace = tmp_path / "teacher"
    workspace.mkdir()
    app = create_app(Settings(_env_file=None, yunyun_mode="pc", llm_provider="mock",
                             yunyun_workspace=workspace, yunyun_data_dir=tmp_path / "state",
                             yunyun_local_token=SecretStr("test-local-capability")))
    with TestClient(app) as client:
        assert client.post("/api/client", json={}).status_code == 403
        client.headers["Authorization"] = "Bearer test-local-capability"
        session = connect(client)
        assert session["workspace_id"]
        assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400


@pytest.mark.parametrize("finish", ["timeout", "cancel"])
async def test_slow_file_tool_does_not_block_health_or_cancel(tmp_path, monkeypatch, finish, record_property):
    import asyncio
    import threading
    from dataclasses import replace

    import httpx
    from app import tools
    from app.workspaces import Workspace
    from conftest import ScriptedProvider, reply

    real_read = Workspace.read
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    def slow_read(self, *args, **kwargs):
        entered.set()
        try:
            release.wait(2)
            return real_read(self, *args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(Workspace, "read", slow_read)
    if finish == "timeout":
        monkeypatch.setattr(tools, "SPECS", tuple(replace(spec, timeout_seconds=.1)
                            if spec.name == "read_file" else spec for spec in tools.SPECS))
    provider = ScriptedProvider(reply(("read_file", {"path": "README.md"})))
    app = create_app(Settings(_env_file=None, llm_provider="mock", yunyun_mode="web",
                             yunyun_data_dir=tmp_path / "state"), provider)
    async with app.router.lifespan_context(app), httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        await client.post("/api/client", json={})
        session = (await client.post("/api/sessions", json={})).json()["session"]
        started = time.monotonic()
        response = await client.post(f'/api/sessions/{session["id"]}/messages', json={
            "content": "读取工作区", "expected_revision": 0, "idempotency_key": "request-0001"})
        rid = response.json()["run_id"]
        try:
            assert await asyncio.to_thread(entered.wait, .5)
            assert time.monotonic() - started < .5
            before_health = time.monotonic()
            assert (await client.get("/api/health")).status_code == 200
            record_property("health_seconds", time.monotonic() - before_health)
            assert time.monotonic() - before_health < .5
            if finish == "cancel":
                before_cancel = time.monotonic()
                assert (await client.post(f"/api/runs/{rid}/cancel", json={})).status_code == 200
                record_property("cancel_seconds", time.monotonic() - before_cancel)
                assert time.monotonic() - before_cancel < .5
            else:
                await asyncio.wait_for(app.state.tasks[rid], 1)
            snapshot = (await client.get(f'/api/sessions/{session["id"]}')).json()
            expected_status = "STOPPED" if finish == "cancel" else "FAILED"
            expected_error = "USER_CANCELLED" if finish == "cancel" else "TOOL_TIMEOUT"
            assert snapshot["runs"][-1]["status"] == expected_status
            assert snapshot["tool_calls"][0]["result"]["error"]["code"] == expected_error
        finally:
            release.set()
            assert await asyncio.to_thread(finished.wait, 1)
        await asyncio.sleep(.01)
        final = (await client.get(f'/api/sessions/{session["id"]}')).json()
        assert final["tool_calls"] == snapshot["tool_calls"]
        assert not final["drafts"] and not final["approvals"]
        assert len(provider.requests) == 1
