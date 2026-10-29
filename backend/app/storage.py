import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from app.domain import AppError, dumps, now, uid


class Store:
    tables = {"sessions", "workspaces", "runs", "calls", "drafts", "approvals", "usage", "test_specs", "reports", "repairs",
              "class_profiles", "lessons", "education_reviews", "education_attempts", "commits"}

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=5000")
        for table in sorted(self.tables):
            self.db.execute(f"CREATE TABLE IF NOT EXISTS {table} "
                            "(id TEXT PRIMARY KEY, session_id TEXT NOT NULL, data TEXT NOT NULL)")
            self.db.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_session "
                            f"ON {table}(session_id)")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
                run_id TEXT, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
                session_id TEXT NOT NULL, event_id INTEGER NOT NULL, data TEXT NOT NULL,
                PRIMARY KEY(session_id, event_id));
        """)

    @contextmanager
    def tx(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def put(self, table: str, data: dict):
        assert table in self.tables
        self.db.execute(f"INSERT INTO {table}(id,session_id,data) VALUES(?,?,?) "
                        "ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                        (data["id"], data.get("session_id", data["id"]), dumps(data)))

    def get(self, table: str, identity: str) -> dict:
        assert table in self.tables
        with self.lock:
            row = self.db.execute(f"SELECT data FROM {table} WHERE id=?", (identity,)).fetchone()
        if not row:
            raise AppError("NOT_FOUND", "资源不存在或不属于当前会话。", 404)
        return json.loads(row["data"])

    def find(self, table: str, session_id: str | None = None) -> list[dict]:
        assert table in self.tables
        with self.lock:
            rows = (self.db.execute(f"SELECT data FROM {table} WHERE session_id=? ORDER BY rowid",
                                    (session_id,)).fetchall() if session_id else
                    self.db.execute(f"SELECT data FROM {table} ORDER BY rowid").fetchall())
        return [json.loads(row["data"]) for row in rows]

    def message(self, sid: str, run_id: str, message: dict):
        self.db.execute("INSERT INTO messages(session_id,run_id,data) VALUES(?,?,?)",
                        (sid, run_id, dumps(message)))

    def messages(self, sid: str) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT data FROM messages WHERE session_id=? ORDER BY seq",
                                   (sid,)).fetchall()
        return [json.loads(row["data"]) for row in rows]

    def event(self, sid: str, run_id: str | None, kind: str, payload: dict):
        last = self.db.execute("SELECT COALESCE(MAX(event_id),0) FROM events WHERE session_id=?",
                               (sid,)).fetchone()[0]
        data = {"schema_version": 1, "session_id": sid, "run_id": run_id, "event_id": last + 1,
                "type": kind, "timestamp": now(), "payload": payload}
        self.db.execute("INSERT INTO events VALUES(?,?,?)", (sid, last + 1, dumps(data)))

    def events(self, sid: str, after: int = 0) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT data FROM events WHERE session_id=? AND event_id>? "
                                   "ORDER BY event_id LIMIT 1000", (sid, after)).fetchall()
        return [json.loads(row["data"]) for row in rows]

    def cursor(self, sid: str) -> int:
        with self.lock:
            return self.db.execute("SELECT COALESCE(MAX(event_id),0) FROM events WHERE session_id=?",
                                   (sid,)).fetchone()[0]

    def interrupt_commit(self, commit):
        """在调用者事务内同步中断状态；不写文件，也不猜测工具最终结果。"""
        changed = commit['status'] != 'INTERRUPTED'
        commit['status'] = 'INTERRUPTED'
        self.put('commits', commit)
        approval = self.get('approvals', commit['approval_id'])
        changed |= approval['status'] != 'INTERRUPTED'
        approval['status'], approval['commit_id'] = 'INTERRUPTED', commit['id']
        self.put('approvals', approval)
        error = {'code': 'RECOVERY_REQUIRED', 'message': '正式写入中断，请先对账恢复；未自动重放文件操作。',
                 'commit_id': commit['id']}
        if approval.get('call_id'):
            call = self.get('calls', approval['call_id'])
            if call['status'] != 'DONE':
                changed |= call['status'] != 'INTERRUPTED'
                call['status'] = 'INTERRUPTED'
                self.put('calls', call)
            run = self.get('runs', approval['run_id'])
            if run['status'] not in {'STOPPED', 'COMPLETED'}:
                changed |= run['status'] != 'INTERRUPTED' or run.get('error') != error
                run['status'], run['error'] = 'INTERRUPTED', error
                self.put('runs', run)
        if changed:
            session = self.get('sessions', commit['session_id'])
            session['revision'] += 1
            self.put('sessions', session)
            self.event(commit['session_id'], approval.get('run_id'), 'workspace.interrupted', error)

    def recover(self):
        with self.tx():
            for commit in self.find('commits'):
                if commit['status'] in {'APPLYING', 'ROLLING_BACK', 'INTERRUPTED'}:
                    self.interrupt_commit(commit)
            for run in self.find("runs"):
                if run["status"] in {"RUNNING", "READY"}:
                    run["status"] = "INTERRUPTED"
                    run["error"] = {"code": "PROCESS_INTERRUPTED",
                                    "message": "服务中断，检查点和预算已保留，可继续。"}
                    self.put("runs", run)
                    self.event(run["session_id"], run["id"], "run.interrupted", run["error"])

    def reserve(self, run: dict, input_tokens: int, output_tokens: int,
                input_price: float, output_price: float, settings) -> dict:
        amount = (input_tokens * input_price + output_tokens * output_price) / 1_000_000
        all_usage = self.find("usage")
        mine = [x for x in all_usage if x["run_id"] == run["id"]]
        if (sum(x["input_tokens"] for x in mine) + input_tokens > settings.max_input_tokens
                or sum(x["output_tokens"] for x in mine) + output_tokens >
                settings.max_total_output_tokens
                or sum(x["cny"] for x in mine) + amount > settings.max_run_cny
                or sum(x["cny"] for x in all_usage if x["session_id"] == run["session_id"]) + amount > settings.max_session_cny
                or sum(x["cny"] for x in all_usage) + amount > settings.max_project_cny):
            raise AppError("BUDGET_EXCEEDED", "已达到 Token 或费用预算，本轮已停止。", 409)
        record = {"id": uid(), "session_id": run["session_id"], "run_id": run["id"],
                  "input_tokens": input_tokens, "output_tokens": output_tokens, "cny": amount,
                  "input_price": input_price, "output_price": output_price,
                  "status": "RESERVED_UNKNOWN", "model": run["model"], "created_at": now()}
        self.put("usage", record)
        return record

    def settle(self, record: dict, reply):
        record.update(input_tokens=reply.input_tokens, output_tokens=reply.output_tokens,
                      cny=(reply.input_tokens * record["input_price"] +
                           reply.output_tokens * record["output_price"]) / 1_000_000,
                      status="USAGE_ESTIMATE", actual_model=reply.model,
                      provider_request_id=reply.request_id)
        self.put("usage", record)

    def close(self):
        self.db.close()
