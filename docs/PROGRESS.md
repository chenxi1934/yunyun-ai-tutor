# 开发进度与真实验证记录

> 不要把计划写成已完成。由 Codex 每阶段更新，写明事实和证据。

| 阶段 | 状态 | 验收证据 | 阻塞/风险 |
|---|---|---|---|
| 1. 设计/骨架/预部署 | PARTIAL：设计/骨架/远端临时容器验证完成 | 阶段02命令与下方证据；远端 Python 3.12 / Node 22 镜像构建及进程恢复通过 | 原阶段缺口已在05补齐：公网HTTPS与持续Runner |
| 2. Agent Core | 已实现；专项修复归档阈值与验证工具指令冲突 | 阶段04历史151项；阶段05当前172项回归；真实模型整课为上轮证据 | 正式交付/浏览器已在05完成；人工教育审查待完成 |
| 3. 正确性验证 | 已实现；真实隔离、错误/修复/过期阻断 | 阶段03第11节125项历史验收；阶段04另有真实回归 | 阶段05已部署持续Manager；保持候选按次创建/清理 |
| 4. 教育能力 | 两班情与大学真实生成、逐项文案修订及复验PASS | 151后端+8真实教育集成；最终15程序/51用例PASS；专项验收末节有差异与完整证据 | 真实教师审核仍PENDING；教育UI/正式发布已在05验收 |
| 5. PC/Web | 已实现；五项评审修复专项回归PASS | 当前172后端+6真实容器+22浏览器控制流；双端主线三场景/51用例为上轮证据 | 本轮修复未部署，公网新版本NOT_TESTED；人工教学审查/原生弹窗待验收；见末节 |
| 6. 回归与交付 | NOT_STARTED | 最终面试全矩阵、视频与现场验收尚未开展；功能回归和Web链接见05 | 依赖前五阶段与人工教育审核 |

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

## 2026-10-29：阶段04 — 教育垂类核心与完整循环课

起始`git status --short`为空。已阅读AGENTS、原始要求、PLAN/PROGRESS、阶段04 prompt、Agent/Registry/Store/API及真实Runner实现；本轮未使用多Agent、未修改前端、未启动浏览器或本地开发服务，未改.env/锁文件/生产配置，未提交或推送Git。

### 本轮实现

- `backend/app/education/models.py`：严格Pydantic教案、目标/可观察标准、环节、2–3示例、三档题、每题100分评分点、结构化错因；强制45分钟、唯一稳定ID、正确引用和三档各一题。持久化版本在SQLite新增教育实体表，沿用现有Store，不新增迁移脚本或修改现有数据。
- `profiles.py/rules.py/catalog.py`：粘贴文本、UTF-8 JSON/CSV原文上传；上限1 MiB/1000行；三类观察分别保留计数/分母/来源位置/Hash，交集未知不合计，未知人数不算比例，未提供的类别不当作0。负数、小数、约数、重复JSON字段/CSV列、冲突、超分母、乱码均拒绝。只保留汇总白名单，姓名/学号等无关列不持久化、不送模型。
- A班（5未交、3死循环）为`5+8+10+10+10+2`分钟；B班（明确0未交、0死循环、8边界错误）为`2+8+8+15+10+2`分钟。A提供while初值/条件/更新追踪，B更换第二个演示为偶数累加、增加边界支架与边界评分。大学改为不变量/终止性/复杂度目标、嵌套循环示例、约数/素数题，评分为程序50/论证30/复杂度20。不是改班名或语气。
- 错因保留`misconception_type/evidence_ids/basis/trigger/cause/cause_status/teaching_intervention/exercise_ids/stage`。观察只说明行为，所有病因仍为hypothesis；没有同类非零事实的结论只能标predicted。非零观察不得遗漏干预；未知项和事实引用可复查。
- `service.py/render.py`：稳定lesson/item ID、递增revision、父版本、Hash、班情revision、代码/规格/报告关联、逐项教师接受/拒绝与审核记录。单项修订保留旧版本；只改环节不重跑代码，改一题仅重测该题并使关联错因审核失效；班情变化使整体适配/审核失效。历史项目可作为replacement生成恢复草稿，正式文件不动。
- 全部示例/参考解由固定任务契约冻结用例，调用阶段03真实VerificationService/Runner，包含正常、最小/零次与边界；语法错误、输出错误、超时、漏测、过期、执行器不可用均不能成为可交付候选。不可删除失败项、换任务或删减用例过关；通用propose_patch不能绕开教案绑定。模型修复额度仍为每文件两次，不因提新教案/恢复重置。代码PASS不能消除课程风险或自动接受教学内容。
- `education/api.py`及Agent/Registry：导入、结构预览、生成、单项修改、整课验证、逐项审核、历史/草稿JSON、审核后文件组合导出。模型只有读取/提案/受限验证工具；教师审核不注册为工具。导出返回JSON/Markdown/5份Python/用例/报告/manifest映射，所有文件Hash可核；这是已审核**草稿组合**，阶段05再处理正式落盘/ZIP。
- `backend/seeds/core/`现在共7文件，含A班JSON/文本、B班CSV、初中/大学完整结构种子，均标注合成、NOT_TESTED/未审核；读取种子不等于确认班情。README补充API与复跑方法，不开发教育界面。

