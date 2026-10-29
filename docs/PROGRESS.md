# 开发进度与真实验证记录

> 不要把计划写成已完成。由 Codex 每阶段更新，写明事实和证据。

| 阶段 | 状态 | 验收证据 | 阻塞/风险 |
|---|---|---|---|
| 1. 设计/骨架/预部署 | PARTIAL：设计/骨架/远端临时容器验证完成 | 阶段02命令与下方证据；远端 Python 3.12 / Node 22 镜像构建及进程恢复通过 | 公网入口/HTTPS与独立 Runner 尚未交付 |
| 2. Agent Core | Review两项缺陷已修复；针对性回归PASS | 当前62项pytest、真实百炼草稿取回；旧版本九项证据保留为历史，本轮未全量重跑 | run_python_tests 明确不可用；正式批准/提交待阶段03/05；当前完整九项复验NOT_TESTED |
| 3. 正确性验证 | NOT_STARTED | 无真实执行报告 | 独立 Runner 与隔离尚未实现/验证 |
| 4. 教育能力 | NOT_STARTED | 仅协议/策略与用例设计 | 尚无真实生成及两班情/两学段对照 |
| 5. PC/Web | NOT_STARTED（启动/部署骨架已在02建立） | 本机和VPS临时容器可运行共享API与静态前端；无公网/整包证据 | 正式提交、导出、HTTPS及完整双端教育验收待实现 |
| 6. 回归与交付 | NOT_STARTED | 未运行产品回归，未生成视频/交付链接 | 依赖前五阶段与人工教育审核 |

## 2026-10-29：执行 prompts/01-plan.md，仅架构与验收设计

### 本轮实际完成

- 读取仓库 AGENTS、原题、现有 PLAN/PROGRESS/ACCEPTANCE、启动说明与后续 02–06 阶段 prompts；保留原题与用户已有规则。
- `git status --short` 初始为 `.DS_Store`、AGENTS、README、docs、prompts 均未跟踪；基线文件数 17。本轮修订 PLAN、ACCEPTANCE、PROGRESS 与追加要求中的 DESIGN_DECISIONS 四个文档，不创建业务源码，不执行 Git 提交、推送或发布。
- [PLAN.md](PLAN.md) 写入共享核心、工具白名单/原生调用、循环限额、暂停恢复、结构化教育协议、学情依据链、工作区/hash/审批/回退、Runner 隔离、API/SSE、0–5h 部署闸口、六阶段任务、五项阻塞及三个人工决定。
- [ACCEPTANCE.md](ACCEPTANCE.md) 按原题补为 A–E 24 项和 F01–F23 故障标准，写入 PC/Web 手动验收步骤；所有产品功能仍 NOT_TESTED。
- 用户在规划期间更新 AGENTS/阶段 5 提示并新增 UI_GUIDELINES 与参考图；读取后保留其内容，PLAN 同步引用 UI 规范。按追加要求仅给 DESIGN_DECISIONS 增加一个简短的“产品交互与视觉设计”段落，保持原有一页骨架；未重复添加已有规则。
- 已查阅 DeepSeek 与阿里云官方工具调用文档，确认候选存在原生工具调用协议；仅属文档核对，未用账户实际调用，不满足 A4。来源与检查日期见 PLAN 第 3 节。
- 未启动本地服务/浏览器/Docker，未安装依赖、修改本机环境或 `.env`，未创建云资源/部署。未使用多 Agent。

### 本轮实际命令与观察

环境探测通过只读 Python 脚本使用 `shutil.which` 和带超时的 `subprocess.run` 执行下列命令；检查环境变量只输出存在性，不输出密钥值。

| 命令/检查 | 实际结果 | 结论边界 |
|---|---|---|
| `git status --short` | 退出 0；初始全部为未跟踪作战包文件 | 已记录用户现有内容，未覆盖无关文件 |
| `rg --files --hidden`（排除 .git/构建/依赖） | 仅文档与阶段 prompts | 无可运行项目骨架，不能运行产品测试 |
| `platform.system()/mac_ver()/machine()` | Darwin / 27.0 / arm64 | 当前机器信息；现场机器尚待确认 |
| `python3.12 --version` | 退出 0，Python 3.12.14，位于用户本地 bin | 3.12 解释器存在；项目依赖未验证 |
| `python3 --version` | 退出 0，Python 3.9.6，系统路径 | 后续启动必须显式选择 3.12 |
| `node --version`、`npm --version` | 均退出 0，v22.19.0 / 10.9.3 | 构建工具存在；未运行 Vite/构建 |
| `docker --version` | 退出 0，29.3.1，build c2be9cc | 只有 CLI 可用证据 |
| `docker info --format '{{.ServerVersion}}'` | 退出 1；用户 Docker socket 不存在，无法连接 daemon | 真实探测失败，未启动 daemon，Runner 仍不可验收 |
| DEEPSEEK_API_KEY / DASHSCOPE_API_KEY / OPENAI_API_KEY 存在性 | 当前进程均未设置 | 不代表用户没有 Key；真实 API NOT_TESTED |
| `python3.12 -`（内联文档一致性/文件边界检查） | 退出 0；24 项需求与 23 项故障 ID 唯一且全为 NOT_TESTED；六阶段合计 48h；相对链接/代码围栏有效；本轮仅改四个文档 | 检查脚本见本会话工具记录，不新增仓库脚本；不等同于产品测试 |
| `git diff --no-index --check <本轮前临时快照> <目标文档>`（四文件逐一） | 无空白错误输出；额外检查无行末空白且结尾有换行 | 文件原为未跟踪，故用本轮前快照核对，避免普通 git diff 漏检 |

