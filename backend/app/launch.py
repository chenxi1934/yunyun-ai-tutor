import argparse
import secrets
import threading
import webbrowser
from pathlib import Path

import uvicorn
from pydantic import SecretStr

from app.api import create_app
from app.config import Settings


def main():
    parser = argparse.ArgumentParser(description="耘耘AI助教 PC 启动入口")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if args.workspace.is_symlink() or not args.workspace.is_dir():
        parser.error("--workspace 必须指向已有的真实教学目录。")
    token = secrets.token_urlsafe(32)
    settings = Settings(yunyun_mode="pc", yunyun_workspace=args.workspace.resolve(),
                        yunyun_local_token=SecretStr(token))
    app = create_app(settings)
    if not args.no_browser:
        url = f"http://127.0.0.1:{args.port}/#token={token}"
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print("本机工作台已准备；代码执行与正式发布将在后续阶段开放。", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
