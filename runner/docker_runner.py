"""一次性受限容器；只接受代码和 stdin，镜像/命令/配额均由 Manager 冻结。"""
import asyncio
import contextlib
import json
import os
import re
import signal
import time
from pathlib import Path

from app.domain import dumps, sha
from app.verification.models import ExecutionRequest, ExecutionResult

LABEL = 'yunyun.runner=stage03'
POLICY = {'version': 1, 'case_seconds': 2, 'suite_seconds': 30, 'output_bytes': 65536,
          'memory': '128m', 'pids': 32, 'cpus': '0.5', 'tmp_bytes': '16m'}
# -I 禁用户 site/PYTHON* 注入；候选没有 expected、报告文件或宿主挂载。
# 容器内通过真实管道传stdin，支持buffer/FD 0和继承stdin的子进程。
BOOTSTRAP = """import sys,json,subprocess
from pathlib import Path
p=json.loads(sys.stdin.read())
Path('/tmp/candidate.py').write_text(p['code'],encoding='utf-8')
r=subprocess.run([sys.executable,'-I','-u','/tmp/candidate.py'],input=p['input'].encode('utf-8'))
sys.exit(r.returncode if r.returncode>=0 else 128-r.returncode)
"""


class DockerRunner:
    def __init__(self, image: str):
        # 配置必须指向已预拉取的不可变镜像；不运行用户自定镜像，不隐式 pull。
        if not re.fullmatch(r'(sha256:[a-f0-9]{64}|[^\s]+@sha256:[a-f0-9]{64})', image):
            raise ValueError('Runner 镜像必须是不可变 sha256 ID/digest')
        self.image = image
        self.runtime_digest = ''
        self.runner_policy_hash = sha(dumps(POLICY) + BOOTSTRAP +
                                      Path(__file__).read_text(encoding='utf-8'))
        self.healthy = False
        self.lock = asyncio.Lock()

    async def command(self, *args, timeout=5):
        proc = await asyncio.create_subprocess_exec('docker', *args,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout)
        except BaseException:
            proc.kill()
            await proc.wait()
            raise
        if proc.returncode:
            raise RuntimeError('Docker 管理命令失败：' + err.decode(errors='replace')[:500])
        return out.decode().strip()

    async def startup(self):
        # 专用 Manager 单实例；重启回收本策略标记的孤儿，不触碰其他容器。
        orphans = await self.command('ps', '-aq', '--filter', 'label=' + LABEL)
        if orphans:
            await self.command('rm', '-f', *orphans.split())
        info = json.loads(await self.command('info', '--format', '{{json .}}'))
        if not all(info.get(k) for k in ('MemoryLimit', 'SwapLimit', 'PidsLimit', 'CpuCfsQuota')):
            raise RuntimeError('Docker 宿主缺少必要的资源限制能力')
        if not any('seccomp' in x for x in info.get('SecurityOptions', [])):
            raise RuntimeError('Docker 必须支持默认 seccomp')
        self.runtime_digest = await self.command('image', 'inspect', '--format', '{{.Id}}', self.image)
        self.healthy = True

    def identity(self):
        return {'ready': self.healthy, 'runtime_digest': self.runtime_digest,
                'runner_policy_hash': self.runner_policy_hash, 'policy': POLICY}

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if not self.healthy:
            raise RuntimeError('Runner 未就绪')
        async with self.lock:
            return await self._execute(request)

    async def _execute(self, request):
        started = time.monotonic()
        name = 'yunyun-case-' + request.job_id
        evidence = {'job_id': request.job_id, 'container': name, 'isolated': True,
                    'limits': POLICY, 'cleanup': False}
        status, error, exit_code = 'RUNNER_ERROR', None, None
        streams = [bytearray(), bytearray()]
        proc = None
        try:
            cid = await self.command('create', '--pull=never', '-i', '--name', name,
                '--label', LABEL, '--network=none', '--user=10001:10001', '--read-only',
                '--cap-drop=ALL', '--security-opt=no-new-privileges', '--cpus=0.5',
                '--memory=128m', '--memory-swap=128m', '--pids-limit=32',
                '--ulimit', 'nofile=64:64', '--ulimit', 'core=0:0',
                '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777',
                '--workdir=/tmp', '--log-driver=none', '--env', 'LANG=C.UTF-8',
                self.runtime_digest, 'python', '-I', '-u', '-c', BOOTSTRAP)
            evidence['container_id'] = cid
            proc = await asyncio.create_subprocess_exec('docker', 'start', '-ai', name,
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE, start_new_session=True)

            async def capture(reader, buffer):
                while chunk := await reader.read(8192):
                    room = POLICY['output_bytes'] - len(buffer)
                    buffer.extend(chunk[:room])
                    if len(chunk) > room:
                        raise OverflowError('stdout/stderr 超过 64 KiB')

            async def feed():
                try:
                    proc.stdin.write(dumps(request.model_dump()).encode())
                    await proc.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    proc.stdin.close()

            tasks = [asyncio.create_task(capture(proc.stdout, streams[0])),
                     asyncio.create_task(capture(proc.stderr, streams[1])),
                     asyncio.create_task(feed()), asyncio.create_task(proc.wait())]
            try:
                await asyncio.wait_for(asyncio.gather(*tasks), POLICY['case_seconds'])
                state = json.loads(await self.command('inspect', '--format', '{{json .State}}', name))
                exit_code = state['ExitCode']
                stderr = streams[1].decode(errors='replace')
                if state.get('OOMKilled') or exit_code in (137, 139):
                    status, error = 'RESOURCE_LIMIT', '内存或进程资源限制终止程序'
                elif proc.returncode != 0 and exit_code == 0:
                    status, error = 'RUNNER_ERROR', 'Docker attach 失败'
                elif exit_code:
                    status = ('SYNTAX_ERROR' if re.search(r'^(?:\w*SyntaxError|IndentationError|TabError):', stderr, re.M) else
                              'ASSERTION_ERROR' if re.search(r'^AssertionError', stderr, re.M) else
                              'RESOURCE_LIMIT' if 'Resource temporarily unavailable' in stderr else
                              'RUNTIME_ERROR')
                    error = stderr[-2000:] or f'程序退出码 {exit_code}'
                else:
                    status = 'PASS'  # 仅表示执行成功；服务端仍须比对所有固定 expected。
            except TimeoutError:
                status, error = 'TIMEOUT', '用例超过 2 秒墙钟限制'
            except OverflowError as exc:
                status, error = 'OUTPUT_LIMIT', str(exc)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            status, error = 'RUNNER_ERROR', str(exc)[:1000]
        finally:
            # rm -f 由 daemon 杀整个容器进程树；不能仅杀 Docker CLI。
            try:
                await asyncio.shield(self.command('rm', '-f', name))
                evidence['cleanup'] = True
            except Exception:
                self.healthy = False
                status, error = 'RUNNER_ERROR', '容器清理失败，执行器已关闭'
            if proc and proc.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGKILL)
                await proc.wait()
        return ExecutionResult(status=status, stdout=streams[0].decode(errors='replace'),
            stderr=streams[1].decode(errors='replace'), exit_code=exit_code,
            duration_ms=(time.monotonic() - started) * 1000, error=error, evidence=evidence,
            runtime_digest=self.runtime_digest, runner_policy_hash=self.runner_policy_hash)
