import json

import pytest
from app.domain import AppError, sha
from conftest import ScriptedProvider, reply


async def test_native_calls_real_files_and_result_returned_to_model(setup_agent):
    def after_read(messages):
        tools = [m for m in messages if m["role"] == "tool"]
        result = json.loads(tools[-1]["content"])
        assert "unit-42" in result["data"]["content"]
        calls = messages[-3]["tool_calls"]
        assert [m["tool_call_id"] for m in tools] == [c["id"] for c in calls]
        return reply(("propose_patch", {"path": "notes.md", "content": "依据 unit-42 的草稿", "base_hash": None}))

    provider = ScriptedProvider(reply(("list_files", {}), ("read_file", {"path": "fixture.md"})),
                                after_read, reply(content="根据 unit-42 已保存草稿；代码未测试。"))
    agent, store, session, workspace = setup_agent(provider)
    run = agent.new_run(session["id"], "读取班情并提出草稿", 0, "request-0001")
    await agent.run(run["id"])
    assert store.get("runs", run["id"])["status"] == "COMPLETED"
    assert len(store.find("calls", session["id"])) == 3
    drafts = store.find("drafts", session["id"])
    assert drafts[0]["content_hash"] == sha("依据 unit-42 的草稿")
    assert not (workspace / "notes.md").exists()
    assert len(store.find("usage", session["id"])) == 3
    agent.new_run(session["id"], "继续，记住上轮班情", 1, "request-0002")
    assert "unit-42" in str(agent.context(session))


async def test_unknown_tool_and_bad_arguments_return_to_model(setup_agent):
    provider = ScriptedProvider(reply(("shell", {"command": "ls"}),
                                      ("read_file", {"path": "fixture.md", "approved": True})),
                                reply(content="操作被权限策略拒绝。"))
    agent, store, session, _ = setup_agent(provider)
    run = agent.new_run(session["id"], "尝试工具", 0, "request-0001")
    await agent.run(run["id"])
    results = [json.loads(m["content"]) for m in provider.requests[-1] if m["role"] == "tool"]
    assert [r["error"]["code"] for r in results] == ["TOOL_NOT_ALLOWED", "INVALID_TOOL_ARGUMENTS"]
    assert store.get("runs", run["id"])["status"] == "COMPLETED"


async def test_runner_unavailable_never_fakes_pass(setup_agent):
    def test_draft(messages):
        draft = json.loads(messages[-1]["content"])["data"]["draft_id"]
        return reply(("run_python_tests", {"draft_id": draft, "test_spec_revision": "test-v1"}))

    provider = ScriptedProvider(reply(("propose_patch", {"path": "sum.py", "content": "print(1)", "base_hash": None})),
                                test_draft, reply(content="执行器不可用，尚未测试。"))
    agent, store, session, _ = setup_agent(provider)
    run = agent.new_run(session["id"], "验证代码", 0, "request-0001")
    await agent.run(run["id"])
    calls = store.find("calls", session["id"])
    assert calls[-1]["result"]["error"]["code"] == "RUNNER_UNAVAILABLE"
    assert store.find("drafts", session["id"])[0]["verification_status"] == "NOT_TESTED"


@pytest.mark.parametrize('steps,calls_per_step', [(13, 1), (1, 25)])
async def test_model_and_tool_counts_do_not_limit_progress(setup_agent, steps, calls_per_step):
    responses = [reply(*[("propose_patch", {"path": "notes.md", "content": f'{i}-{j}',
                         "base_hash": None}) for j in range(calls_per_step)]) for i in range(steps)]
    provider = ScriptedProvider(*responses, reply(content='已完成。'))
    agent, store, session, _ = setup_agent(provider)
    run = agent.new_run(session["id"], "读取文件", 0, "request-0001")
    await agent.run(run["id"])
    value = store.get("runs", run["id"])
    assert value["status"] == "COMPLETED"
    assert value['steps'] == steps + 1 and value['tool_count'] == steps * calls_per_step
    assert all(c["status"] == "DONE" for c in store.find("calls", session["id"]))