### 实际验证与排错

```bash
.venv/bin/python -m pytest backend/tests/unit backend/tests/integration/test_api.py backend/tests/integration/test_session_resume.py backend/tests/integration/test_education_api.py -q --tb=short --junitxml=.runtime/stage04-regression-verified.xml -o junit_family=xunit1
.venv/bin/python scripts/verify_stage04.py <已授权SSH目标> --real-model --evidence-prefix stage04-verified
.venv/bin/ruff check backend runner scripts/verify_stage03.py scripts/verify_stage04.py
git diff --check
```

第一条已实际147 PASS，0失败/0跳过（8.48秒），只有既有Starlette TestClient弃用警告。真实隔离/最终模型结果待下方补记，不以先前源码证据冒充最终源码。

本轮发现并修正：①原API种子测试固定期望2文件，与本阶段明确扩为7文件冲突，改为逐一校验确切7个路径，未弱化为宽松计数；②任务测试契约检查原先在逐项执行时才做，改为全课预检后才执行，Runner未配置也能先指出规格删减。中间2 FAIL/144 PASS报告保存在`.runtime/stage04-regression-before-fixes.xml`，最终没有覆盖为成功。

真实模型初次（`stage04-live-model.json`，会话`4ce3fdaed8eb4aec84f5c19aa8c4fbb7`）发生一次PROVIDER_TIMEOUT，原60秒预算与未知费用预留保留，重试后工具链和5份代码通过；但内容与规则草稿完全相同，**不能作为模型自主教育内容生成的证据**。中间重复验收`stage04-final-*`也保留，仅作当时源码记录。最终探针已加强为必须改写至少两个具体课堂活动、两个示例讲解，并对实际JSON差异断言；结果另行补记。结构格式失败→修复由明确标识的ScriptedProvider单测验证（INVALID_LESSON字段位置、原参数及成功后新版本可查），不冒充真实模型格式故障。

### 当前边界与手动验证

尚未执行真实教师的教育审查；自动化中的accept/reject均是显式合成教师动作，只验证机制。课程AST/术语规则只能发现首版已定义风险，不能证明教案适合所有学生。普通文本解析是窄范围汇总识别，不是任意自然语言或学生源码自动诊断；未识别/冲突数据请教师核实。

本轮不验收公网HTTPS、持续Runner、完整教育UI、正式创建/覆写/恢复教师文件或ZIP；这些继续归阶段05。容器共享宿主内核，Manager持Docker权限，仍需专用可信宿主；API与候选无Docker Socket/Key。服务器仅用于授权的临时隔离测试，无发布端口，结束后清理本次资源；Key留在本机。

浏览器/Playwright **NOT_TESTED**：本轮纯后端且仓库禁止未经明确要求启动浏览器。后续手动：选初中/初二并导入A→确认5/3与交集未知→生成并检查45分钟/2示例/3档题→查看每份代码case输入/期望/实际与报告Hash→故意改坏一题，确认失败/旧报告过期且导出拒绝→修复重测与逐项拒绝/接受→对比B的15分钟边界环节与大学的不变量/复杂度→正式落盘留阶段05。

补充实际排错：加强探针后，会话`05e5e52ecd454cb7908865f0963884de`真实出现`plan.stage`字段缺失，模型根据INVALID_LESSON字段定位改为初中并保留新提案；活动与示例讲解已有实际改写。该run因一次模型超时的未知费用/输入预留，加上同轮重复整课JSON，达到80k输入预算，正确STOPPED/BUDGET_EXCEEDED，**没有执行报告，也不记为端到端PASS**。证据`.runtime/stage04-verified-live-model.json`和FAIL汇总完整保留。

据此为Agent增加教育同轮上下文归档：只折叠已完成交换，保留当前教师需求与最后成功提案的完整工具协议，提供班情Hash/事实及成功/失败call索引；所有原始消息、参数、错误与预算仍在SQLite。相同失败历史的下次输入预留从44,906降为25,773；没有调整80k输入/12k输出/12步/费用/60秒模型时限。新增单测精确检查原始历史字节不变、错误可见、班情Hash与最新协议保留。最终源码离线结果改为**148 PASS**（8.49秒），证据`.runtime/stage04-complete-regression.xml`；真实复验改用`--evidence-prefix stage04-complete`，待下方最终结果。

### 最终结果（最终源码，非前次累计）

