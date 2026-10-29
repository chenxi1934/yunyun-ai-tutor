import os
import stat
from pathlib import Path, PurePosixPath

from app.domain import AppError, sha, uid


def is_python_path(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() == ".py"


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
                return {"path": path, "content": content, "hash": sha(content), "mode": stat.S_IMODE(info.st_mode) & 0o777}
            finally:
                os.close(target)
        except FileNotFoundError:
            if allow_missing:
                return {"path": path, "content": "", "hash": None, "mode": None}
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

    def replace(self, path: str, content: str | None, expected_hash: str | None, *,
                mode: int | None = None, expected_mode: int | None = None):
        """提交服务专用：目录句柄内原子替换；再次校验外部文件和链接。"""
        parts = self.parts(path)
        if content is not None and len(content.encode('utf-8')) > self.max_bytes:
            raise AppError('FILE_TOO_LARGE', '正式文件超过64 KiB。', 413)
        fd = self._root_fd()
        temporary = None
        try:
            for part in parts[:-1]:
                if content is not None:
                    try:
                        os.mkdir(part, mode=0o755, dir_fd=fd)
                    except FileExistsError:
                        pass
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = nxt
            # 校验后只操作已打开的父目录，避免父路径被替换后写到外部。
            def current_state():
                try:
                    target = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                except FileNotFoundError:
                    return None, None
                try:
                    info = os.fstat(target)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > self.max_bytes:
                        raise AppError('PATH_DENIED', '目标已变为链接或不可写教学文件。', 403)
                    with os.fdopen(os.dup(target), 'r', encoding='utf-8', newline='') as stream:
                        return sha(stream.read(self.max_bytes + 1)), stat.S_IMODE(info.st_mode) & 0o777
                finally:
                    os.close(target)
            original_hash, original_mode = current_state()
            if original_hash != expected_hash or (expected_mode is not None and original_mode != expected_mode):
                raise AppError('REVISION_CONFLICT', '正式文件已被外部修改，请重新生成Diff。', 409)
            if content is None:
                os.unlink(parts[-1], dir_fd=fd)
            else:
                temporary = '.yunyun-' + uid()
                target = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=fd)
                with os.fdopen(target, 'wb') as stream:
                    stream.write(content.encode('utf-8'))
                    stream.flush()
                    target_mode = mode if mode is not None else (original_mode if original_mode is not None else 0o600)
                    if not 0 <= target_mode <= 0o777:
                        raise AppError('INVALID_MODE', '文件权限超出普通访问位范围。', 422)
                    os.fchmod(stream.fileno(), target_mode)
                    os.fsync(stream.fileno())
                if current_state() != (original_hash, original_mode):
                    raise AppError('REVISION_CONFLICT', '写入前目标版本已变化。', 409)
                os.replace(temporary, parts[-1], src_dir_fd=fd, dst_dir_fd=fd)
                temporary = None
            os.fsync(fd)
        except (OSError, UnicodeError):
            raise AppError('WORKSPACE_WRITE_FAILED', '文件写入失败或目标包含链接，请检查工作区。', 409) from None
        finally:
            if temporary:
                os.unlink(temporary, dir_fd=fd)
            os.close(fd)
