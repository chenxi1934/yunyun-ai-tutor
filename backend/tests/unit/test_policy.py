import os

import pytest
from app.domain import AppError, sha
from app.workspaces import Workspace


@pytest.mark.parametrize("path", ["../secret.md", "/tmp/secret.md", "folder\\file.py", "./file.py",
                                  "folder/../file.py", ".env", ".git/config", "a//file.py",
                                  "C:/file.py", "secrets/data.json", "private_key.txt", "api_key.json"])
def test_path_rejected(tmp_path, path):
    with pytest.raises(AppError) as error:
        Workspace(tmp_path).read(path)
    assert error.value.code == "PATH_DENIED"


def test_symlink_hardlink_and_same_prefix_directory_denied(tmp_path):
    root = tmp_path / "teacher"
    root.mkdir()
    outside = tmp_path / "teacher-other"
    outside.mkdir()
    source = outside / "file.md"
    source.write_text("secret")
    (root / "linked.md").symlink_to(source)
    (root / "linked_dir").symlink_to(outside, target_is_directory=True)
    os.link(source, root / "hard.md")
    ws = Workspace(root)
    for path in ["linked.md", "linked_dir/file.md", "hard.md", "../teacher-other/file.md"]:
        with pytest.raises(AppError):
            ws.read(path)
    assert ws.list_files() == []


def test_path_swap_after_validation_is_rechecked(tmp_path):
    root, outside = tmp_path / "teacher", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "data.md").write_text("outside")
    (root / "folder").mkdir()
    ws = Workspace(root)
    ws.parts("folder/data.md")
    (root / "folder").rmdir()
    (root / "folder").symlink_to(outside, target_is_directory=True)
    with pytest.raises(AppError):
        ws.read("folder/data.md", allow_missing=True)


def test_size_and_utf8_boundaries(tmp_path):
    (tmp_path / "big.md").write_bytes(b"a" * 65537)
    (tmp_path / "bad.md").write_bytes(b"\xff")
    for name, expected in [("big.md", "FILE_TOO_LARGE"), ("bad.md", "ENCODING_ERROR")]:
        with pytest.raises(AppError) as error:
            Workspace(tmp_path).read(name)
        assert error.value.code == expected


def test_formal_patch_conflicts_are_not_hidden(setup_agent):
    from app.domain import dumps, uid
    from conftest import ScriptedProvider

    agent, store, session, root = setup_agent(ScriptedProvider())
    call = {"id": uid(), "run_id": "test", "name": "propose_patch", "arguments": dumps({
        "path": "fixture.md", "content": "changed", "base_hash": sha("wrong original")})}
    original = (root / "fixture.md").read_bytes()
    with store.tx():
        result = agent.registry.execute(call, session, agent.workspace(session))
    assert result["error"]["code"] == "REVISION_CONFLICT"
    assert (root / "fixture.md").read_bytes() == original
    assert not store.find("drafts")


def test_authorized_root_replaced_with_another_directory_is_denied(setup_agent):
    from conftest import ScriptedProvider

    agent, _, session, root = setup_agent(ScriptedProvider())
    root.rename(root.with_name("old-teacher"))
    root.mkdir()
    (root / "fixture.md").write_text("different owner")
    with pytest.raises(AppError) as error:
        agent.workspace(session).read("fixture.md")
    assert error.value.code == "WORKSPACE_UNAVAILABLE"


def test_nested_file_quota_error_propagates(tmp_path):
    folder = tmp_path / "nested"
    folder.mkdir()
    for number in range(201):
        (folder / f"{number:03}.md").write_text("synthetic teaching fixture")
    with pytest.raises(AppError) as error:
        Workspace(tmp_path).list_files()
    assert error.value.code == "WORKSPACE_TOO_LARGE"


def test_file_quota_only_counts_allowed_files(tmp_path):
    for number in range(200):
        (tmp_path / f"{number:03}.md").write_text("synthetic teaching fixture")
    (tmp_path / "z-ignored.bin").write_bytes(b"ignored")
    assert len(Workspace(tmp_path).list_files()) == 200


async def test_read_draft_enforces_session_ownership_and_strict_arguments(setup_agent):
    from app.domain import dumps, uid
    from conftest import ScriptedProvider, reply

    agent, store, session, _ = setup_agent(ScriptedProvider(
        reply(("propose_patch", {"path": "draft.md", "content": "private draft body", "base_hash": None})),
        reply(content="草稿已保存。")))
    run = agent.new_run(session["id"], "创建草稿", 0, "request-0001")
    await agent.run(run["id"])
    draft = store.find("drafts", session["id"])[0]
    other = agent.create_session("another-owner", session["context"])

    def read_as(current, args):
        return agent.registry.execute({"id": uid(), "name": "read_draft", "run_id": run["id"],
                                       "arguments": dumps(args)}, current, agent.workspace(current))

    own = read_as(session, {"draft_id": draft["id"]})
    assert own["ok"] and own["data"]["content"] == "private draft body"
    denied = read_as(other, {"draft_id": draft["id"]})
    assert not denied["ok"] and denied["error"]["code"] == "NOT_FOUND"
    assert "private draft body" not in dumps(denied)
    malformed = read_as(other, {"draft_id": draft["id"], "session_id": session["id"]})
    assert malformed["error"]["code"] == "INVALID_TOOL_ARGUMENTS"