- **148项后端回归（8.49秒）+37项真实容器集成（188.54秒）=185 PASS，0失败/0错误/0跳过**。ruff与`git diff --check`通过；只有既有Starlette弃用警告，未升级依赖。最终命令使用`stage04-complete`前缀，完整源码/集成测试/驱动脚本Hash已逐一与汇总核对相同。
- 真实百炼`qwen3.8-max`会话`9b961324592840cea00e6f993ca85c1b`、run `1f498cfb76b64e809fecf8cc36896a16`：5次成功请求，4次工具调用（context→格式错误提案→修复提案→verify_lesson）。实际提案曾缺失`plan.stage`，服务422/INVALID_LESSON给出字段位置；模型修正后6个环节activity、2个示例explanation均与规则草稿不同。全部2示例+3参考解真实PASS；candidate_ready=true、teacher_review_status=PENDING、delivery_ready=false，未冒充教师审核。估算¥0.564432、未知预留0笔；之前失败探针的未知预留仍保留在同一实例账本，没有重置预算。
- 5份真实报告：`25398062f84148a6913debdc19235554`、`f36482d527d64c29891db74f7d9f3250`、`2f1dc65270d14207a093db6e833e004f`、`eaf838aa0fc047fcb0bec632a37df465`、`9583a702f36445c091890d66f1d87c43`。代码/规格/镜像/策略Hash及逐case完整证据在最终JSON/XML。
- 可查看：[实际模型完整记录](../.runtime/stage04-complete-live-model.json)、[单独教案草稿JSON（教师待审）](../.runtime/stage04-complete-lesson.json)、[A/B/大学真实课例对照（合成教师操作已标明）](../.runtime/stage04-complete-comparison.json)、[源码Hash/Runner与清理汇总](../.runtime/stage04-complete-summary.json)、[148项后端JUnit](../.runtime/stage04-complete-regression.xml)、[37项真实容器JUnit](../.runtime/stage04-complete-real-tests.xml)。这些为忽略的本机运行证据，不提交Git；源码中保留可复跑脚本。
- 执行镜像`sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159`、策略Hash`403190056f014b4843a67a3a9824fbaf06666f4b683fd0317a0a1bb5b70da214`。最终孤儿回收探针PASS；脚本结束后又独立只读查询：候选/Manager容器、临时Manager镜像标签和`/tmp/yunyun-stage03-*`目录均为空。无公网端口、无远端Key、无持续服务，SSH控制连接随后关闭。

本阶段无剩余业务/API验收P0。真实教师对教学文字/难度/评分的审查、教育界面、正式教师目录写入/恢复、ZIP与公网部署继续NOT_TESTED，不能由这185项或模型文字代替；下一步为阶段05。当前工作区改动未提交/推送，未修改规则文档。

## 2026-10-29：阶段04专项验收 — 两班情真实生成与学段对照

本轮开始时存在上阶段完整未提交改动，全部保留；不提交/推送、不改规则/.env/锁文件/生产配置，不扩展学生端、教务或其他学科。新增可复跑专项探针`scripts/accept_stage04.py`，分别为初中A、初中B、大学A调用真实百炼，再核对每份代码的冻结契约、Hash及逐case实际结果；不再把规则样例的对照称作“两班情真实模型生成”。三组都保持主题《循环结构》、45分钟、40人、已学条件语句；A为5未交/3死循环且交集未知，B为0未交/0死循环/8边界错误，大学复用A事实仅切换stage/grade。

实际发现与最小修复：成功提案加规则模板的同轮历史只有22,538字节，低于24,000字节归档阈值；之后模型连接失败的保守预留导致预算提前耗尽。最终只将教育归档触发阈值改为16,000，仍保留当前教师请求与最后成功提案的完整工具协议。中间尝试移走最后协议造成模型重读/重复生成，已回退该尝试；新增/强化测试保证最新协议、原始SQLite历史、错误索引与完整产物都保留。没有提高80k输入、12k输出、12步、模型60秒或任何代码用例/限额。

本机直连官方模型接口发生连续PROVIDER_UNAVAILABLE/超时，所有未知费用预留仍在原SQLite；未切Mock。用同上下文、16-token上限的诊断请求得到真实qwen3.8-max HTTP200/length，明确只作网络诊断且没有执行工具；不能据此判教案通过。最终专项探针使用现有SSH服务器仅转发官方HTTPS的TLS字节，本机httpx保留官方SNI/证书校验和API Key，服务器未收到Key文件或明文HTTP。该路径只在验收脚本显式传YUNYUN_ACCEPT_MODEL_SOCKET时启用，没有修改产品Provider默认配置。后续部署仍需验证直连模型链路的稳定性。

实际命令：

```bash
.venv/bin/python -m pytest backend/tests/unit backend/tests/integration/test_api.py backend/tests/integration/test_session_resume.py backend/tests/integration/test_education_api.py -q --tb=short --junitxml=.runtime/stage04-acceptance-pass-backend.xml -o junit_family=xunit1
# SSH控制连接复用已有授权；下例socket为本轮临时路径，API Key不传服务器
ssh -S .runtime/ssh_control -N -L <本机临时model.sock>:dashscope.aliyuncs.com:443 <已授权SSH目标>
YUNYUN_ACCEPT_MODEL_SOCKET=<本机临时model.sock> .venv/bin/python scripts/accept_stage04.py <已授权SSH目标> --real-model --evidence-prefix stage04-acceptance-pass
.venv/bin/ruff check backend/app/agent.py backend/tests/unit/test_education.py scripts/verify_stage03.py scripts/accept_stage04.py
git diff --check
```

