import os
import stat
from pathlib import Path, PurePosixPath

from app.domain import AppError, sha


class Workspace:
    """所有用户文件读取使用目录句柄逐段打开，拒绝链接和私有路径。"""

    suffixes = {".md", ".txt", ".json", ".csv", ".py"}
    max_bytes = 65536

    def __init__(self, root: str | Path, identity: tuple[int, int] | None = None):
        self.root = Path(root)
        self.identity = identity

    @classmethod
    def parts(cls, path: str) -> tuple[str, ...]:
        p = PurePosixPath(path)
        raw = path.split("/")
        if (not path or len(path) > 300 or p.is_absolute() or "\\" in path or ":" in path
                or any(not x or x.startswith(".") for x in raw)
                or any(ord(c) < 32 for c in path)
                or p.suffix.lower() not in cls.suffixes):
            raise AppError("PATH_DENIED", "仅允许工作区内的教学文本相对路径。", 403)
        if any(x.lower() in {"node_modules", "secrets", "credentials"} for x in raw):
            raise AppError("PATH_DENIED", "该目录不在授权教学文件范围内。", 403)
        if any(x in p.name.lower() for x in ("secret", "credential", "private_key", "api_key", "apikey", "access_token", "密钥")):
            raise AppError("PATH_DENIED", "禁止读取凭据文件。", 403)
        return tuple(raw)

    def _root_fd(self) -> int:
        try:
            fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            info = os.fstat(fd)
            if self.identity is not None and (info.st_dev, info.st_ino) != self.identity:
                os.close(fd)
                raise AppError("WORKSPACE_UNAVAILABLE", "授权目录已被替换，请重新建立会话。", 409)
            return fd
        except OSError:
            raise AppError("WORKSPACE_UNAVAILABLE", "工作区不可用或已被替换。", 409) from None

    def read(self, path: str, *, allow_missing: bool = False) -> dict:
        parts = self.parts(path)
        fd = self._root_fd()
        try:
            for part in parts[:-1]:
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = nxt
            target = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            try:
                info = os.fstat(target)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise AppError("PATH_DENIED", "链接或非普通文件不可访问。", 403)
                if info.st_size > self.max_bytes:
                    raise AppError("FILE_TOO_LARGE", "文件超过 64 KiB 读取上限。", 413)
                data = bytearray()
                while len(data) <= self.max_bytes:
                    chunk = os.read(target, min(8192, self.max_bytes + 1 - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
                if len(data) > self.max_bytes:
                    raise AppError("FILE_TOO_LARGE", "文件超过 64 KiB 读取上限。", 413)
                content = data.decode("utf-8")
                return {"path": path, "content": content, "hash": sha(content)}
            finally:
                os.close(target)
        except FileNotFoundError:
            if allow_missing:
                return {"path": path, "content": "", "hash": None}
            raise AppError("FILE_NOT_FOUND", "工作区内没有该文件。", 404) from None
        except UnicodeDecodeError:
            raise AppError("ENCODING_ERROR", "仅支持 UTF-8 教学文本。", 422) from None
        except OSError:
            raise AppError("PATH_DENIED", "路径包含链接、不可访问目录或非法文件。", 403) from None
        finally:
            os.close(fd)

    def list_files(self) -> list[dict]:
        result: list[dict] = []

        def walk(fd: int, prefix: str, depth: int):
            if depth > 8:
                return
            for name in sorted(os.listdir(fd)):
                if name.startswith(".") or name in {"node_modules", "secrets", "credentials"}:
                    continue
                path = prefix + name
                try:
                    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode):
                        child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                        dir_fd=fd)
                        try:
                            walk(child, path + "/", depth + 1)
                        finally:
                            os.close(child)
                    elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                        self.parts(path)
                        if len(result) >= 200:
                            raise AppError("WORKSPACE_TOO_LARGE", "工作区文件超过 200 个，请缩小范围。", 413)
                        result.append({"path": path, "size": info.st_size})
                except AppError as error:
                    if error.code != "PATH_DENIED":
                        raise
                except OSError:
                    continue

        root = self._root_fd()
        try:
            walk(root, "", 0)
        finally:
            os.close(root)
        return result
