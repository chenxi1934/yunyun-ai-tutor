import pytest
from app.agent import Agent
from app.config import Settings
from app.domain import ModelReply, ToolCall, dumps, uid
from app.storage import Store


def reply(*calls: tuple[str, dict], content: str | None = None) -> ModelReply:
    return ModelReply(content=content, tool_calls=[ToolCall(id=uid(), name=n, arguments=dumps(a))
                                                  for n, a in calls],
                      finish_reason="tool_calls" if calls else "stop",
                      input_tokens=100, output_tokens=20, model="TEST_MOCK")


class ScriptedProvider:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    async def complete(self, messages, tools):
        self.requests.append(messages)
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        if callable(value):
            value = value(messages)
        return value


@pytest.fixture
def setup_agent(tmp_path):
    workspace = tmp_path / "teacher"
    workspace.mkdir()
    (workspace / "fixture.md").write_text("班情：5未交，3死循环，交集未知。随机标记：unit-42", encoding="utf-8")
    settings = Settings(_env_file=None, yunyun_mode="pc", yunyun_workspace=workspace,
                        yunyun_data_dir=tmp_path / "state", llm_provider="mock")
    stores = []

    def create(provider, **overrides):
        configured = settings.model_copy(update=overrides)
        store = Store(configured.yunyun_data_dir / "state.sqlite3")
        stores.append(store)
        agent = Agent(configured, store, provider)
        session = agent.create_session("owner", {"stage": "初中", "grade": "初二", "topic": "循环结构"})
        return agent, store, session, workspace

    yield create
    for store in stores:
        try:
            store.close()
        except Exception:
            pass