后端回归已149 PASS（8.51秒，既有Starlette弃用警告1条）；最终真实模型/Runner与具体差异结果见随后补记。脚本另支持`--model-only`仅重跑模型，相关汇总会明确pytest=NOT_TESTED，不复用成“本次已重跑”。`stage04-acceptance-*`、`stage04-acceptance-final-*`、`stage04-acceptance-retry-*`、`stage04-acceptance-tls-*`失败记录保留，均不充当最终源码PASS证据。

### 专项验收最终结果与文案审校

最终分别用真实qwen3.8-max生成初中A、初中B、大学A三套结构化教案（两班除观察数据外保持40人、已学条件语句、主题/课时/模型相同）。三套原始生成均走`get_education_context → propose_lesson → verify_lesson`并COMPLETED，15份代码/51条冻结用例真实通过，估算¥1.409208；这次真实生成证据是`.runtime/stage04-acceptance-final2-live-model.json`，不是旧规则样例或Mock。

**代码通过后继续读文字，仍发现了真实AI错误。** 例如把Python `for/range`写成`i`自动变为`n+1`再判断退出，大学参考说明把n=0时递减量写为-1，以及把素数计数的保守上界当作所有候选都会取满的实际次数。这些错误不能由stdout用例自动发现。最终通过现有`EducationService.revise`逐项修订：保留for迭代器耗尽与while条件判断的区别，补齐不变量初始化/保持/退出、终止性及准确复杂度说明；保持代码、冻结规格、评分点和时间不变。原模型稿与每项before/after、parent/revision均保存。修订由自动验收执行，**不是教师正式审批，也不冒称模型首次生成已正确**。

本轮源码最小修复还包括：将旧逐文件验证指令限定为独立草稿，完整教案明确使用批量verify_lesson；0人未交不再创建补交环节；大学参考解缺乏实际论证时阻断候选；Markdown导出不再丢掉练习的参考解说明。对应文件为`agent.py/tools.py`、`education/rules.py/render.py`、大学结构种子及相关测试。新增`accept_stage04.py/recheck_stage04.py`保留可复跑过程；没有改冻结输入/期望或执行限额。

最终文本版本与实际差异：

| 维度 | 初中A | 初中B | 大学A |
|---|---|---|---|
| 学情 | 5未交、3死循环；交集未知 | 0未交、0死循环、8边界错误 | 同A，仅切换大学/大一 |
| 六环节分钟 | 5/8/10/10/10/2=45 | 2/8/8/15/10/2=45 | 5/8/10/10/10/2=45 |
| 课堂示例 | count、while sum | count、for even_sum | sum不变量、pairs嵌套计数 |
| 三档题 | countdown/even_sum/multiples | 同三题，改用边界支架与评分重心 | sum/divisors/primes |
| 评分 | 25初值条件/35更新结果/20边界/20追踪表 | 25初值条件/35更新结果/40边界 | 50程序/30不变量及终止证明/20复杂度 |
| 最终教案revision | 2 | 5 | 7 |
| 最新真实执行 | 5程序17用例PASS | 5程序18用例PASS | 5程序16用例PASS |

最终使用新的临时隔离器再次执行**全部15份代码/51条用例**，不是沿用旧报告；新报告ID与原报告ID不重合，代码Hash与原生成稿相等，冻结规格ID/Hash及断言不变。原报告仍作为历史保留。A的不同学生人数保持未知，不能把5+3直接计作8；B的8只对应有来源的边界错误观察。预警的evidence_ids可回溯到相应事实、count与原JSON位置/Hash；cause_status始终hypothesis，缺少证据的类型明确predicted。

实际结果：**151项后端回归PASS（8.59秒）+8项真实教育集成PASS（102.64秒）**，0失败/0错误/0跳过；另有三次真实生成及最终独立重跑的15份代码/51用例PASS，不把用例数累计成pytest数量。ruff/git diff --check通过。最终审校快照的teacher_review_status仍PENDING、delivery_ready=false；本次自动审校不代替真实教师判断。

最终复验命令（源码中脚本可复跑；先生成新会话，再以该生成文件作为source，拒绝覆盖已有后续修订）：

```bash
.venv/bin/python -m pytest backend/tests/unit backend/tests/integration/test_api.py backend/tests/integration/test_session_resume.py backend/tests/integration/test_education_api.py -q --tb=short --junitxml=.runtime/stage04-acceptance-final2-backend.xml -o junit_family=xunit1
YUNYUN_ACCEPT_MODEL_SOCKET=<本机临时model.sock> .venv/bin/python scripts/accept_stage04.py <已授权SSH目标> --real-model --evidence-prefix stage04-acceptance-final2
YUNYUN_ACCEPT_SOURCE=.runtime/stage04-acceptance-final2-live-model.json .venv/bin/python scripts/recheck_stage04.py <已授权SSH目标> --recheck-artifacts --model-only --evidence-prefix stage04-acceptance-corrected
.venv/bin/ruff check backend runner scripts/accept_stage04.py scripts/recheck_stage04.py scripts/verify_stage03.py scripts/verify_stage04.py
git diff --check
```

