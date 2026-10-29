# 开发进度与真实验证记录

> 不要把计划写成已完成。由 Codex 每阶段更新，写明事实和证据。

| 阶段 | 状态 | 验收证据 | 阻塞/风险 |
|---|---|---|---|
| 1. 设计/骨架/预部署 | IN_PROGRESS：设计已记录；骨架/部署 NOT_STARTED | PLAN、ACCEPTANCE；下列只读环境探测 | Docker daemon 当前无法连接；真实模型凭据/公网目标待确认 |
| 2. Agent Core | NOT_STARTED | 无业务源码/测试 | 需先完成环境/Provider 探针 |
| 3. 正确性验证 | NOT_STARTED | 无真实执行报告 | 独立 Runner 与隔离尚未实现/验证 |
| 4. 教育能力 | NOT_STARTED | 仅协议/策略与用例设计 | 尚无真实生成及两班情/两学段对照 |
| 5. PC/Web | NOT_STARTED | 无启动/部署/导出证据 | 需要现场机器确认、VPS/域名与服务启动授权 |
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

产品没有开始实施，A–E 与故障场景全部 NOT_TESTED；不存在已通过的代码、部署或教育验证。当前最先处理的依赖为真实 Provider Key/地域和端点、可用的 Docker daemon/独立 Runner、VPS/域名/实际部署授权。PC 普通子进程仅有限防护，不能宣称沙箱；Web 无隔离时必须关闭执行和正式交付。

下一步先由用户复核 PLAN 第 12 节的运行资源、模型/费用、教学/发布闸口三个决定，再在明确的下一阶段范围内创建骨架并完成 0–5h 探针。最先打通单个累加示例的真实失败→修复→重测→拒绝/确认→本地落盘→重启恢复；不提前扩张 UI 或整套业务。本轮没有开始执行 prompts/02-agent-core.md。

### 验证缺口

- pytest、前端类型检查/构建、Playwright：NOT_TESTED；原因是本轮仅文档规划，仓库尚无业务源码、依赖配置或测试文件。
- 浏览器、现场 PC 冷启动、公网 URL、真实模型请求与费用、容器隔离/故障清理：NOT_TESTED；没有运行服务或部署，相关授权/资源仍待下一阶段确认。
- 本轮没有真实 AI 代码失败案例，不能编造并填充 AI_DEV_LOG，也不能把设计中的故意错误样例当成已运行证据。