文档检查首次因内联命令编码错误未完成，改为显式 Python 3.12 与 ASCII 转义后重跑。边界检查同时发现用户更新 AGENTS/阶段 5 提示及新增 UI 规范/参考图；已按追加消息读取、区分并保留，未回滚这些文件。两处 UI 前置规则各已有明确要求，没有重复添加；DESIGN_DECISIONS 仅增加 4 行，当前共 25 行、572 字符，保留一页简短骨架，其他章节待真实实现后填写。

### 当前 P0、风险与下一步

产品没有开始实施，A–E 与故障场景全部 NOT_TESTED；不存在已通过的代码、部署或教育验证。百炼平台、旗舰模型及 endpoint 已确定，目标 VPS 已成功只读连接；尚待验证本地凭据配置、账户模型权限与真实工具往返，准备 Docker/镜像获取与应用入口。PC 普通子进程仅有限防护，不能宣称沙箱；Web 无隔离时必须关闭执行和正式交付。

下一步先由用户复核 PLAN 第 12 节的运行资源、模型/费用、教学/发布闸口三个决定，再在明确的下一阶段范围内创建骨架并完成 0–5h 探针。最先打通单个累加示例的真实失败→修复→重测→拒绝/确认→本地落盘→重启恢复；不提前扩张 UI 或整套业务。本轮没有开始执行 prompts/02-agent-core.md。

### 验证缺口

- pytest、前端类型检查/构建、Playwright：NOT_TESTED；原因是本轮仅文档规划，仓库尚无业务源码、依赖配置或测试文件。
- 浏览器、现场 PC 冷启动、公网 URL、真实模型请求与费用、容器隔离/故障清理：NOT_TESTED；没有运行服务或部署，相关授权/资源仍待下一阶段确认。
- 本轮没有真实 AI 代码失败案例，不能编造并填充 AI_DEV_LOG，也不能把设计中的故意错误样例当成已运行证据。

## 2026-10-29：模型接入决定更新，未启动阶段 02

- 用户选定阿里云百炼与 `https://dashscope.aliyuncs.com/compatible-mode/v1`；PLAN 同步平台选择，初始模型建议 `qwen-plus`，模型 ID 保持可配置。
- 本轮仅记录非敏感决定并核对百炼官方 Function Calling/调用示例；未把用户提供的密钥写入文件、工具参数或 Git，未修改 `.env`、调用模型 API 或开发业务代码。
- 平台选择已明确；凭据有效性、模型权限、余额与原生工具调用仍 NOT_TESTED，不能将收到凭据等同于接入完成。A4 保持 NOT_TESTED。
- 验证：`git diff --check` 与 `python3.12 -` 内联静态检查均通过；仅上述三个文档有改动，24 项需求/23 项故障状态不变，文档未检出密钥格式值，未创建本地配置或业务目录。

## 2026-10-29：旗舰模型与目标 VPS 只读检查

- 用户要求更高档模型，默认模型改为百炼 `qwen3.8-max`。已核对官方目录、Function Calling 与北京地域原价（输入 ¥12/百万 token、输出 ¥36/百万 token）；仍沿用现有费用上限，未发起真实模型调用。
- 本轮开始时工作区干净，本地已有用户提交 `b4d4e6b`，比本地记录的 origin/master 超前 1 个提交；保留该提交，不自动推送。
- 使用用户提供的连接信息完成一次 SSH 只读探测，远端执行 `python3 -` 内联脚本，退出 0；读取系统/资源、命令存在性、监听端口，并执行无凭据的 HTTPS 可达性探测。连接口令与服务器地址不写入仓库。

| 实际检查 | 结果 | 可证明的范围 |
|---|---|---|
| `uname -srm`、`/etc/os-release`、CPU/内存/磁盘读取 | Ubuntu 26.04 LTS，x86_64，4 核，内存约 7.4 GiB，根盘剩余约 161.1 GiB | 目标资源容量满足设计建议，不代表应用已部署 |
| `shutil.which`、`python3 --version` | 未发现 docker/node 命令；Python 3.14.4 | Docker/Compose 执行能力尚未就绪；项目仍按 Python 3.12 实施，不改技术栈 |
| `ss -ltn` | 80 端口已有监听 | 后续部署须保留既有服务，本轮未改端口/配置 |
| `curl` 百炼 `/models`，未带 Key | 退出 0，HTTP 401，TLS 校验结果 0 | 只证明远端到百炼 HTTPS 可达，不证明 Key 或旗舰模型可用 |
| `curl` Docker Hub registry `/v2/` | 退出 28，HTTP 000，4 秒连接限额超时 | 本次直连探测失败；镜像获取与隔离 Runner 尚未验证 |

- 未安装软件、创建应用、部署、启动或重启服务，未修改 `.env`，未编写业务代码。初次连接命令因包含临时文件清理的 `rm -f` 被自动审核拒绝，未执行；改用不创建临时文件的 SSH 命令后完成上述检查。
- A4、D1 与全部产品能力仍 NOT_TESTED；已收到资源与凭据不能等同于真实工具闭环、部署或隔离验收通过。
- `git diff --check` 与 `python3.12 -` 内联静态检查通过：仅 PLAN/ACCEPTANCE/PROGRESS 变更，24 项需求及 23 项故障均保持 NOT_TESTED，未创建业务目录或本地凭据文件。按用户安排，远端整备交由其他人执行，本轮只在聊天中提供任务与验收清单，不继续操作服务器。

## 2026-10-29：阶段02 — 工程骨架、真实 Agent Core 与恢复

本轮按 `prompts/02-agent-core.md` 编码。开始时 PLAN/PROGRESS/ACCEPTANCE 已有用户未提交修改，全部保留；本轮不改 PLAN、AGENTS、原题和 UI 规则，不提交/推送 Git。用户自行完成本地 `.env` 配置，并授权继续检查已整备的服务器；凭据未进入源码、构建上下文或仓库文档。

### 实现与文件