@pytest.mark.parametrize('scope', ['run', 'session', 'project', 'legacy_unknown'])
async def test_historical_usage_never_blocks_request(setup_agent, scope):
    provider = ScriptedProvider(reply(content="正常执行"))
    agent, store, session, _ = setup_agent(provider, llm_provider="bailian")
    run = agent.new_run(session["id"], "请求", 0, "request-0001")
    historical = {'id': 'history', 'session_id': session['id'] if scope != 'project' else 'other',
                  'run_id': run['id'] if scope == 'run' else 'other', 'input_tokens': 10**9,
                  'output_tokens': 10**9, 'cny': 10**9,
                  'status': 'RESERVED_UNKNOWN' if scope == 'legacy_unknown' else 'USAGE_ESTIMATE'}
    store.put('usage', historical)
    await agent.run(run["id"])
    assert store.get("runs", run["id"])["status"] == "COMPLETED"
    assert len(provider.requests) == 1 and store.get('usage', 'history') == historical


async def test_unknown_usage_is_not_reset_on_resume(setup_agent):
    provider = ScriptedProvider(AppError("PROVIDER_AUTH", "鉴权失败", 503), reply(content="恢复完成"))
    agent, store, session, _ = setup_agent(provider, llm_provider="bailian")
    run = agent.new_run(session["id"], "请求", 0, "request-0001")
    await agent.run(run["id"])
    unknown = store.find("usage")[0]
    assert unknown["status"] == "USAGE_UNKNOWN" and unknown["cny"] is None
    assert unknown['input_tokens'] == unknown['output_tokens'] == 0
    restored = agent.prepare_resume(session["id"], 1)
    await agent.run(restored["id"])
    assert store.get("runs", run["id"])["steps"] == 2
    assert store.find("usage")[0] == unknown


async def test_repeated_no_progress_and_retry_limits(setup_agent):
    provider = ScriptedProvider(*[reply(("read_file", {"path": "../denied.md"})) for _ in range(3)])
    agent, store, session, _ = setup_agent(provider)
    run = agent.new_run(session["id"], "测试", 0, "request-0001")
    await agent.run(run["id"])
    assert store.get("runs", run["id"])["error"]["code"] == "NO_PROGRESS"


async def test_provider_error_not_silently_mocked(setup_agent):
    provider = ScriptedProvider(*[AppError("PROVIDER_RATE_LIMIT", "限流", 503, True) for _ in range(3)])
    agent, store, session, _ = setup_agent(provider)
    run = agent.new_run(session["id"], "请求", 0, "request-0001")
    await agent.run(run["id"])
    assert len(provider.requests) == 3
    assert store.get("runs", run["id"])["status"] == "FAILED"
    assert store.get("runs", run["id"])["error"]["code"] == "PROVIDER_RATE_LIMIT"
    assert not [m for m in store.messages(session["id"]) if m["role"] == "assistant"]


async def test_idempotent_messages_and_single_active_run(setup_agent):
    agent, store, session, _ = setup_agent(ScriptedProvider())
    one = agent.new_run(session["id"], "请求", 0, "request-0001")
    assert agent.new_run(session["id"], "请求", 0, "request-0001")["id"] == one["id"]
    with pytest.raises(AppError, match="同一请求标识"):
        agent.new_run(session["id"], "另一请求", 1, "request-0001")
    with pytest.raises(AppError, match="当前任务"):
        agent.new_run(session["id"], "请求2", 1, "request-0002")
    assert len(store.messages(session["id"])) == 1


async def test_single_request_timeout_remains_an_execution_error(setup_agent):
    import asyncio

    class SlowProvider:
        async def complete(self, messages, tools):
            await asyncio.sleep(1)

    agent, store, session, _ = setup_agent(SlowProvider(), model_timeout_seconds=.02)
    run = agent.new_run(session["id"], "请求", 0, "request-0001")
    await agent.run(run["id"])
    assert store.get("runs", run["id"])["status"] == "FAILED"
    assert store.get("runs", run["id"])["error"]["code"] == "PROVIDER_TIMEOUT"
    assert len(store.find("usage")) == 3
    assert all(u['status'] == 'USAGE_UNKNOWN' and u['cny'] is None for u in store.find('usage'))


