import asyncio
import json

import pytest
from app.agent import Agent
from app.domain import AppError
from app.storage import Store
from conftest import ScriptedProvider, reply


async def test_restart_restores_approval_draft_pending_calls_and_usage(setup_agent):
    def publish(messages):
        draft_id = json.loads(messages[-1]["content"])["data"]["draft_id"]
        return reply(("request_publish", {"draft_id": draft_id}), ("read_file", {"path": "fixture.md"}))

    provider = ScriptedProvider(reply(("propose_patch", {"path": "new.md", "content": "draft", "base_hash": None})), publish)
    agent, store, session, root = setup_agent(provider)
    run = agent.new_run(session["id"], "提出正式变更", 0, "request-0001")
    await agent.run(run["id"])
    before_run = store.get("runs", run["id"])
    before_usage = store.find("usage")
    assert before_run["status"] == "WAITING_APPROVAL"
    assert [c["status"] for c in store.find("calls")] == ["DONE", "WAITING", "PENDING"]
    reopened = Store(agent.settings.yunyun_data_dir / "state.sqlite3")
    try:
        reopened.recover()
        restored = Agent(agent.settings, reopened, ScriptedProvider(reply(content="已拒绝，读取结果可用。")))
        assert reopened.get("workspaces", session["workspace_id"])["root"] == str(root)
        assert reopened.get("runs", run["id"])["status"] == "WAITING_APPROVAL"
        approval = reopened.find("approvals")[0]
        # 阶段05已开放明确批准；本例仍验证拒绝后的恢复且不发生写入。
        restored.reject(approval["id"], 1)
        restored.prepare_resume(session["id"], 2)
        await restored.run(run["id"])
        assert reopened.get("runs", run["id"])["status"] == "COMPLETED"
        assert len(reopened.find("drafts")) == 1
        assert len(reopened.find("approvals")) == 1
        assert reopened.find("usage")[:len(before_usage)] == before_usage
        assert reopened.get("runs", run["id"])["tool_count"] == 3
        assert not (root / "new.md").exists()
        messages = reopened.messages(session["id"])
        wire = [m for m in messages if m["role"] == "tool"]
        assert len(wire) == len({m["tool_call_id"] for m in wire}) == 3
    finally:
        reopened.close()


