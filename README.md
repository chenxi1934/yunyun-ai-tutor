# 耘耘AI助教

阶段 02 工程骨架：Python 3.12 / FastAPI / Pydantic / SQLite，共享串行 Agent Core，React / TypeScript / Vite / Tailwind 教师工作台。当前可真实调用百炼工具、读授权工作区、保存草稿、查看 diff、暂停审批及恢复会话。

**代码执行器、教育结构化产出、正式批准/写入与教案包导出尚未开放。** `run_python_tests` 明确返回 `RUNNER_UNAVAILABLE / NOT_TESTED`，不会执行未知代码或显示假通过；阶段 03/04/05 分别补齐这些能力。

## 安装与配置

需要 Python **3.12**（不要误用 macOS 系统 Python 3.9）、Node 22.19+、npm。

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
npm --prefix frontend install --package-lock=false
npm --prefix frontend run build
```

将 `.env.example` 复制为本地 `.env`，填写 `DASHSCOPE_API_KEY`。已有 `.env` 请保留。默认平台为百炼，地址 `https://dashscope.aliyuncs.com/compatible-mode/v1`，模型 `qwen3.8-max`，关闭 thinking。更换模型还需显式配置经核对的 `LLM_INPUT_CNY_PER_MILLION` 与 `LLM_OUTPUT_CNY_PER_MILLION`；`qwen3.8-max` 估价采用输入 ¥12/百万、输出 ¥36/百万。

仅显式设置 `LLM_PROVIDER=mock` 才进入 **MOCK_LLM** 固定读文件演示；界面与事件醒目标识，真实 API 失败不自动切 Mock。密钥只在后端，`.env`、运行数据库和构建依赖均忽略于 Git。本阶段遵照仓库规则未生成锁文件，后续需另行授权固定完整依赖树。

## 本机 PC

先创建仓库外的教师目录，放入 UTF-8 教学 Markdown/Python/JSON/CSV/TXT 文件。然后一条命令启动：

```bash
bash scripts/start-desktop.sh --workspace /绝对路径/教师教案目录
```

服务仅监听 `127.0.0.1:8000`，启动入口生成本机能力口令，通过 URL fragment 交给页面并立即清除 fragment；口令保存在该标签页的 sessionStorage，不进入日志。`--no-browser` 可关闭自动打开浏览器，`--port 8001` 可更换端口。目录只通过启动参数授权；API 无任意开目录入口。草稿保存在应用 SQLite，正式目录不变。

## Web 开发与部署骨架

```bash
# 已构建的前端由同一API服务提供
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
# 可选开发界面，/api 代理到本机8000
npm --prefix frontend run dev
```

Web 会话从两个明确标识为 NOT_TESTED 的合成种子文件复制独立工作区。服务端随机 HttpOnly / SameSite=Strict cookie 绑定资源归属；PC 有本机能力口令，变更请求校验 Origin/Host。当前只支持一个 API worker，同一实例串行运行任务。数据库默认 `.runtime/state.sqlite3`，重启保持目录和 cookie 可恢复，运行中的任务转为 INTERRUPTED，需教师点击继续。

```bash
docker build -t yunyun-tutor:stage02 .
docker run --rm --name yunyun-tutor -p 127.0.0.1:8000:8000 \
  --env-file .env -e YUNYUN_MODE=web -e YUNYUN_DATA_DIR=/data \
  -v yunyun-stage02-data:/data yunyun-tutor:stage02
```

镜像使用 Python 3.12，非 root，无 Docker Socket。该骨架不是公网发布：实际部署还需 HTTPS、同源反向代理、持久卷和私网 Runner；设置 `YUNYUN_HOSTS=域名,127.0.0.1` 与 `YUNYUN_SECURE_COOKIE=true`。不要公开当前阶段尚未具备完整费用/访问治理的演示实例，不要复用已有 80 端口服务。阶段 02 不提供任意 shell，也不使用裸 subprocess 执行模型代码。

## 验证

```bash
# 离线控制流/权限/恢复测试，模型为测试Mock；不会消费Key
.venv/bin/python -m pytest backend/tests/unit/test_agent_loop.py backend/tests/unit/test_policy.py backend/tests/unit/test_provider.py backend/tests/integration/test_session_resume.py backend/tests/integration/test_api.py -q
.venv/bin/ruff check backend scripts
npm --prefix frontend run build
# 真实启动PC/Web进程并停止、重启，读取静态界面和SSE；模型显式Mock，不启动浏览器
.venv/bin/python scripts/smoke_startup.py
# 阶段02真实HTTP验收：PC/Web真实模型调用、SIGKILL/恢复与错误分支；需Key，会消费额度
.venv/bin/python scripts/verify_stage02.py
# 显式真实API探针，有费用；随机标记读取→草稿→第二轮上下文
.venv/bin/python scripts/probe_provider.py
# 同一核心的Web模式真实探针；失败可显式加 --resume <探针会话ID>，预算保留
.venv/bin/python scripts/probe_provider.py --mode web
# 仅用户指定的SSH服务器：临时构建/运行，不上传.env，不发布端口，结束清理
.venv/bin/python scripts/probe_remote.py user@host
# 只检验远端真实Provider配置下的服务/静态资源，不上传Key、不调用远端模型
.venv/bin/python scripts/probe_remote.py user@host --real-startup
```

本轮远端到官方PyPI文件下载存在超时，已验证腾讯镜像可构建。需要时对本次镜像显式指定 `docker build --build-arg PYPI_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple -t yunyun-tutor:stage02 .`，或为远端探针追加 `--pypi-index https://mirrors.cloud.tencent.com/pypi/simple`；不修改宿主全局源配置。

默认上限：每 run 12 次模型请求、24 次工具调用、12 分钟主动时间、输入 80k / 输出 12k token、费用估算 ¥3；每会话 ¥9、实例累计 ¥45。请求前保守预留，厂商 usage 后结算估值，超时/中断预留不会清零。已结束 run 的消息和事件不因刷新重放。正式审批接口在本阶段只支持拒绝；批准会明确返回 `PUBLISH_NOT_READY`。

浏览器尚未验证。手动操作：启动 PC 后输入“读取工作区示例并提出修改草稿”，预期出现真实文件读取记录和 diff，正式文件不变；刷新恢复会话，检查失败提示、工作区展开及审核拒绝后的状态。完整验收状态与本阶段执行证据见 [PROGRESS](docs/PROGRESS.md) 和 [ACCEPTANCE](docs/ACCEPTANCE.md)。