async def test_repeating_same_draft_hash_stops_despite_new_ids(setup_agent):
    provider = ScriptedProvider(*[reply(("propose_patch", {"path": "repeated.md", "content": "same", "base_hash": None}))
                                  for _ in range(3)])
    agent, store, session, root = setup_agent(provider)
    run = agent.new_run(session["id"], "请求", 0, "request-0001")
    await agent.run(run["id"])
    assert store.get("runs", run["id"])["error"]["code"] == "NO_PROGRESS"
    assert len(store.find("drafts")) == 3 and not (root / "repeated.md").exists()


async def test_cancel_resolves_unfinished_tool_batch(setup_agent):
    def publish(messages):
        draft_id = json.loads(messages[-1]["content"])["data"]["draft_id"]
        return reply(("request_publish", {"draft_id": draft_id}), ("list_files", {}))

    provider = ScriptedProvider(reply(("propose_patch", {"path": "new.md", "content": "draft", "base_hash": None})), publish)
    agent, store, session, root = setup_agent(provider)
    run = agent.new_run(session["id"], "请求", 0, "request-0001")
    await agent.run(run["id"])
    agent.stop(run["id"], "STOPPED", {"code": "USER_CANCELLED", "message": "教师取消。"})
    assert all(c["status"] == "DONE" for c in store.find("calls"))
    assert store.find("approvals")[0]["status"] == "CANCELLED"
    assert not (root / "new.md").exists()
    assert len([m for m in store.messages(session["id"]) if m["role"] == "tool"]) == 3


async def test_other_session_usage_does_not_block_new_session(setup_agent):
    provider = ScriptedProvider(reply(content="第一轮"), reply(content="第二轮"))
    agent, store, session, _ = setup_agent(provider, llm_provider="bailian")
    with store.tx():
        store.put("usage", {"id": "existing", "session_id": "other", "run_id": "other",
                            "input_tokens": 10**9, "output_tokens": 10**9, "cny": 10**9})
    run = agent.new_run(session["id"], "请求", 0, "request-0001")
    await agent.run(run["id"])
    second = agent.create_session('owner', session['context'])
    another = agent.new_run(second['id'], '新会话', 0, 'request-0002')
    await agent.run(another['id'])
    assert len(provider.requests) == 2
    assert store.get("runs", run["id"])["status"] == 'COMPLETED'
    assert store.get("runs", another['id'])["status"] == 'COMPLETED'


async def test_large_actual_usage_does_not_block_tool_execution(setup_agent):
    excessive = reply(("propose_patch", {"path": "new.md", "content": "draft", "base_hash": None}))
    excessive.output_tokens = 12001
    excessive.input_tokens = 1000000
    agent, store, session, _ = setup_agent(ScriptedProvider(excessive, reply(content='已保存草稿。')),
                                          llm_provider='bailian')
    run = agent.new_run(session["id"], "请求", 0, "request-0001")
    await agent.run(run["id"])
    assert store.get("runs", run["id"])["status"] == 'COMPLETED'
    assert len(store.find("drafts")) == 1
    assert store.find("usage")[0]["output_tokens"] == 12001


async def test_unpriced_model_records_unknown_cost_without_blocking(setup_agent):
    agent, store, session, _ = setup_agent(ScriptedProvider(reply(content='完成。')),
                                          llm_provider='bailian', llm_model='unpriced-model')
    run = agent.new_run(session['id'], '请求', 0, 'unpriced-model')
    await agent.run(run['id'])
    assert store.get('runs', run['id'])['status'] == 'COMPLETED'
    assert store.find('usage')[0]['cny'] is None


async def test_model_claims_are_not_tool_or_verification_evidence(setup_agent):
    agent, store, session, _ = setup_agent(ScriptedProvider(reply(content="已读取、已测试，PASS。")))
    run = agent.new_run(session["id"], "检查示例", 0, "request-0001")
    await agent.run(run["id"])
    assert store.find("calls") == [] and store.find("drafts") == []
    event = [e for e in store.events(session["id"]) if e["type"] == "run.completed"][-1]
    assert event["payload"]["delivery_status"] == "DRAFT_ONLY"