最后一条脚本在本次**不调用模型**，`model_called=false`；它修订已生成产物并真实重跑代码，pytest明确NOT_TESTED，回归结果来自前两条的独立JUnit，不能假称重跑了回归。最终业务源码/测试/驱动Hash、修订脚本Hash与来源生成文件Hash均已核对。

证据：[真实生成完整记录](../.runtime/stage04-acceptance-final2-live-model.json)、[最终A/B/大学结构化差异与参考说明](../.runtime/stage04-acceptance-corrected-artifact-recheck-comparison.json)、[逐项before/after、父版本与最新执行报告](../.runtime/stage04-acceptance-corrected-artifact-recheck.json)、[A教案](../.runtime/stage04-acceptance-corrected-artifact-recheck-junior_A-lesson.json)、[B教案](../.runtime/stage04-acceptance-corrected-artifact-recheck-junior_B-lesson.json)、[大学教案](../.runtime/stage04-acceptance-corrected-artifact-recheck-university_A-lesson.json)、[151项JUnit](../.runtime/stage04-acceptance-final2-backend.xml)、[8项真实集成JUnit](../.runtime/stage04-acceptance-final2-real-tests.xml)、[最终来源Hash与清理汇总](../.runtime/stage04-acceptance-corrected-summary.json)。全部为忽略的本机运行证据，未提交Git。

实际输出摘要（均exit_code=0）：A sum输入5→stdout `15\n`；A count输入0→stdout空串；B even_sum输入6→`12\n`；大学pairs输入4→`10\n`、divisors输入12→`6\n`、primes输入10→`4\n`。逐case的stdin/expected/actual/stdout/stderr/耗时/退出码及代码/规格/运行时/策略Hash均在上述报告。执行镜像仍为`sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159`。

最终独立查询确认候选/Manager容器、临时Manager镜像标签及远端源码目录为空，无公网端口。只剩本机运行证据与原费用账簿；本轮没有提交/推送，没有正式覆盖教师文件。真实教师审核、浏览器/Playwright、教育UI、正式发布/ZIP仍NOT_TESTED；本轮未修改前端且未获浏览器验收请求。直连模型长响应仍有网络稳定性风险，最终真实生成通过明示的端到端TLS转发完成，产品默认Provider未被替换。

## 2026-10-29–30：阶段05 — PC/Web完整功能交付与真实验收

开始时Git干净。按 `prompts/05-pc-web.md` 实施，共享React UI和原有Python Agent Core；未提交/推送Git，未改本地 `.env`、锁文件、既有CI或无关业务。用户本轮要求包括实际启动、部署和浏览器验收，故启动了本机服务与指定VPS上的本项目服务。

### 本阶段实现

- `backend/app/delivery.py`、`delivery_api.py`、`workspaces.py`：教师专用正式提交、逐文件Diff/原Hash/新Hash审批快照、真实创建/覆盖/删除、版本冲突拒绝、目录句柄/O_NOFOLLOW与原子文件替换。模型没有批准能力；拒绝不落盘。
- `storage.py`、`agent.py`、`api.py`、`verification/service.py`：提交日志与审批恢复；部分提交不自动重放，历史产生恢复Diff再确认；持久提交后、工具回填前崩溃可补齐一次结果且不重新写文件。修订教案/代码会使关联待审批包过期，修复整包审批没有单文件draft_id时的失效处理。
- `education/render.py`、`education/service.py`：当前验证与逐项审核闸口贯穿正式写入和ZIP；导出教案、示例/参考解、分层题/评分、固定规格、真实报告、Hash manifest与正式提交凭据。外部改文件、失败/漏测/过期/未审均阻断下载。
- `frontend/src/App.tsx`、`EducationWorkspace.tsx`、`api.ts`、`styles.css`：沿用浅紫白色/Lucide、AI对话+可展开工作区。学段/班情粘贴与文件选择、结构教案/示例/练习/错因、真实逐case报告、编辑评分/代码、逐项接受/拒绝、历史恢复、文件树/Diff/正式审批/ZIP已接通。增加键盘切换标签与未保存编辑提醒；不做IDE/账号/移动产品扩展。使用ui-ux、ui-ux-pro-max；按web-design-guidelines做最终源码与实际截图复核。
- `launch.py`与现有 `scripts/start-desktop.sh`：CLI选真实目录，自动开GUI；macOS原生目录选择入口；可选 `--runner-ssh` 一条命令连接已部署私有执行器，退出清理临时socket/转发，无需本机Docker。原生目录弹窗尚未人工验收；CLI目录与实际服务已验收。
- `scripts/deploy-web.py`、`configure-https.py`：指定VPS持久化API与独立Manager，API仅loopback端口，只有Manager持Docker Socket；新增本项目Nginx虚拟主机并保留原默认站点。首次域名验证被云厂商备案拦截；改用受信任的IP shortlived证书后成功。证书私钥、模型Key与Runner Token只留宿主受限配置，不进入构建包或Git。