- `pyproject.toml`、`backend/app/`：Python 3.12、FastAPI、Pydantic、SQLite；配置从本地 `.env` 读取，百炼 `qwen3.8-max` 使用原生 tool_calls，关闭 thinking。Mock 仅显式启用，不自动降级。
- `agent.py` / `providers.py` / `tools.py`：真实模型→串行白名单工具→按原生 call_id 回传→继续推理；模型请求/工具数、主动时间、Token、单 run/会话/实例费用预留与停止，临时网络错误最多两次重试，重复无进展停止。没有可靠 usage 的请求保留未知预留，已知未发送则不计费。
- `storage.py` / `workspaces.py`：真实读取、SQLite不可变草稿/diff/审批/消息/工具结果/预算/事件检查点；路径逐段目录句柄 + O_NOFOLLOW、硬链接/敏感文件拒绝、根目录 inode 绑定、64 KiB 限制。Web 根目录由服务端分配；PC 根目录由启动参数授权。
- `list_files`、`read_file`、`propose_patch`、`run_python_tests`、`request_publish` 已注册。测试工具当前真实返回 `RUNNER_UNAVAILABLE / NOT_TESTED`，没有执行候选代码；正式变更只能进入待审批暂停，拒绝后可继续原批工具，批准返回 `PUBLISH_NOT_READY`。正式文件不变。
- `api.py` / `launch.py`：会话归属 cookie、Host/Origin 与 PC 能力口令检查；SSE先落库后发送，游标补发；幂等请求、单会话活动 run、实例串行执行。重启后 READY/RUNNING 变 INTERRUPTED，预算保留；等待审批保持暂停，不自动重放写操作。
- `frontend/src/`：React/TS/Vite/Tailwind/Lucide 最小教师工作台，历史/聊天/文件/草稿diff/执行事件/失败/继续/拒绝入口；浅紫白色沿用现有规范。执行未接通与 Mock 显著标识；完成 `web-design-guidelines` 源码检查，修正上下文回显、空/加载状态、旧快照覆盖和键盘焦点/语义标题。
- `scripts/start-desktop.sh`、`scripts/smoke_startup.py`、`scripts/probe_provider.py`、`scripts/probe_remote.py`、`Dockerfile`、`README.md`：PC一条启动命令、同源静态前端、远端临时容器探针；没有启动浏览器，没有公网发布或改已有服务。

### 实际命令与结果

命令均在仓库根目录运行。源码指纹（后端/前端/脚本/构建配置与种子，不含凭据/文档/依赖产物）：`bca61b9f476cd5acfad689bfc2a3ac3f41fd04135204e0b6aae8c60780be55fd`；可复查于 `.runtime/source-sha256.txt`。运行证据目录已被 Git 忽略。

| 实际命令 | 结果与证据 | 验收边界 |
|---|---|---|
| `uv venv --python python3.12 .venv`；`uv pip install --python .venv/bin/python --default-index https://pypi.org/simple -e '.[dev]'` | PASS；Python 3.12.14；依赖安装成功 | 只安装项目虚拟环境，未改系统解释器/全局源 |
| `npm --prefix frontend install --package-lock=false --registry=https://registry.npmjs.org --prefer-offline --fetch-retries=1 --fetch-timeout=30000 --no-fund` | PASS；39项审计，最终0个已知漏洞 | 未生成仓库锁文件；不表示未知风险为零 |
| `.venv/bin/python -m pytest backend/tests/unit/test_agent_loop.py backend/tests/unit/test_policy.py backend/tests/unit/test_provider.py backend/tests/integration/test_session_resume.py backend/tests/integration/test_api.py -q` | PASS；**51 passed**，1条Starlette TestClient未来弃用警告 | 模型为显式测试Mock/HTTP契约桩，不消费Key；覆盖真实文件/SQLite、预算、错误、权限、恢复与SSE |
| `.venv/bin/ruff check backend scripts`；`git diff --check` | PASS | 仅本轮代码/相关diff检查 |
| `npm --prefix frontend run build` | PASS；TypeScript + Vite 7.3.7；1580 modules；JS `index-6QFvVWe9.js` / CSS `index-CTLBFxWQ.css` | 编译成功，未执行浏览器渲染/交互 |
| `.venv/bin/python scripts/probe_provider.py`（首轮PC） | PASS；真实百炼原生 list/read/propose；随机文件标记进入工具结果、草稿及最终回复，第二轮正确复述；正式文件未创建；5次请求，usage输入8267/输出575，估算¥0.119904；`.runtime/probe-provider.json` | 真实API，不是Mock；不是代码验证或完整教案 |
| `.venv/bin/python scripts/probe_provider.py --mode web`；随后 `--mode web --resume <探针session_id>` | 首次 FAIL（PROVIDER_PROTOCOL），同一检查点继续后 PASS；真实 list/read/propose与第二轮通过，未重复创建草稿；`.runtime/probe-provider-web.json` 保存工具、事件、usage和 recovered_errors | 失败没有抹除或切Mock；合计估算/预留¥0.338520，含一次用量未知的保守预留 |
| `.venv/bin/python scripts/smoke_startup.py` | PASS；`.runtime/smoke-startup.json` / `.runtime/smoke-startup.log`：实际启停PC/Web进程、HTTP健康/前端、无本机口令拒绝、工具真实读取、重启恢复消息/草稿/审批/usage、拒绝后继续无重复、SSE回放、缺Key真实报错 | LLM显式Mock；故障分支为真实Bailian Provider缺Key，不发网络；不启动浏览器 |
| `bash scripts/start-desktop.sh --workspace <仓库外临时教师目录> --no-browser --port <随机空闲端口>` | PASS；真实启动shell入口，HTTP健康检查200，随后正常停止 | 合成临时目录、LLM显式Mock，不打开浏览器 |
| `.venv/bin/python scripts/probe_remote.py <SSH目标> --pypi-index https://mirrors.cloud.tencent.com/pypi/simple` | PASS；远端Docker 29.9.2 / Compose 5.6.1，Python 3.12.16 x86_64 + Node22多阶段构建；同一启动/恢复探针全部通过，最终临时镜像 manifest `sha256:93dcdb6b1e848fe021596916e864b554e71450d11a3935cb7540e41f4b528fa0`；命令输出保存在本会话 | 容器非root、只读根、无外网、无Socket、无宿主挂载、无发布端口；这是应用启动测试，**不是候选代码Runner隔离验收** |

