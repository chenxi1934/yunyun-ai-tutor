"""显式调用真实API；只使用随机标记与合成内容，证据存入忽略的 .runtime。"""
import argparse
import asyncio
import json
import tempfile
from pathlib import Path

from app.agent import Agent
from app.config import PROJECT_ROOT, Settings
from app.domain import dumps, now, uid
from app.storage import Store


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["pc", "web"], default="pc")
    parser.add_argument("--resume", help="恢复本工具创建的既有探针会话；不清零预算")
    args = parser.parse_args()
    settings = Settings()
    if settings.llm_provider == "mock":
        raise SystemExit("FAIL：探针拒绝 MOCK_LLM，请配置真实百炼 Provider。")
    if not settings.dashscope_api_key.get_secret_value():
        raise SystemExit("NOT_TESTED：未配置 DASHSCOPE_API_KEY。")
    with tempfile.TemporaryDirectory(prefix="yunyun-provider-") as temporary:
        root = Path(temporary)
        workspace = root / "teacher"
        workspace.mkdir()
        marker = "PROBE-" + uid()
        (workspace / "fixture.md").write_text("合成文件，随机标记：" + marker, encoding="utf-8")
        configured = settings.model_copy(update={"yunyun_mode": args.mode, "yunyun_workspace": workspace})
        # 与应用共用预算账本。重复探针不能通过临时数据库清零项目累计费用。
        store = Store(settings.yunyun_data_dir / "state.sqlite3")
        existing_evidence = PROJECT_ROOT / ".runtime" / "probe-provider.json"
        if existing_evidence.exists():
            historical = json.loads(existing_evidence.read_text())
            with store.tx():
                for usage in historical.get("usage", []):
                    if not any(u["id"] == usage["id"] for u in store.find("usage")):
                        store.put("usage", usage)
        agent = Agent(configured, store)
        if args.resume:
            session = store.get("sessions", args.resume)
            if session["owner"] != "probe" or session["mode"] != args.mode:
                raise SystemExit("只能恢复相同模式下本工具创建的探针会话。")
            workspace = agent.workspace(session).root
            marker = (workspace / "fixture.md").read_text().split("：")[-1]
            run = store.find("runs", session["id"])[0]
            if run["status"] in {"FAILED", "INTERRUPTED"}:
                run = agent.prepare_resume(session["id"], session["revision"])
                await agent.run(run["id"])
        else:
            session = agent.create_session("probe", {"stage": "初中", "grade": "初二", "topic": "工具协议探针"})
            workspace = agent.workspace(session).root
            (workspace / "fixture.md").write_text("合成文件，随机标记：" + marker, encoding="utf-8")
            run = agent.new_run(session["id"], "请先列出工作区文件，再真实读取 fixture.md。"
                            "原样报告文件中的随机标记，并以读取内容为依据为 notes.md 提出草稿，"
                            "草稿中必须保留该标记。不要请求正式发布，不要运行代码。", 0, uid())
            await agent.run(run["id"])
        first = store.get("runs", run["id"])
        messages = store.messages(session["id"])
        read_calls = [c for c in store.find("calls", session["id"]) if c["name"] == "read_file" and c["result"]["ok"]]
        matched = bool(read_calls and marker in dumps(read_calls[0]["result"]))
        drafts = store.find("drafts", session["id"])
        first_ok = (first["status"] == "COMPLETED" and matched and drafts and
                    marker in drafts[-1]["content"] and marker in (messages[-1]["content"] or "")
                    and not (workspace / "notes.md").exists())
        second_ok = False
        if first_ok:
            existing_runs = store.find("runs", session["id"])
            if len(existing_runs) == 1:
                revision = store.get("sessions", session["id"])["revision"]
                second = agent.new_run(session["id"], "继续上一轮：无需再读取文件，请原样复述刚才读到的随机标记，"
                                       "并说明草稿是否已经写入正式文件。", revision, uid())
                await agent.run(second["id"])
            else:
                second = existing_runs[-1]
            second_ok = (store.get("runs", second["id"])["status"] == "COMPLETED" and
                         marker in store.messages(session["id"])[-1]["content"])
        report = {"timestamp": now(), "mode": args.mode, "provider": settings.llm_provider,
                  "model": settings.llm_model, "mock": False, "first_turn_ok": bool(first_ok),
                  "second_turn_ok": second_ok, "formal_file_unchanged": not (workspace / "notes.md").exists(),
                  "messages": store.messages(session["id"]), "tool_calls": store.find("calls", session["id"]),
                  "runs": store.find("runs", session["id"]), "usage": store.find("usage", session["id"])}
        report["events"] = store.events(session["id"])
        report["recovered_errors"] = [e["payload"] for e in report["events"] if e["type"] == "model.failed"]
        location = PROJECT_ROOT / ".runtime" / f"probe-provider-{args.mode}.json"
        location.parent.mkdir(exist_ok=True)
        # 此文件只含合成数据；仍做密钥精确脱敏，不输出原始HTTP body。
        content = dumps(report).replace(settings.dashscope_api_key.get_secret_value(), "[REDACTED]")
        location.write_text(content, encoding="utf-8")
        summary = {"status": "PASS" if first_ok and second_ok else "FAIL",
                   "provider": settings.llm_provider, "model": settings.llm_model,
                   "first_turn_ok": bool(first_ok), "second_turn_ok": second_ok,
                   "tool_names": [c["name"] for c in store.find("calls", session["id"])],
                   "estimated_cny": sum(u["cny"] for u in store.find("usage", session["id"])),
                   "errors": [r["error"] for r in store.find("runs", session["id"]) if r["error"]],
                   "recovered_errors": report["recovered_errors"],
                   "evidence": str(location)}
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        store.close()
        if summary["status"] != "PASS":
            raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
