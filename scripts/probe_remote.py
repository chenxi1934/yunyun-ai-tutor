"""在用户指定SSH主机临时构建并运行应用，退出后清理本次容器、镜像标签和源码。

不上传.env，不发布端口，不安装宿主软件，不调整已有服务。
"""
import argparse
import hashlib
import json
import shlex
import subprocess
import tarfile
import tempfile
from pathlib import Path

from app.config import PROJECT_ROOT
from app.domain import dumps, now, uid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="SSH配置别名或 user@host；不要在参数中放密码")
    parser.add_argument("--pypi-index", default="https://pypi.org/simple", help="构建时的PyPI源；仅影响本次镜像")
    parser.add_argument("--real-startup", action="store_true", help="只检验真实Provider配置下的服务/静态资源，不调用远端模型")
    args = parser.parse_args()
    runtime = PROJECT_ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    options = ["-o", "ControlMaster=auto", "-o", "ControlPersist=600", "-o",
               f"ControlPath={runtime / 'ssh_control'}", "-o",
               f"UserKnownHostsFile={runtime / 'ssh_known_hosts'}", "-o",
               "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=8"]
    ssh = ["ssh", *options, args.target]
    identity = uid()
    remote = "/tmp/yunyun-stage02-" + identity
    image = "yunyun-stage02-probe:" + identity
    name = "yunyun-stage02-probe-" + identity

    def run(command, check=True, timeout=600, capture=False):
        return subprocess.run([*ssh, command], check=check, timeout=timeout,
                              capture_output=capture, text=capture)

    def include(info):
        if "__pycache__" in info.name or info.name.endswith(".pyc") or info.issym() or info.islnk():
            return None
        return info

    with tempfile.TemporaryDirectory(prefix="yunyun-upload-") as temporary:
        archive = Path(temporary) / "source.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for path in ["pyproject.toml", "Dockerfile", ".dockerignore", "backend", "scripts",
                         "frontend/package.json", "frontend/tsconfig.json", "frontend/vite.config.ts",
                         "frontend/index.html", "frontend/src"]:
                tar.add(PROJECT_ROOT / path, arcname=path, filter=include)
        run("mkdir " + shlex.quote(remote))
        try:
            subprocess.run(["scp", *options, str(archive), args.target + ":" + remote + "/source.tar.gz"],
                           check=True, timeout=60)
            build_arg = shlex.quote("PYPI_INDEX_URL=" + args.pypi_index)
            run(f"cd {shlex.quote(remote)} && tar xzf source.tar.gz && docker build --build-arg {build_arg} -t {shlex.quote(image)} .")
            model_provider = "bailian" if args.real_startup else "mock"
            entry = "verify_stage02.py --startup-only" if args.real_startup else "smoke_startup.py"
            invocation = ("docker run --rm --name " + name + " --network none --read-only "
                "--cap-drop=ALL --security-opt=no-new-privileges --memory=256m --pids-limit=64 "
                "--tmpfs /tmp:rw,nosuid,size=128m --tmpfs /data:rw,nosuid,uid=10001,gid=10001,size=32m "
                "-e LLM_PROVIDER=" + model_provider + " -e YUNYUN_EVIDENCE_DIR=/tmp/evidence " + image +
                " python scripts/" + entry)
            if args.real_startup:
                checked = run(invocation, timeout=120, capture=True)
                report = {"timestamp": now(), "status": "PASS", "source_archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                          "runtime": json.loads(checked.stdout),
                          "image_id": run("docker image inspect --format '{{.Id}}' " + image, capture=True).stdout.strip(),
                          "remote_model_called": False, "ports_published": False}
                location = runtime / f"stage02-remote-{identity}.json"
                location.write_text(dumps(report), encoding="utf-8")
                print(dumps({"status": "PASS", "evidence": str(location), "mock": False,
                             "remote_model_called": False, "ports_published": False}), flush=True)
            else:
                run(invocation, timeout=120)
                print("PASS：远端容器完成后端/静态前端、PC入口、真实进程重启恢复检查；LLM=MOCK_LLM，浏览器未测。", flush=True)
        finally:
            run("docker rm -f " + name, check=False, timeout=20)
            run("docker image rm " + image, check=False, timeout=20)
            cleanup = "import shutil; shutil.rmtree(" + repr(remote) + ")"
            run("python3 -c " + shlex.quote(cleanup), check=False, timeout=20)


if __name__ == "__main__":
    main()