真实API本轮累计估算/未知用量预留 **¥0.458424**，未知预留1笔；不是账单精确实耗。探针与应用共用SQLite预算，恢复不清零。临时远端容器、应用镜像标签和源码目录由脚本清理；基础镜像/构建缓存保留，未安装宿主Python/Node、未改80端口服务。

### 排错与修复记录

- 本机清华PyPI源403：本次命令显式使用官方源；没有修改全局配置。
- npm元数据下载缓慢、镜像Babel版本不一致：移除非必要Babel插件，使用Vite内置JSX；刷新官方元数据并固定直接依赖。根据[Vite官方公告](https://github.com/vitejs/vite/security/advisories/GHSA-9jrq-w75r-8gcw)选7.3.7，并按[esbuild](https://github.com/advisories/GHSA-g7r4-m6w7-qqqr)/[source-map-js](https://github.com/advisories/GHSA-68fv-2mgg-jv7q)公告固定修复版覆盖，最终安装审计0告警，实际重新构建通过；未运行 `audit fix --force`。
- 单测首次41通过/1失败：默认未知输出预留4096×3会先触发12k预算，符合预算优先；重试专项以每次1000预留验证确实最多重试2次，保留原断言3次请求，不放宽生产限额。
- 真实Web探针收到一次不合协议响应：明确失败且不执行其操作；保存原生call/result与预算，从同一会话继续成功。原始HTTP body未保存，具体缺失字段无法追溯；已增加只含字段名/异常类型的脱敏诊断，未伪称查明厂商内部原因。
- 远端官方PyPI索引/文件下载先报不可解析、长时间回溯，固定直接依赖后定位为 `files.pythonhosted.org` 读取超时。容器内实测三个镜像均有目标版本，腾讯源0.06秒；构建参数显式切该源后依赖约9秒安装成功，再实际启动通过。未更改远端pip/Docker全局配置。

### 未完成与下一步

- 阶段03：独立Runner、真实Python执行/固定用例/失败定位/自动修复及隔离清理仍 NOT_TESTED；当前接口显式关闭执行。
- 阶段04/05：结构化教育产物、班情导入/策略、完整种子、逐项版本回退、正式提交/导出尚未实现；本阶段批准写入被后端阻断。
- 公网HTTPS URL、反向代理、真实浏览器/Playwright及教师教育审查 NOT_TESTED；未启动浏览器符合AGENTS限制。README已给PC/服务启动与手动检查步骤。
- 长上下文仅做完整教师轮次边界的历史索引，原始消息留库；教育事实的语义压缩仍待后续结构模型，不承诺无限上下文。只支持单API worker；依赖树未锁定，正式交付前另行固定与回归。下一步进入阶段03，不跨阶段扩张UI。

## 2026-10-29：阶段02专项验收 — 九项复验全部PASS

本次仅验收阶段02并修复该范围内缺陷，没有实现后续教育业务、Runner、正式提交或公网发布。前述实施记录保留为历史；本次源码指纹为 `20b2a2bf7f7e37b786befd0a5a603a2530a3298226343e4a7e180fdd89c25b47`。

### 实际修复与验收入口

- 真实复现文件列举缺陷：201个文件位于子目录时，`WORKSPACE_TOO_LARGE`被父层捕获，静默返回200个文件；恰好200个合法文件后出现不支持扩展名时，又会误报超限。新增两项断言先实际得到2 FAIL，再在 `backend/app/workspaces.py` 精确修复计数位置与错误传播；未放宽200文件限额。`test_policy.py`修复后19 PASS，相关完整回归53 PASS。
- 新增 `scripts/verify_stage02.py`：通过真实FastAPI HTTP接口分别运行PC/Web会话，固定`LLM_PROVIDER=bailian`；随机字段只在实际fixture中，未放进教师请求。检验原生调用、真实读取hash、匹配call_id的工具消息、后续模型草稿/最终回复、SIGKILL与重新启动、七类快照一致、拒绝后的真实模型继续、无重复草稿/工具结果。
- `scripts/probe_remote.py --real-startup`：不上传Key，在远端临时容器内用真实Provider配置检验API/前端HTML与全部入口JS/CSS，保存构建镜像ID、源码归档hash和运行结果；此路径不调用远端模型，不以Mock证明启动。
- 负向网络探针初次被现有HTTP代理转为502，服务实际上已明确返回`PROVIDER_HTTP_ERROR`，没有降级Mock。修正探针子进程的`NO_PROXY`后，在不监听的本机绑定端口真实触发连接拒绝，保持原`PROVIDER_UNAVAILABLE`断言。验收脚本也补了中间报告落盘；未修改模型/代理的产品逻辑或全局环境。

### 本次实际命令与结果

| 命令/操作 | 实际结果 |
|---|---|
| `npm --prefix frontend run build` | PASS；TypeScript + Vite 7.3.7，1580 modules；JS `index-6QFvVWe9.js`、CSS `index-CTLBFxWQ.css` |
| `.venv/bin/python -m pytest backend/tests/unit/test_agent_loop.py backend/tests/unit/test_policy.py backend/tests/unit/test_provider.py backend/tests/integration/test_session_resume.py backend/tests/integration/test_api.py -q` | PASS；**53 passed**，1条既有TestClient未来弃用警告；这些离线测试中的Mock/HTTP桩只作补充，不是下列真实能力的依据 |
| `.venv/bin/ruff check backend scripts` | PASS |
| `.venv/bin/python scripts/verify_stage02.py` | PASS；PC/Web真实HTTP、qwen3.8-max共12次成功请求、原生工具8条、强制重启恢复、真实连接拒绝报错；全部`mock=false` |
| `npm --prefix frontend run dev -- --port <随机空闲端口> --strictPort` | PASS；实际启动Vite，`/`、`/@vite/client`、`/src/main.tsx`均HTTP200，随后停止 |
| `bash scripts/start-desktop.sh --workspace <临时教师目录> --no-browser --port <随机空闲端口>` | PASS；实际启动PC入口，健康200、runtime为`pc / bailian / mock=false`，随后停止 |
| `.venv/bin/python scripts/probe_remote.py <SSH目标> --pypi-index https://mirrors.cloud.tencent.com/pypi/simple --real-startup` | PASS；当前源码多阶段Docker构建、非root容器API与JS/CSS HTTP200；Python3.12.16 / Linux x86_64，Docker29.9.2 / Compose5.6.1；未公开端口，容器/本次镜像/源码已清理 |
| 远端Python3.12容器实际请求百炼`/compatible-mode/v1/models`，未附Key | HTTPS/TLS验证成功，HTTP401；证明出口可达，不冒充鉴权成功或远端模型调用 |

### 证据与逐项判定

- [九项汇总](../.runtime/stage02-acceptance-summary.json)：9 PASS，当前无活动验收run，浏览器/公网URL明确未测。账本累计估算及保守预留¥1.390224，包含此前运行和负向探针预留，不是精确账单。
- [本机真实HTTP/模型/恢复报告](../.runtime/stage02-acceptance-52c404a1a3e2.json)：实际`provider_request_id`/usage/模型名、原生call/result、fixture hash、快照与失败状态。PC读取call `call_6c383f86ba144b659c1e9672`；Web读取call `call_cf2ab342bb14469380ffb58d`。PC进程33666→33737，Web进程33762→33904；SIGKILL前后session/messages/runs/tool_calls/drafts/approvals/usage逐项一致，之后真实模型复述随机字段，草稿和结果未重复。
- [Vite与PC入口](../.runtime/stage02-entrypoints.json)及`.runtime/stage02-entrypoints.log`：真实进程HTTP状态记录。
- [远端运行报告](../.runtime/stage02-remote-425f17b3c9ff4c669f853788a76c7efc.json)：镜像ID `sha256:f2023b250e3d1d16dfe40f72fe2e16e336eeb083182ff0bf3cfd7d8769041b2a`；运行时`mock=false`，未传Key/未调远端模型/未发布端口。

用户九项要求逐项结果见 ACCEPTANCE 第7节，均有本次执行证据。首次探针已完成PC/Web真实链路，但未落最终报告；本次修正验收脚本后完整重跑，以上使用第二次完整保存的报告，所有调用成本仍留在原SQLite预算中，没有通过换库清零。

浏览器渲染/Playwright、公网HTTPS和真实Python Runner仍 NOT_TESTED，未把它们计入上述PASS。未修改`.env`、锁文件、系统/服务器全局配置或用户原有PLAN修改；未Git提交或推送。

## 2026-10-29：阶段02 Review — 仅修复P1草稿取回与P2工具超时

本轮只修改 `backend/app/agent.py`、`tools.py`、`domain.py` 及相关回归测试、PROGRESS/ACCEPTANCE。保留已有未提交内容；没有前端/教育业务/Runner/发布功能变更，没有改配置、依赖或提交Git。当前验证对应文件hash见[本轮汇总](../.runtime/stage02-review-summary.json)；前面的九项验收对应历史源码，不能直接作为当前版本全量PASS。

### P1：长上下文后的草稿正文不可取回 — PASS

- 根因：36,000字节以上历史按完整轮次裁剪，正文只留SQLite，索引只有ID/path/hash；`read_file`仅读正式文件，模型无取回草稿正文的工具。
- 最小修复：注册L0只读 `read_draft(draft_id)`，复用服务端会话归属校验，返回完整正文与版本/base_hash；裁剪索引提示使用它。参数仍严格校验，无法传另一个session_id伪造归属，不改变草稿/正式文件。
- 回归：PC/Web各建立约20KB真实SQLite草稿，确实形成超过36,000字节历史；关闭旧Store并重开后新轮上下文无正文标记，按索引ID读取草稿，逐字节断言完整正文，然后保留原稿追加说明，核对父版本与正式文件未改变。另验证跨会话读取被拒、正文不泄露、额外参数被拒。测试Provider为显式协议桩，不冒充真实模型。
- 额外真实API：[百炼专项报告](../.runtime/stage02-review-live-draft.json)。测试夹具为直接准备的合成草稿/历史，明确不是模型生成；历史40,214字节，存储关闭重开，裁剪输入中无随机标记。真实 `qwen3.8-max` 原生调用 `read_draft`，工具返回完整正文与预期一致，最终回复包含仅在正文末尾的随机标记；实际usage估算¥0.075060。该探针只证明真实取回；保留全文续改由上述完整正文回归验证。

### P2：声明超时未生效，文件操作阻塞事件循环 — PASS

- 根因：Loop在SQLite事务内同步调用整个handler；5秒声明没有用于调度，主动时间也等返回后才增加，取消无法及时执行。
- 最小修复：文件列举/读取及diff改为后台只读准备，等待时不持有SQLite事务；采用 `min(工具超时, run剩余主动时间)` 限时并提前持久化次数/时间预留。只有仍处于RUNNING/PENDING的调用，才在主循环原子保存草稿/审批/工具结果；超时报TOOL_TIMEOUT并使run失败，run时间耗尽则TIME_BUDGET停止。超时/取消后不执行准备结果的落库阶段。
- 回归：生产默认5秒限额下真实读取注入5.1秒延迟，5.006622秒进入FAILED/TOOL_TIMEOUT，10ms心跳在0.013895秒触发；80ms剩余预算同样限制文件工具。分别检查迟到的草稿与审批准备不能写库、不能把超时结果改成成功；ASGI实际健康/取消路由在读取未结束时响应，健康0.001185/0.000815秒，取消0.001291秒，迟到返回后结果不变。这些是测试环境数据，不是生产延迟承诺。
- 边界：Python无法强杀已进入底层阻塞I/O的线程；该只读操作可能在后台继续，但其迟到结果被丢弃，不能追加草稿/审批或覆盖终态。本轮没有引入子进程执行器或扩大到阶段03。

### 实际命令与证据

```bash
.venv/bin/python -m pytest backend/tests/unit/test_agent_loop.py backend/tests/unit/test_policy.py backend/tests/unit/test_provider.py backend/tests/unit/test_tool_timeouts.py backend/tests/integration/test_session_resume.py backend/tests/integration/test_api.py -q --junitxml=.runtime/stage02-review-tests.xml -o junit_family=xunit1
.venv/bin/ruff check backend/app backend/tests
git diff --check
```

结果：**62 passed**，1条既有Starlette TestClient未来弃用警告；ruff和空白检查通过。新增9个回归案例，修复前已实际复现6个FAIL（P1两端2个、P2四个），保留断言后通过。完整测试与计时属性见[JUnit报告](../.runtime/stage02-review-tests.xml)，真实API命令和脱敏结果见本会话及专项JSON；没有把合成历史或协议桩计作真实API证据。

当前完整九项HTTP/PC/Web/远端验收、浏览器、前端构建、隔离Runner均未在本轮重跑，保持NOT_TESTED；本次结论仅覆盖两项修复及相关后端回归。无需为纯后端修复重新做前端/部署工作。

## 2026-10-29：阶段03 — Python真实验证闭环

开始时 `git status --short` 为空；按 `prompts/03-verification.md` 实现验证、Runner与必要Agent/UI接线。未修改AGENTS、PLAN、生产配置、`.env`、依赖/锁文件或CI；未提交/推送Git，未开发完整教育界面或正式发布。

### 实现与主要文件

- `backend/app/verification/models.py`：严格Pydantic的TestCase/TestSpec/CaseResult/VerificationReport，逐用例记录输入、expected、actual、stdout/stderr、退出码、耗时、状态、错误及执行证据。stdin/stdout契约精确比较，换行也是规格的一部分。
- `verification/service.py`：固定累加基准n=0/1/5与教师冻结规格，期望值在候选容器之外比对；报告指纹绑定代码Hash、测试Hash、不可变镜像ID及Runner策略Hash。报告保留历史，代码/规格/镜像/策略变更使旧资格过期；只有最新完整成功报告才可待教师审核。
- `runner/docker_runner.py`、`manager.py`、`Dockerfile`：独立可信Manager，仅私有鉴权Unix socket；公网API使用`verification/runner.py`，不持有Docker Socket。候选每用例一次性容器、UID10001、无网络、只读根、默认seccomp、cap-drop、no-new-privileges，0.5CPU/128MiB内存与相同swap总额/32pids/64FD/16MiB tmpfs；stdout/stderr各64KiB，单例2秒、整套30秒。超时/取消删除整个容器；Manager重启回收标记孤儿；清理失败关闭执行器。
- `agent.py`、`tools.py`：真实失败报告按原call_id回传；上下文始终提供现有草稿/规格ID；模型只改代码，再用同一冻结规格重测。按会话+路径持久化两次修复额度与失败Hash，重启/新run不重置；两次修复仍失败立即STOPPED/REPAIR_LIMIT，重复失败Hash报NO_PROGRESS。正式文件Diff保留，新增Python修复Diff对照父候选。
- `api.py`、`domain.py`、`config.py`、`storage.py`：教师冻结规格API、资源归属、只读报告与有效状态、SQLite规格/报告/修复记录；规格不能由Agent工具改写。重新测试开始即撤销旧资格，不能在执行器故障后沿用旧PASS。整组Python候选有失败/漏测/过期时阻断待审请求，不能隐藏失败题；正式批准仍返回PUBLISH_NOT_READY。
- `frontend/src/App.tsx`、`api.ts`：沿用现有草稿区区分未测/失败/超时/过期/用例通过，展开用例、日志、退出码、版本与修复Diff。仅按ui-ux轻量流程接线，按web-design-guidelines做源码Review；真实浏览器尚未验证。
- `backend/tests/unit/test_verification_policy.py`、`integration/test_verification.py`、`scripts/verify_stage03.py`：策略回归与必须连接真实Manager的容器测试；缺环境直接失败，不skip，不使用执行Mock。脚本可临时构建Manager、转发Unix socket、注入重启故障并清理资源。README补充配置、教师API和复跑入口。

### 环境阻塞与排错

- 本机`docker info --format '{{.ServerVersion}}'`实际失败：daemon socket不存在。没有启动本机Docker或用裸subprocess降级；向用户说明后，在用户提供的已整备SSH主机使用临时Manager/容器验证。没有上传模型Key、发布端口、改既有服务或安装宿主依赖。
- 首轮真实容器15 PASS/1 FAIL：客户端取消后下一作业429。修复为显式私有DELETE按job_id取消并等待完整清理，不单靠HTTP断连；原断言保留后通过。
- 进程限额测试曾因同时启动大量独立Python解释器先触发128MiB内存限制而失败。改为fork共享只读页、子进程pause，专门触发32pids；CPU/内存/pids/swap从候选cgroup实际读取断言，没有放宽生产限额或删除隔离断言。
- 长文本恢复回归发现新修复Diff重复回传正文耗尽预算；仅为Python代码保存独立repair_diff，保留原正式文件Diff与父版本语义，所有原回归断言恢复通过。
- 首次真实模型探针因当前上下文没有草稿ID，尝试猜测ID，最终STEP_BUDGET停止。新增真实草稿/规格索引；原失败调用与预算留库，报告保存在`.runtime/stage03-live-model-failed-no-index.json`。后续探针已真实修复通过，但脚本误把RESERVED_UNKNOWN预留也当成功请求，缺请求ID而报错；改为分别核验成功请求ID/usage与未知预留，不把未知用量冒充实耗，保留原证据`.runtime/stage03-live-model-recovered-with-unknown.json`。

### 实际验证

```bash
.venv/bin/python -m pytest backend/tests/unit backend/tests/integration/test_api.py backend/tests/integration/test_session_resume.py -q --junitxml=.runtime/stage03-regression.xml -o junit_family=xunit1
.venv/bin/python scripts/verify_stage03.py <用户提供的SSH目标> --real-model
npm --prefix frontend run build
.venv/bin/ruff check backend runner scripts/verify_stage03.py
git diff --check
```

离线策略/相关后端回归 **72 PASS**，真实容器回归 **19 PASS**（合计91项）；前端TypeScript/Vite构建、ruff、diff空白检查通过。离线控制流Provider为显式测试桩；真实容器里的候选Python实际执行；百炼探针单列，不混淆三类证据。既有Starlette TestClient弃用警告1条，未升级依赖。

证据：[相关回归JUnit](../.runtime/stage03-regression.xml)、[真实容器JUnit及逐用例报告](../.runtime/stage03-real-tests.xml)、[本轮汇总与源码Hash](../.runtime/stage03-summary.json)、[真实模型纠错](../.runtime/stage03-live-model.json)、[运行日志](../.runtime/stage03-run.log)。最终模型与清理结果见ACCEPTANCE第9节。

### 边界与下一步

本阶段核心验证无剩余P0阻塞。隔离Manager为独立按需配置组件，本次临时验收资源会清理；未配置的PC/Web实例仍RUNNER_UNAVAILABLE，不暗中启用宿主执行。容器共享内核，持Docker权限的Manager属于高信任面；仅在专用可信宿主单实例运行，不据此宣称任意敌意代码生产平台。

阶段04的结构化教案、完整示例/三档题清单和教育审核，以及阶段05的正式提交/导出/公网HTTPS仍NOT_TESTED。本阶段没有把原题B2/D4的完整教育能力提前标PASS。测试规格编辑界面未开发，当前由教师API冻结。浏览器/Playwright未运行：遵守未获明确授权不启动浏览器的规则。手动验收：配置隔离器与教师规格→发送验证修复需求→展开草稿报告核对具体失败case/日志→检查修复Diff及新PASS→改代码后确认旧报告“已过期”，未通过的候选不能请求待审；正式写入仍被阻断。

最终真实模型与清理：汇总PASS；qwen3.8-max会话`5e56151eaf664478a6bb417b35427b49`共6次成功请求/5次原生调用，真实报告OUTPUT_MISMATCH→PASS，冻结规格Hash不变。成功探针估算¥0.258612、未知预留0笔；阶段03所有探针（包括失败）在原SQLite账本累计估算/保守预留¥2.350224，未知预留5笔，不是精确账单。中途另一次探针遇PROVIDER_UNAVAILABLE三次后按预算停止，保留`.runtime/stage03-live-model-network-failed.json`；没有清零重试预算或切换Mock。工具说明与索引补充正式base_hash语义，最终新探针没有版本冲突。

最终19项真实容器回归耗时45.62秒，72项相关后端回归7.34秒；前端构建产物JS `index-BCwFtBGv.js`。汇总记录源码Hash与镜像ID。再次查询阶段03候选/Manager容器为空；临时Manager镜像标签和源码目录清理，不保留正在运行的验收服务。

## 2026-10-29：阶段03对抗性验收与真实stdin修复

本轮开始工作区保留上一轮阶段03未提交改动，全部保留；只新增对抗测试、修正Runner执行适配、给现有验收脚本增加证据前缀并更新PROGRESS/ACCEPTANCE。未改既定用例的input/expected、执行资源限制或原有断言；未修改前端、生产配置、`.env`、锁文件或CI，未提交/推送。

### 实际发现与修复

- 真实Runner首轮 **23 PASS / 3 FAIL**。正常循环程序使用`sys.stdin.buffer.readline()`报`AttributeError: '_io.StringIO' object has no attribute 'buffer'`；使用`os.read(0,64)`或继承stdin的子进程得到空输入并报ValueError。三份报告退出码均为1，属于正确程序被执行适配层误判，并非代码/测试本身错误。原始证据保存在`.runtime/stage03-adversarial-before-real-tests.xml`和对应before日志/汇总。
- 根因在`runner/docker_runner.py`的容器内BOOTSTRAP：先消费JSON，再把Python的`sys.stdin`替换成StringIO，没有给FD 0及子进程提供真实输入。修复为在同一受限容器的tmpfs写入本次代码快照，以固定Python解释器/参数启动候选，使用真实stdin管道传入冻结输入；stdout/stderr仍由容器外捕获，expected仍不进入容器。子进程负返回码转为对应信号退出码，超时继续删除整个容器进程树，所有原隔离参数保持不变。Runner源码Hash自动变化，因此旧报告不能沿用。
- 修复stdin后 **25 PASS / 1 FAIL**：新增tmpfs探针在磁盘达到16MiB后捕获write的ENOSPC，却未捕获close再次flush的ENOSPC。修正探针为整个文件生命周期捕获OSError；继续严格要求errno=28、零capabilities、no-new-privileges=1、seccomp=2、nofile=64/core=0，未改限额或期望值。中间结果保存在`.runtime/stage03-adversarial-fixed-stdin-real-tests.xml`及对应日志。

### 新增对抗覆盖与复跑入口

在`backend/tests/integration/test_verification.py`原19项上新增7项：三种真实stdin方式、正确输出后再抛异常仍失败、零次循环错误不能被正常用例掩盖、Manager鉴权/禁止参数拒绝、实际权限/FD/core/tmpfs限额。原Hash失效、同规格修复与修复耗尽测试增加JUnit证据属性，没有放宽断言。

`scripts/verify_stage03.py`新增`--evidence-prefix`，保存本轮独立证据，不覆盖首轮阶段03历史报告；汇总增加测试源码Hash，便于确认实际运行的是哪套断言。

```bash
.venv/bin/python scripts/verify_stage03.py <用户提供的SSH目标> --evidence-prefix stage03-adversarial-before
.venv/bin/python scripts/verify_stage03.py <用户提供的SSH目标> --evidence-prefix stage03-adversarial --real-model
.venv/bin/python -m pytest backend/tests/unit backend/tests/integration/test_api.py backend/tests/integration/test_session_resume.py -q --junitxml=.runtime/stage03-adversarial-regression.xml -o junit_family=xunit1
.venv/bin/ruff check runner backend/tests/integration/test_verification.py scripts/verify_stage03.py
git diff --check
```

最终结果、十项逐条判定及关键stdout/stderr/退出码/耗时见ACCEPTANCE第10节和`.runtime/stage03-adversarial-evidence.json`。本轮真实候选均在远端私有Manager的一次性受限容器执行；不在API/本机宿主裸跑，不发布公网端口，不上传模型Key。不可修复分支使用受控连续错误提案来确定性触发Agent Core两次修复上限，真实模型自主修复分支单独记录，二者不混淆。

最终复验：26项真实Runner集成在70.16秒内全部通过；72项相关后端回归在7.37秒内全部通过，均0失败/0跳过，保留1条既有Starlette弃用警告。真实qwen3.8-max共6次请求/5次工具，原用例下OUTPUT_MISMATCH→PASS，规格Hash不变，估算/保守预留¥0.261036（未知0笔）。最终汇总status=PASS、源码/测试Hash与当前文件一致。十项验收与逐用例数据见[证据JSON](../.runtime/stage03-adversarial-evidence.json)及ACCEPTANCE第10节。容器/镜像标签/临时源码清理后独立查询确认；未保留运行中的服务。

## 2026-10-29：阶段03 P1 — Python后缀大小写绕过验证闸口

本轮保留开始时全部未提交改动。根因为Workspace路径允许规则已使用`suffix.lower()`，但规格冻结、验证、发布/整组候选与Agent完成状态使用大小写敏感的`endswith('.py')`，导致`.PY/.pY`被当作普通文档。

最小修复：在`backend/app/workspaces.py`增加统一的`is_python_path`（取最后后缀并lower），由`api.py`、`verification/service.py`、`tools.py`、`agent.py`复用；同时覆盖修复Diff的Python识别。原始文件名大小写、工作区边界及测试规格保持不变，没有缩窄文件权限来掩盖验证遗漏。

新增回归：`backend/tests/unit/test_verification_policy.py`参数化`.py/.PY/.pY` × NOT_TESTED/RUNTIME_ERROR/STALE × 发布代码/发布同组Markdown，要求VERIFICATION_REQUIRED、审批和审批事件均为空；补充规格冻结API与Agent完成状态。未修复时先实际得到 **14 FAIL / 7 PASS**，证据`.runtime/stage03-suffix-before.xml`；修复后该文件 **34 PASS**。

真实Runner回归在`backend/tests/integration/test_verification.py`参数化三种后缀：异常代码未测时拒绝，实际运行失败仍拒绝，原冻结规格下修复为正确代码后可验证通过；再次编辑后旧PASS过期、新版本未测试均拒绝。同组另一个小写文件即使真实通过，也不能绕过大写文件漏测，所有拒绝阶段无审批记录。

实际命令：

```bash
.venv/bin/python -m pytest backend/tests/unit/test_verification_policy.py -k python_suffix -q --junitxml=.runtime/stage03-suffix-before.xml -o junit_family=xunit1
.venv/bin/python -m pytest backend/tests/unit/test_verification_policy.py -q --junitxml=.runtime/stage03-suffix-policy.xml -o junit_family=xunit1
.venv/bin/python -m pytest backend/tests/unit backend/tests/integration/test_api.py backend/tests/integration/test_session_resume.py -q --tb=short --junitxml=.runtime/stage03-suffix-regression.xml -o junit_family=xunit1
.venv/bin/python scripts/verify_stage03.py <已授权SSH目标> --evidence-prefix stage03-suffix
.venv/bin/ruff check backend/app backend/tests
git diff --check
```

相关后端回归96 PASS，34项策略测试包含在这96项内，不重复累计。真实Runner结果与证据见ACCEPTANCE第11节。本轮不调用真实模型、不修改前端、不启动浏览器；未改生产配置、`.env`、依赖/锁文件或CI，未提交/推送Git。

最终结果：96项相关后端回归（约7.64秒，含34项策略测试）+29项真实Runner集成（约87.61秒）=125 PASS，0失败/0跳过。`.py/.PY/.pY`均真实失败/通过/编辑失效，所有拒绝场景审批数0，整组检查包含大写文件；源码/测试Hash核验一致。ruff与git diff --check通过。证据见ACCEPTANCE第11节及`.runtime/stage03-suffix-*.xml/json`。远端候选/Manager容器、镜像标签、临时源码目录独立查询为空，SSH控制连接已关闭；本轮不保留运行服务。