### 实际命令与结果

| 命令/动作 | 实际结果 | 证据与边界 |
|---|---|---|
| `.venv/bin/python -m pytest backend/tests/unit backend/tests/integration/test_api.py backend/tests/integration/test_education_api.py backend/tests/integration/test_session_resume.py backend/tests/integration/test_delivery.py -q -o junit_family=xunit1 --junitxml=.runtime/stage05-final-backend.xml` | **156 passed** | 控制流使用显式测试Mock；真实文件/SQLite/审批/字节/恢复断言，不冒充模型或Runner |
| `.venv/bin/python scripts/verify_stage05.py root@<授权宿主> --tests-only` | **5 passed**，真实容器约61秒 | `.runtime/stage05-real-delivery.xml`；初中A/B与大学整课真实执行/写入/拒绝/恢复/ZIP；故意错误修复及待审整包过期 |
| `.venv/bin/ruff check backend scripts`；`npm --prefix frontend run build`；`git diff --check` | PASS | TypeScript+Vite真实构建；无新增锁文件 |
| `.venv/bin/python scripts/smoke_startup.py` | PASS | `.runtime/stage05-final-startup.log`；真实PC/Web进程与静态GUI、权限、SSE、重启、拒绝不改正式文件；模型显式Mock |
| 真实模型浏览器PC A班，Chrome | PASS：5程序/**17用例**；逐项审核、拒绝、真实写入、ZIP、刷新；待审/已提交各SIGKILL重启一次 | `.runtime/stage05-chrome-pass-firefox-launch-fail.json`内PC场景PASS及两个restart字段；同一文件整体FAIL仅因后续Firefox启动失败，不能抹去该异常 |
| 真实模型公网Web B班，Chrome | PASS：5程序/**18用例**；故意改为`print("intentional-wrong")`真实OUTPUT_MISMATCH；恢复代码后原固定用例通过；逐项审核、拒绝/接受、ZIP、cookie隔离 | 同上Chrome Web场景及failure_repair；失败n=0期望空串、实际`intentional-wrong\n`，退出0仍明确FAIL；截图/下载包保留 |
| 公网Web大学A班，WebKit26.5 | **PASS**：5程序/**16用例**；真实模型、逐项审核、正式提交、ZIP、刷新及新浏览器资源404 | `.runtime/stage05-webkit-browser.json`、`stage05-webkit-browser.log`；不是Chrome换一个上下文冒充第二引擎 |
| 解包三份浏览器下载ZIP，核对manifest/每份Python/报告 | PASS：每包5份Python、5份真实PASS报告，全部文件Hash一致 | `.runtime/stage05-packages.json`；旧Chrome Web下载14文件；当前包另含正式提交凭据，共15文件 |
| `MAX_PROJECT_CNY=33 bash scripts/start-desktop.sh --workspace <仓库外全新目录> --runner-ssh root@<授权宿主> --port 18007` | PASS：实际启动入口、自动打开GUI；`runtime`为pc、真实百炼、ISOLATED、发布可用 | 当前本机端口18007；真实根目录记录在 `.runtime/stage05-desktop-path.txt`。另有pytest在仓库外全新目录完成正式覆盖/删除与字节不变断言 |
| `.venv/bin/python scripts/deploy-web.py root@<授权宿主> --domain <服务器IP>`；外网curl/Chrome/WebKit访问 | PASS：[公网HTTPS](https://111.229.226.186)；真实模型/隔离器，API健康，重部署后持久目录保留 | `.runtime/stage05-delivery-deploy.log`、浏览器JSON/截图；开发机网络之外的第三条独立网络尚未验证 |

初轮回归150/151通过，唯一失败为阶段02旧测试仍断言批准必须`PUBLISH_NOT_READY`；更新为阶段05的新契约后保留拒绝不写入的全部断言，并补充真实批准/删除/恢复/崩溃窗口测试。真实多文件故障注入暴露了未写入文件不应再请求删除的问题，已修复。浏览器探针先后修正了测试自身的标签定位与request baseURL配置；失败日志未冒充通过。

Firefox在本机macOS图形子进程启动失败（sandbox extension / framebuffer），未完成Firefox兼容验收；改用正式WebKit运行完成公网大学主线。对应失败记录保留，Chrome与WebKit功能验收各有独立结果。自动化“教师接受”全部显式标注合成动作，只证明审核机制，不表示真实教师已确认教学适配。

### 当前交付与限制

- Web：[https://111.229.226.186](https://111.229.226.186)，无需注册；只用于合成班情演示。API/Manager容器设置自动重启；数据库和会话工作区持久保存。PC本轮服务在 `http://127.0.0.1:18007`，重新通过启动命令打开带本机能力口令的GUI。
- 现有默认Nginx站点保留。IP证书有效至**2026-11-05 14:07 Asia/Shanghai**；每日续期检查已启用，当前证书检查成功，未来真实续期尚未观测。
- 单API worker；同一实例串行Agent/验证；不将此演示宣称为生产多租户平台。Manager的Docker权限仍是高信任边界。多文件逐文件原子提交，整包中途故障可能部分写入；日志/人工恢复Diff可见，不承诺整组文件系统事务。
- Web预算单独¥12、本机本轮总限额¥33；不清零既有费用/未知预留。实际合计用量与源码指纹留在阶段05运行汇总；不把模型账单估值说成精确扣款。
- 真实教师教育审查、Firefox、本机原生目录弹窗、未来证书续期、现场机器及≤5分钟视频仍NOT_TESTED。阶段06尚未开展，不将本轮功能验收替代最终面试交付。

最终收尾：`.runtime/stage05-summary.json`汇总156/156后端、5/5真实容器交付、三浏览器场景15程序/51初始用例及限制；业务/种子/前端/Runner源码逐文件Hash与部署目录一致，汇总指纹为`ff4eea65ca7fb395844764113fcc777b356015c0d70836757db5ffe419ff072a`。重部署后两个Web会话的正式ZIP仍可由当前核心导出，隔离器无活动作业；截至本次检查，本地历史账簿含预留约¥17.909916、Web约¥1.161156，合计约¥19.071072，不等于厂商精确账单。源码凭据边界检查未发现配置Key进入受Git管理/待管理文件。

## 2026-10-30：阶段05专项验收 — 全新PC目录与Web会话

本轮开始保留前轮24个已修改/未跟踪文件，基线Hash存于 `.runtime/stage05-acceptance-baseline.json`；未覆盖无关既有改动。只修复UI长操作反馈与验收脚本缺口，不增加业务能力。

- `frontend/src/App.tsx`、`EducationWorkspace.tsx`、`styles.css`：测试/保存/审批显示明确状态，下载显示加载并防重复，读取文件显示进度、保存中禁用编辑。此前主要只有按钮置灰；新状态通过真实请求延迟观察与截图验证。非法评分真实422，原版本和编辑内容保留。
- `scripts/browser-stage05.cjs`：补充PC界面覆盖已有formal.md的拒绝/接受/字节核对、第三次重启恢复、实际查看正式教案；Web实际选择上传CSV、非法评分错误、真实失败与409交付阻断、修复同一规格、错因内容、ZIP、直接越界/跨cookie/跨源访问；状态观察只延迟请求，不伪造模型/执行报告。
- `scripts/verify_stage05.py`：增加证据前缀；PC独立验收数据库继承历史费用预留并在结束合并新增usage，避免重启探针影响已运行的PC会话；真实测试增加容器网络/文件/Key/Socket/进程限制检查。
- 已将本轮UI修复部署到指定VPS后实际验收。公网不是预期状态：本次证书正常验证、HTTP200，Chrome与WebKit均实际执行了真实模型备课和ZIP导出。运行时共享核心模块Hash与本地一致、React业务源代码一致，公网JS与运行容器文件Hash一致。

验收结果：PC八步及Web八步自动化通过，详见ACCEPTANCE第15节。新PC目录 `/private/tmp/yunyun-stage05-teacher-d8m6_ob2`，已有文件拒绝后bytes完全不变，接受后内容一致，重启后mtime不变；会话在三个检查点实际SIGKILL重启恢复。Web上传class_B.csv的服务端source_hash与原文件一致；n=0期望空串、实际intentional-wrong换行，真实失败；失败时接受禁用，package/delivery均409，无新审批；原规格修复PASS。三份实际下载ZIP各15文件/5份Python/5份PASS报告，manifest全部匹配。

实际命令与结果：

| 命令 | 本轮结果 |
|---|---|
| `pytest backend/tests/unit`及API/教育API/恢复/提交5个集成文件，完整命令见ACCEPTANCE第15节 | **156 passed**，0失败/0skip，1条既有Starlette弃用警告；另跑的78项安全/恢复是该集合子集，不累计为234 |
| `YUNYUN_PLAYWRIGHT_MODULE=<已有Playwright模块> .venv/bin/python scripts/verify_stage05.py root@<授权宿主> --browser --url https://111.229.226.186 --evidence-prefix stage05-acceptance` | **PASS**，全新PC A班/公网Web B班/公网WebKit大学A班；15程序/51条初始用例；真实失败/修复、审核、文件落盘与ZIP |
| `.venv/bin/python scripts/verify_stage05.py root@<授权宿主> --tests-only --evidence-prefix stage05-acceptance` | **6 passed**，约62秒；5项交付及1项真实容器权限/资源/清理验证 |
| `npm --prefix frontend run build`；`.venv/bin/ruff check backend scripts`；`git diff --check` | PASS |

[本轮汇总](../.runtime/stage05-acceptance-summary.json)、[浏览器结果](../.runtime/stage05-acceptance-browser.json)、[后端JUnit](../.runtime/stage05-acceptance-backend.xml)、[真实容器JUnit](../.runtime/stage05-acceptance-real-delivery.xml)、[ZIP核对](../.runtime/stage05-acceptance-packages.json)。原生目录弹窗、真实教师教育审核和第三条独立网络明确NOT_TESTED；Firefox未在本轮重跑。无剩余自动化主线阻断，未Git提交/推送。测试API进程/临时转发已结束，实际文件与持久化证据保留；旧PC服务未被验收重启。最后查询候选容器为空，Web API/私有Manager健康运行。


## 2026-10-30：阶段05五项评审修复

本轮从已有未提交改动继续，保留原有代码与文档修改；没有提交、推送或更新生产部署。此前主线验收漏掉了下列故障窗口，不能用历史PASS覆盖本轮问题。

- **P1 中断恢复**：`storage.py`统一提交/审批/任务/工具调用中断状态；`delivery.py`按工作区物理身份阻断未对账的新提交、恢复任务及导出。增加教师对账GET/POST入口及复用原工作区的对账Diff界面。按实时Hash/权限区分未写、已写、无差异、外部冲突；全未写可拒绝，全已写可确认且不重放，部分写入只在教师确认后回退已写入项。完成后工具结果仅记一次，原任务可继续；未知外部修改保留现场。
- **P1 会话回填**：`App.tsx`在操作发起时绑定会话ID和代次，快照/文件/SSE/错误/加载状态均复核；游标仅比较同会话。切换时清除原生文件选择，班情文件迟到读取也不能回填；教育编辑组件按会话隔离。
- **P2 Python删除契约**：`tools.py`请求发布与教师入口共同调用提交服务；只校验待写入Python的真实验证，删除仍受路径/Hash/审批约束，其他漏测或失败代码继续阻断交付。纯删除不产生PASS证据。
- **P2 权限**：`workspaces.py`临时文件默认0600，覆盖保留原rwx权限；日志保存before/content权限并用于回退。旧待审批实际提交也补齐权限；旧已完成日志无法推断的权限采用0600。
- **P2 上传**：`api.ts`直接发送File到现有原文接口；按原始字节限1 MiB，界面显示大小/格式错误。后端记录原始上传Hash，包括UTF-8 BOM；解析时去BOM不改变溯源Hash。未修改锁文件、环境密钥或生产配置。

主要文件：`backend/app/{delivery,delivery_api,storage,workspaces,tools,agent,api}.py`、`backend/app/verification/service.py`、`backend/app/education/{api,service}.py`、`frontend/src/{App.tsx,api.ts}`；新增`backend/tests/integration/test_stage05_review.py`与`scripts/review-stage05-browser.cjs`，更新原中断提交回归及README/ACCEPTANCE。

| 实际验证 | 结果与边界 |
|---|---|
| README中172项pytest命令，加入`test_stage05_review.py` | **172 PASS**；新增16项包含真实子进程os._exit、SQLite重开、磁盘字节/mtime/权限、对账所有权/版本/Hash、Python删除拒绝/接受、漏测阻断、540065字节及1 MiB边界/中文/转义/BOM/源Hash；模型为显式脚本Mock |
| `scripts/verify_stage05.py root@111.229.226.186 --tests-only --evidence-prefix stage05-review` | **6 PASS**；复用现有私有Runner，经临时socket转发真实执行容器交付/失败阻断/回退/隔离；不更新部署，不调用真实LLM |
| `scripts/review-stage05-browser.cjs`，现有Playwright，Chrome/WebKit | **22 PASS**；延迟A保存/验证/审批及文件响应，切换B并保持B自己的pending；B较低游标仍展示B；班情迟到读取/原生选择清理、CSV/转义中文JSON/原文1 MiB/BOM/Hash、对账Diff与继续。HTTP后端为显式控制流夹具，不能作为真实LLM/Runner证据 |
| `.venv/bin/python scripts/smoke_startup.py` | PASS；实际启动PC/Web进程与静态前端、真实目录读写、无口令拒绝、重启恢复/拒绝后继续/SSE回放；模型显式Mock，不是整课验收 |
| `npm --prefix frontend run build`；`.venv/bin/ruff check backend scripts`；`git diff --check` | PASS；UI按UI_GUIDELINES及web-design-guidelines复核，维持既有布局与组件，无视觉扩展 |

证据：[后端JUnit](../.runtime/stage05-review-backend.xml)、[真实容器JUnit](../.runtime/stage05-review-real-delivery.xml)、[浏览器控制流](../.runtime/stage05-review-browser.json)、[对账截图](../.runtime/stage05-review-chrome-recovery.png)。首轮55项、132项等针对性检查均属于上述集合，不叠加计数。

**NOT_TESTED**：本轮修复的公网部署与公网完整备课重跑、真实模型整课重跑、真实教师教育审核、原生目录选择器人工操作。上轮URL/整课证据仅是历史记录。未知外部内容/权限冲突需教师人工核对，不自动覆盖；修复前已丢失的原权限无法追溯恢复。