async def test_interruption_after_draft_does_not_replay_write(setup_agent):
    blocked = asyncio.Event()

    class Interruptible:
        count = 0

        async def complete(self, messages, tools, max_tokens):
            self.count += 1
            if self.count == 1:
                return reply(("propose_patch", {"path": "new.md", "content": "draft", "base_hash": None}))
            blocked.set()
            await asyncio.Event().wait()

    agent, store, session, root = setup_agent(Interruptible())
    run = agent.new_run(session["id"], "保存草稿", 0, "request-0001")
    task = asyncio.create_task(agent.run(run["id"]))
    await asyncio.wait_for(blocked.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert store.get("runs", run["id"])["status"] == "INTERRUPTED"
    usage_before = store.find("usage")
    second = Agent(agent.settings, store, ScriptedProvider(reply(content="已继续")))
    second.prepare_resume(session["id"], 1)
    await second.run(run["id"])
    assert len(store.find("drafts")) == 1
    assert store.get("runs", run["id"])["steps"] == 3
    assert store.find("usage")[:2] == usage_before
    assert not (root / "new.md").exists()


def test_crashed_running_marked_interrupted_with_budget_retained(setup_agent):
    agent, store, session, _ = setup_agent(ScriptedProvider())
    run = agent.new_run(session["id"], "请求", 0, "request-0001")
    with store.tx():
        run.update(status="RUNNING", steps=2, tool_count=1, active_seconds=60)
        store.put("runs", run)
    store.recover()
    restored = store.get("runs", run["id"])
    assert restored["status"] == "INTERRUPTED"
    assert restored["active_seconds"] == 60 and restored["steps"] == 2


def test_crash_before_worker_starts_is_resumable(setup_agent):
    agent, store, session, _ = setup_agent(ScriptedProvider())
    run = agent.new_run(session["id"], "请求", 0, "request-0001")
    store.recover()
    assert store.get("runs", run["id"])["status"] == "INTERRUPTED"
    assert agent.prepare_resume(session["id"], 1)["id"] == run["id"]


async def test_resume_rejects_policy_or_limit_change(setup_agent):
    agent, store, session, _ = setup_agent(ScriptedProvider(AppError("PROVIDER_AUTH", "无权", 503)))
    run = agent.new_run(session["id"], "请求", 0, "request-0001")
    await agent.run(run["id"])
    changed = Agent(agent.settings.model_copy(update={"max_steps": 11}), store, ScriptedProvider())
    with pytest.raises(AppError) as error:
        changed.prepare_resume(session["id"], 1)
    assert error.value.code == "CONFIG_CHANGED"


@pytest.mark.parametrize("mode", ["pc", "web"])
async def test_compacted_history_restart_can_read_and_revise_full_draft(setup_agent, mode):
    from app.domain import dumps, uid

    marker = "draft-body-" + uid()
    original = marker + "\n" + "x" * 20000
    agent, store, session, _ = setup_agent(ScriptedProvider(
        reply(("propose_patch", {"path": "long.md", "content": original, "base_hash": None})),
        reply(content="草稿已保存。")), yunyun_mode=mode)
    first = agent.new_run(session["id"], "创建长草稿", 0, "request-0001")
    await agent.run(first["id"])
    assert store.get("runs", first["id"])["status"] == "COMPLETED"
    assert len(dumps(store.messages(session["id"])).encode()) > 36000
    draft = store.find("drafts", session["id"])[0]
    store.close()

    reopened = Store(agent.settings.yunyun_data_dir / "state.sqlite3")
    try:
        reopened.recover()

        def retrieve(messages):
            assert marker not in dumps(messages), "此用例须确实进入裁剪后的上下文。"
            index = next(m for m in messages if m["content"] and m["content"].startswith("历史索引"))
            indexed = json.loads(index["content"].split("：", 1)[1])["drafts"][-1]
            assert indexed["draft_id"] == draft["id"]
            return reply(("read_draft", {"draft_id": indexed["draft_id"]}))

        revised = original + "\n教师要求的追加说明。"

        def revise(messages):
            result = json.loads(messages[-1]["content"])
            assert result["ok"] is True
            assert result["data"]["content"] == original
            assert result["data"]["base_hash"] is None
            return reply(("propose_patch", {"path": "long.md", "content": revised, "base_hash": None}))

        provider = ScriptedProvider(retrieve, revise, reply(content="已保留原稿并追加说明。"))
        restored = Agent(agent.settings, reopened, provider)
        second = restored.new_run(session["id"], "保留原稿继续修改，只追加说明。", 1, "request-0002")
        await restored.run(second["id"])
        assert reopened.get("runs", second["id"])["status"] == "COMPLETED"
        latest = reopened.find("drafts", session["id"])[-1]
        assert latest["content"] == revised and latest["parent_id"] == draft["id"]
        assert not (restored.workspace(session).root / "long.md").exists()
    finally:
        reopened.close()


async def test_restart_after_durable_commit_finishes_tool_once_without_rewriting(setup_agent):
    def publish(messages):
        did = json.loads(messages[-1]['content'])['data']['draft_id']
        return reply(('request_publish', {'draft_id': did}))
    agent, store, session, root = setup_agent(ScriptedProvider(
        reply(('propose_patch', {'path': 'committed.md', 'content': '正式内容', 'base_hash': None})), publish))
    run = agent.new_run(session['id'], '生成待审草稿', 0, 'commit-crash-0001')
    await agent.run(run['id'])
    approval = agent.delivery.hydrate(store.get('sessions', session['id']), store.find('approvals')[0])
    # 注入崩溃窗口：文件/提交日志已持久化，但工具结果尚未回填。
    agent.delivery.commit(session, approval)
    before = (root / 'committed.md').stat().st_mtime_ns
    reopened = Store(agent.settings.yunyun_data_dir / 'state.sqlite3')
    try:
        restored = Agent(agent.settings, reopened, ScriptedProvider())
        reopened.recover()
        restored.delivery.recover()
        restored.delivery.recover()
        assert reopened.get('runs', run['id'])['status'] == 'INTERRUPTED'
        assert reopened.get('calls', approval['call_id'])['status'] == 'DONE'
        wires = [m for m in reopened.messages(session['id']) if m.get('tool_call_id') == approval['call_id']]
        assert len(wires) == 1
        assert len(reopened.find('commits')) == 1
        assert (root / 'committed.md').stat().st_mtime_ns == before
    finally:
        reopened.close()
