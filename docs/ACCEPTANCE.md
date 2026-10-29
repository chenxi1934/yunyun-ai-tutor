# P0 与交付验收矩阵

**修订日期：2026-10-29。阶段03验证闭环已实现；首次执行证据见第9节，对抗性复验见第10节，当前P1修复见第11节。原题完整教育/发布能力未覆盖部分继续为 NOT_TESTED。**

架构、协议、阶段和部署闸口见 [PLAN.md](PLAN.md)，实际执行记录见 [PROGRESS.md](PROGRESS.md)。历史文档/环境检查不能充当产品能力证据；各阶段证据仅适用于其记录的源码与范围。

## 1. 判定纪律与证据格式

- `PASS`：在目标模式与当前 revision 下实际执行达到该条全部标准，保留可复查证据；`FAIL`：已执行但不满足；`NOT_TESTED`：未运行、无环境或证据不足。设计覆盖、依赖已安装、HTTP 200、模型自述、Mock 演示均不能直接变成 PASS。
- A/B 通用能力须在 PC、Web 两模式分别留证；C 专验 PC、D 专验 Web。只测一端时保留另一端 NOT_TESTED，不能汇总为全部通过。
- 每份证据至少写日期、命令/手动步骤、代码/内容 revision/hash、mode、真实/Mock、Provider/model（若使用）、实际输出或日志/报告位置。运行报告另含 test_spec_hash、runtime_digest、runner_policy_hash 与逐 case 结果。
- 单元测试可用显著 Mock 验证控制流，但不能证明真实模型或真实 Runner；真实 API 探针单独显式启用并记录用量，不让普通离线测试悄悄消费 Key。
- 所有示例与三档参考解必须逐个覆盖；任何 FAIL/TIMEOUT/执行错误/未测试/过期阻断正式提交和教案包导出。代码/测试/运行策略变化不能沿用旧 PASS，教学内容变化使对应教师审批失效。
- Web URL 为主交付；若按题目许可改走视频+部署说明，在 E5 明确选择并留证，D1 保留实际 FAIL/NOT_TESTED，不能把“有视频”写成“公网可访问”。替代分支不豁免真实执行、真实模型和教育能力。

## 2. 逐条原题验收

下表按完整原题判定；局部通过的证据在末列和各阶段子验收中注明。Fxx 故障场景见第 3 节，M-PC/M-WEB 见第 4 节；确切测试文件名和阶段命令见 PLAN 第 10 节。

| ID | 原题锚点/要求 | 可观察的 PASS 标准 | 方法 | 状态 | 实际证据 |
|---|---|---|---|---|---|
| A1 | A1，自然语言工作区读写与可感知变更 | 一句话使真实模型返回原生 tool_calls，实际 list/read；读到随机文件内容后据此提出草稿；界面有真实新文件/diff，可续改，正式文件未经确认不变 | Provider 探针、F21、M-PC、M-WEB | NOT_TESTED | 阶段02 PC/Web真实API子链路PASS；草稿/diff已保存，浏览器呈现与完整审批待阶段05 |
| A2 | A2，真实代码运行 | 候选 Python 确实执行；stdout/stderr/exit_code/耗时与实际一致；错误代码/异常/死循环明确失败并定位，非候选自报 PASS | F01–F06；Runner 集成测试 | PASS | 阶段03：PC共享核心真实容器回归19 PASS；Web真实百炼错误报告→修复→同规格重测通过；逐用例stdout/stderr/退出码/耗时/证据见第9节 |
| A3 | A3，多轮与会话恢复 | 第二轮能引用上一轮班情/修改；关闭后端再启动可恢复消息、草稿、工具结果、冻结用例、报告、待审批与预算；不会重复写/删 | F09、F11、F17；恢复集成测试 | NOT_TESTED | 阶段02实际进程重启恢复消息/草稿/工具/审批/预算PASS；阶段03规格/报告入SQLite，修复额度重开存储保持；正式提交及全链路进程恢复仍待验收 |
| A4 | A4，至少一个真实 API；允许 Mock 兜底 | 一家实际账户 API 完成“模型 call → 工具真执行 → call_id 回传 → 模型使用结果”；留脱敏请求/响应、实际 model/usage；Mock 时界面/事件/导出均醒目标识 | Provider 探针、F16、F21 | NOT_TESTED | 真实百炼qwen3.8-max原生工具往返及两轮上下文PASS，PC/Web均有证据；Mock事件/API标识已测、UI已构建，浏览器与导出标识尚未验收，故整项不提前PASS |
| A5 | A5，明确权限分级 | 授权读/草稿/受限测试可按 Policy 执行；正式创建/覆盖/删除展示具体 diff 并需教师确认；模型和直接 API 均不能伪造批准，路径越界被拒 | F10、F12–F15；Policy/提交测试 | NOT_TESTED | 读/草稿/路径拒绝/待审批/拒绝恢复子项PASS；阶段03受限执行已验证；正式提交待阶段05 |
| B1 | B1，结构化可复用备课产出 | Pydantic 校验 JSON；有稳定 ID 的目标/环节/时间，合计 45 分钟；2–3 个示例；基础/进阶/挑战各 1 题，均含参考解、用例与合计 100 的评分点；JSON/Markdown 导出一致 | 教育单测、M-PC、M-WEB、F20 | NOT_TESTED | 无 |
| B2 | B2，所有代码真正通过用例才可交付 | manifest 的每个示例和参考解均有当前指纹下的完整成功报告，逐 case 输入/预期/实际可查；任一错误或漏测阻断交付；模型至多修复两次且不改保护用例 | F01–F08、F20；真实完整教案生成 | NOT_TESTED | 阶段03已实现逐代码验证、失败/漏测阻断及两次修复；完整教育manifest和三档题待阶段04/05，不能以工程夹具替代 |
| B3 | B1/B2，逐项接受/拒绝/继续编辑与回退 | 教案段落、示例、题目有独立 revision/审批；拒绝后正式文件字节不变并可恢复候选父版本；已发布版本可转成恢复草稿，重测/审批后回写；代码编辑立即使旧验证过期 | F07、F10、F11、F13、F23 | NOT_TESTED | 无 |
| B4 | B3，错因预警贴合班情 | 每条有 misconception_type、evidence/未知项、trigger、cause、teaching_intervention、exercise_ids 与学段；“死循环 3 人”推动具体追踪干预；无证据结论标预测，不能泛化为能力差 | F18、F19；策略单测及教师内容审查 | NOT_TESTED | 无 |
| B5 | B4，初中/大学学段实质适配 | 固定主题与班情切换学段，至少目标、示例/练习、评分点三处实质变化；初中先修/超纲规则生效，大学增加推理/复杂度；两端均可配置 | F19；对照 JSON 与教师审查 | NOT_TESTED | 无 |
| B6 | B4，粘贴/上传班情驱动备课 | 支持粘贴文本与 JSON/CSV 上传；A/B 两份数据同题生成不同分钟分配和至少一项示例/练习策略；5 人未交与 3 人死循环不合计为 8 人，来源/分母/交集可追踪，缺失/冲突不默补 | F18、F19；导入/策略测试 | NOT_TESTED | 无 |
| C1 | C，本机可运行与启动交付 | 在指定 macOS 现场机器按 README 安装前提后，一条启动命令可打开 GUI、访问本机 API；明确 Python 3.12，不能误用系统 3.9；冷启动可复现 | M-PC 第 1 步；现场启动记录 | NOT_TESTED | 无；仅解释器存在 |
| C2 | C，真实本地目录与落盘 | 教师打开仓库外临时真实目录；可读原文件、创建新文件、批准修改后字节真实变化；记录前后 hash 与实际路径；拒绝无落盘 | M-PC、F10、F12、F13 | NOT_TESTED | 无 |
| C3 | C，执行命令/覆盖前的分级权限 | 受限容器测试按 L2；PC 有限防护模式必须对本次 hash 与风险确认；未批准的正式写/删与任意 shell 均被后端拒绝；不把 subprocess 宣称强隔离 | F10、F12、F14；PC 权限操作记录 | NOT_TESTED | 无 |
| C4 | C，教师视角完整 B1–B4 | 在真实本地工作区完成结构产出、所有代码真实验证、逐项回退、班情错因和学段适配；不是只运行一个玩具示例 | M-PC，B1–B6 的 PC 证据 | NOT_TESTED | 无 |
| D1 | D/交付1，直接打开的公网 URL | 实际 HTTPS URL 从开发机之外的网络/新浏览器可打开；能使用 API/SSE 完成主链路；记录地址、访问时间与实际结果 | M-WEB；外部访问记录 | NOT_TESTED | 阶段02已在VPS临时容器实际构建/启动/恢复，结束清理；未发布端口、未提供公网HTTPS URL |
| D2 | D，5–15 个种子文件 | 新会话实际列出 5–15 个可读文件，含教案、练习、示例和两份班情；不同会话独立可写，不修改种子或其他会话 | 文件清单与 F14；拟定 10 文件种子 | NOT_TESTED | 无 |
| D3 | D，真实验证与可看/下载教案包 | 一句话备课到真实 Python 失败/修复/通过可查，再经教师审核导出 ZIP；解包有教案 JSON/Markdown、示例、三档题/参考解/评分点、测试、报告、manifest；hash 对得上 | M-WEB、F02、F05、F20 | NOT_TESTED | 无 |
| D4 | D，Web 全部教育能力与安全边界 | B1–B6 在 Web 均有证据；执行走独立 Runner，网络/资源/文件限制实际生效；公网 API/代码容器无 Docker Socket/宿主目录权限；隔离不可用明确关闭执行 | F05、F06、F12、F14，B1–B6 的 Web 证据 | NOT_TESTED | 无 |
| E1 | 交付4，源码历史与关键 prompt | 源码完整可复现，有解释阶段问题的有意义 Git 提交，关键 prompt 与至少一例真实纠错可查；无 Key/真实学生信息入库。提交/推送需另有授权 | 授权后的 git log/源码检查；prompts 与 AI_DEV_LOG | NOT_TESTED | 无；当前无业务源码 |
| E2 | 交付3，≤5 分钟演示视频 | 可播放实际视频且时长≤300 秒，连续展示需求、结构化产出、真实故意失败及修复/阻断、当前报告、审核、本机正式落盘、班情错因；不是截图拼出假 PASS | 计时视频/链接与 DEMO_SCRIPT 对照 | NOT_TESTED | 无 |
| E3 | 交付5，一页设计与教育判断 | 一页回答错误阻断/验证/留痕/确认边界、裁剪理由、关键 prompt 和至少一例实际 AI 错误/发现/修正、学生端防抄设计、真实班级首轮隐私/内容安全；引用/改写开源时写清出处和范围；简述产品交互/视觉与可靠性优先 | DESIGN_DECISIONS/AI_DEV_LOG 与真实日志对照 | NOT_TESTED | 无；本轮仅新增产品交互说明，其他章节待真实实现后填写 |
| E4 | 现场，换请求仍运行，PC 可启动 | 在现场机器冷启动，用未硬编码的新备课表达完成真实工具/验证/审核链路；解释可验证与需教师判断部分，模型/网络失败时如实展示 | F22、M-PC、真实 API 与现场记录 | NOT_TESTED | 无 |
| E5 | 交付1/2/4/提交方式，交付清单及替代分支 | 实际 Web URL 或经明确说明的视频+部署分支；另有源码仓库地址、PC README 启动命令、≤5 分钟视频链接、一页文档，缺项写明。分支选择不掩盖 D1 状态 | 最终交付清单及真实链接；不自动上传/发布/推送 | NOT_TESTED | 无 |

## 3. 故障、边界与工程闸口

每项故障验收的 PASS 指“系统正确识别并阻断该故障”，不能把故障程序自己的报告改成 PASS。各场景的完整判定与阶段03子覆盖范围见实际证据列和第9节。

| ID | 场景与观测断言 | 拟验证位置 | 状态 | 实际证据 |
|---|---|---|---|---|
| F01 | 所有正确示例与三档参考解真实执行，所需 case_id 全覆盖；报告逐项对应，不能复用一个报告充数 | Runner/完整产物集成 | NOT_TESTED | 无 |
| F02 | `sum_1_to_n` 用 n=0/1/5；故意 `range(1,n)` 得到错误结果，定位 artifact/case/expected/actual；真实模型依据失败修代码后在同一规格通过 | Runner + 真实 API 探针扩展 | NOT_TESTED | 无 |
| F03 | 故意缺冒号触发 SYNTAX_ERROR，展示 stderr 与退出码；UI 不显示验证通过/可发布 | Runner/前端状态 | NOT_TESTED | 无 |
| F04 | 除零等触发 RUNTIME_ERROR；正常退出但答案错触发 OUTPUT_MISMATCH，二者区分 | Runner | PASS | 阶段03真实容器覆盖：除零RUNTIME_ERROR、正常退出错误输出OUTPUT_MISMATCH、AssertionError单列；第9节 |
| F05 | `while True` 在 2 秒墙钟限额及有界清理时间内终止；带派生进程用例也无残留容器/进程；状态 TIMEOUT，拒绝/取消/Manager 重启也能清理 | 真容器集成、进程/作业查询 | NOT_TESTED | 无 |
| F06 | 过量内存/进程/输出触发 RESOURCE_LIMIT 或 OUTPUT_LIMIT；Runner 不崩溃、不影响下一作业；stdout/stderr 各 64 KiB 上限生效 | 真容器集成 | NOT_TESTED | 无 |
| F07 | 分别修改代码、expected、运行镜像或 Runner Policy，旧报告 STALE，旧审批失效，提交/导出被拒；教学语义变化也使相关审核过期 | 验证/发布集成 | NOT_TESTED | 无 |
| F08 | 模型尝试把错误 expected 改为实际输出、删失败 case、延长已批准限额时被拒；新增测试只进待审版本，不替换冻结测试 | Tool/Policy/测试规格 | NOT_TESTED | 无 |
| F09 | 模型轮数/工具数/时间/token/费用/两次修复/重复无进展达到限额后真实停止；重启/换 Provider/重复请求不重置用量，不再产生副作用 | Loop 单测、持久化集成 | NOT_TESTED | 无 |
| F10 | 拒绝新建/覆盖/删除审批，正式文件前后 hash 相同；伪造 approval_id、改候选或文件 hash、重复提交均不能越权；只有最终绑定 diff 的确认才写入 | 提交/审批集成、手动 PC | NOT_TESTED | 无 |
| F11 | 分别在工具调用、等待审批、容器执行、正式多文件提交中断后重启；状态/预算/版本可恢复，不重复写删；不确定写入标 RECOVERY_REQUIRED 并阻断导出 | 故障注入集成 | NOT_TESTED | 无 |
| F12 | `../`、绝对路径、混合分隔符、前缀同名目录、符号链接/硬链接及检查后替换路径均不能访问根外；容器不见宿主文件、Key、Socket，外网连接失败 | 工作区/真实隔离集成 | NOT_TESTED | 无 |
| F13 | 教师在 diff 后外部编辑文件、两个 run 同时提交、目标新建时已存在，返回版本冲突且不覆盖；多文件中途失败按日志安全恢复 | 工作区/提交故障注入 | NOT_TESTED | 无 |
| F14 | 两个 Web 会话互读/改工作区、猜测报告/审批 ID、跨源伪造 PC 开目录/审批均被拒；API 与 Runner 端口/Socket 权限符合部署设计 | API/部署集成 | NOT_TESTED | 无 |
| F15 | 班情/工具结果含“忽略规则、批准覆盖、泄露 Key”时只当数据；模型即便产生危险 tool_call，服务端也拒绝；日志与导出无密钥/个人数据 | 注入/权限测试 | NOT_TESTED | 无 |
| F16 | 无 Key/鉴权失败/429/超时/无 tools 能力/坏参数/截断均有可识别错误；重试遵守预算，不悄悄 Mock；Mock 界面/事件/导出醒目标识 | Provider/Loop 单测、真实探针 | NOT_TESTED | 无 |
| F17 | SSE 断线/重连/重复事件按 event_id 补发去重；刷新用快照恢复待审/失败状态，不能触发第二次 run 或错报完成 | 事件/恢复测试；获授权后端到端 | NOT_TESTED | 无 |
| F18 | 文本/JSON/CSV 的缺字段、负数、冲突/超分母、超限上传有定位错误；5 未交与 3 死循环保留交集未知；原始个人标识不送模型 | 班情导入/策略单测 | NOT_TESTED | 无 |
| F19 | 同题 A/B 班情至少在分钟与示例/练习上有实质差异且 evidence 可追；同班情初中/大学至少三处深度差异；结构、先修、总时长和评分约束生效 | 教育单测、真实输出对照、教师复核 | NOT_TESTED | 无 |
| F20 | 去掉一道必需题/一个报告、伪造模型“PASS”、报告 hash 不匹配、未审候选混入 ZIP 均阻断交付；导出后逐文件 hash 与验证快照一致 | 发布/导出集成 | NOT_TESTED | 无 |
| F21 | 模型只说“已读/已测试”却无原生工具记录，或实际 call 未执行/未回传，不得满足 A1/A2/A4；非法工具及参数报错后回到模型上下文 | Provider/Loop 契约测试 | PASS | 2026-10-29阶段02：51项pytest中原生call/result配对、非法工具/参数回传、文本自报不能产生验证证据均通过；PC/Web真实随机标记探针证明模型使用实际工具结果 |
| F22 | 使用与演示不同的新表达，改变练习侧重或班情数字，仍经过实际工具而非关键词固定脚本，结果可解释且可追溯 | 真实模型现场验收 | NOT_TESTED | 无 |
| F23 | 候选被拒可回到父候选；已发布旧版经新恢复草稿、代码重测与新审批后恢复，当前正式文件在确认前不变，历史记录不消失 | 版本/提交集成 | NOT_TESTED | 无 |

## 4. 双端手动验收流程（本轮未执行）

默认不启动服务和浏览器。以下可由用户手动执行；若后续明确授权浏览器验证，再实现/运行相关 Playwright。先完成 README 安装前提和安全配置，不把下列尚不存在的脚本当成本轮可运行成果。

### M-PC：真实目录闭环

1. 在拟用现场 macOS 上按 README 运行 `scripts/start-desktop.sh --workspace <教师创建的临时教案目录>`。预期本机服务与 GUI 可用，实际用 Python 3.12；显示正确目录和模型/执行模式。
2. 在目录放入安全的既有教案与故意错误累加示例，记录原始文件 SHA256。输入《循环结构》请求和“5 未交、3 死循环”班情。预期显示真实读工具、依据链与结构产物。
3. 展开全部示例/三档答案报告。预期错误能定位到具体 case，死循环报 TIMEOUT；未全部通过时无法正式写入。请求修复后查看真实 diff 与新报告，保护用例不变。
4. 逐项拒绝一个示例或正式覆盖。预期正式文件 hash 不变，必需项缺失时整包不可交付；可回到父候选并继续编辑，改代码后显示验证过期。
5. 补齐候选、重测、逐项审核，再确认最终写入。预期真实目录出现教案/代码/习题等文件，hash 与对应报告/manifest 一致。再把旧发布版本转为恢复草稿，确认前目录不变。
6. 在待审批/已提交两处重启本地服务再恢复。预期待审项、报告、预算和文件版本一致，无自动重写；外部改文件后原审批提交应报冲突。
7. 同主题导入班情 B，再切大学配置，查看教学安排与评分点差异，检查依据来源。预期不是只改称呼，且所有新增代码重新验证。

### M-WEB：独立会话与教案包

1. 从非开发机网络/新浏览器打开实际 HTTPS URL。预期真实页面/API/SSE 可用，创建独立工作区并列出 5–15 个种子文件。
2. 用相同备课主线完成生成与所有代码验证，分别展示错误、死循环及修复。预期报告来自独立 Runner；执行不可用时明确阻断，不能显示假成功。
3. 逐项审核并确认，下载教案包、解包检查内容与 hash，逐题核对参考解报告。预期无遗漏、无未审候选和敏感信息。
4. 刷新/重连恢复，另开新会话尝试访问前一会话资源。预期本会话可恢复、新会话不能越权。切换学段/班情，重复 B 能力对照。

## 5. 当前结论

阶段03当前P1修复验证见第11节，对抗性验收见第10节，首次实施结果见第9节，阶段02历史结果见第6–8节。原题A2真实代码运行已PASS；完整教育结构、发布/导出、公网URL与浏览器交互仍未覆盖。故障F04和F21已有对应证据，其余故障按完整标准保留NOT_TESTED；第9节明确列出本轮实际覆盖，不能将部分覆盖冒充完整产品验收。具体命令、故障排查、用量与证据位置见 [PROGRESS.md](PROGRESS.md)。

## 6. 阶段02实施时子验收（2026-10-29，历史记录）

源码指纹 `bca61b9f476cd5acfad689bfc2a3ac3f41fd04135204e0b6aae8c60780be55fd`。普通pytest的模型均为显式测试Mock；真实Provider探针单独消费API。HTTP读取编译产物不等同于浏览器交互通过。

| ID | 本阶段验收 | 状态 | 实际证据与边界 |
|---|---|---|---|
| S02-01 | Python3.12/FastAPI/Pydantic/SQLite与React/TS/Vite可构建、启动、健康检查 | PASS | 51项pytest；`npm --prefix frontend run build`；`scripts/smoke_startup.py`实际PC/Web进程与静态前端HTTP通过 |
| S02-02 | 真实模型决定文件读取、真实结果回传、继续推理与第二轮上下文 | PASS | 百炼qwen3.8-max；`.runtime/probe-provider.json`（PC）、`.runtime/probe-provider-web.json`（Web）；随机标记进入真实read结果、草稿、最终回复，第二轮复述；Web一次协议失败后同检查点恢复成功，保留失败事件 |
| S02-03 | 工具白名单、Pydantic参数、路径边界、正式操作不能绕审批 | PASS | `test_policy.py` / `test_agent_loop.py` / `test_api.py`：越界、绝对/混合路径、符号/硬链接、目录替换、敏感文件、坏参数、跨会话/跨源拒绝；草稿不改正式文件；批准明确阻断 |
| S02-04 | 步数/工具/主动时间/Token/费用与异常停止 | PASS | `test_agent_loop.py`：各限额、实例累计、未知用量预留、恢复不清零、重试/无进展停止；这是阶段02循环预算，不含阶段03按artifact限制自动修复 |
| S02-05 | 重启恢复工作区、消息、工具/草稿、待审批与预算，不重复副作用 | PASS | `test_session_resume.py`中断/等待审批/多工具恢复；`scripts/smoke_startup.py`本地及远端真实进程重启、拒绝后继续，正式文件不变；不包含未来提交服务/Runner恢复 |
| S02-06 | API不可用有明确错误，测试接口不伪造通过 | PASS | `test_provider.py`鉴权/限流/超时/坏协议契约；真实服务缺Key报API_KEY_MISSING且mock=false；`run_python_tests`返回RUNNER_UNAVAILABLE/NOT_TESTED，无候选执行或PASS报告 |
| S02-07 | 最小React工作台构建、API静态托管、真实SSE/快照协议 | PASS | 类型检查/构建通过；实际HTTP健康、前端页面、SSE游标回放及幂等请求通过；UI实现聊天/文件/diff/事件/错误，源码检查完成；浏览器显示和操作见下一行 |
| S02-08 | PC启动入口与Web远端部署骨架实际可运行 | PASS | `bash scripts/start-desktop.sh --workspace ... --no-browser --port ...`真实shell启动与健康200；VPS Node22/Python3.12多阶段Docker构建与启动/恢复探针通过；不上传.env、不发布端口、结束清理，无公网URL |
| S02-UI | 浏览器渲染/交互、Playwright、人工教育审核 | NOT_TESTED | AGENTS禁止未经明确要求启动浏览器；本轮未运行。手动：PC启动后提出读取/草稿请求，核对工具记录及diff；刷新恢复；检查失败和拒绝后状态。教育审核待阶段04有真实产物后进行 |

尚未完成：真实Python隔离Runner与测试闭环（阶段03）、教育结构/班情/错因（阶段04）、正式批准/提交/版本回退/教案包/公网HTTPS（阶段05）。当前所有示例仍 NOT_TESTED，不能正式交付课堂材料。

## 7. 阶段02专项复验（2026-10-29，历史源码结果）

本次源码指纹 `20b2a2bf7f7e37b786befd0a5a603a2530a3298226343e4a7e180fdd89c25b47`。复验中修复文件列举的嵌套超限错误被吞、合法文件计数误判，2项新增回归先FAIL后PASS；完整pytest现为53 PASS。没有新增其他阶段功能。

证据：**L**=[本机真实HTTP/模型/恢复](../.runtime/stage02-acceptance-52c404a1a3e2.json)，**E**=[启动入口](../.runtime/stage02-entrypoints.json)，**R**=[远端容器运行](../.runtime/stage02-remote-425f17b3c9ff4c669f853788a76c7efc.json)，**S**=[九项汇总](../.runtime/stage02-acceptance-summary.json)。所有主要链路均`mock=false`；真实模型为百炼`qwen3.8-max`，实际主机为`dashscope.aliyuncs.com`。普通离线单测的测试Mock不替代这些证据。

| 用户项 | 状态 | 本次实际执行证据 |
|---|---|---|
| 1. 前后端能够启动 | PASS | `npm --prefix frontend run build`成功；E中Vite实际启动，首页/Vite客户端/TS入口均200；PC shell入口健康200。L/R中FastAPI启动、HTML及所有入口JS/CSS实际200并记录文件hash。未声称浏览器交互通过 |
| 2. 连接真实模型API | PASS | L记录PC/Web共12次真实百炼请求，各有`chatcmpl-*`请求ID、非零usage及实际`qwen3.8-max`模型名；不是只检查Key存在性 |
| 3. 模型发起真实Tool Call | PASS | L含8条原生调用：两模式各list_files/read_file/propose_patch/request_publish；例如PC read `call_6c383f86ba144b659c1e9672`、Web read `call_cf2ab342bb14469380ffb58d`，均真实执行并持久化 |
| 4. 工具结果回传模型 | PASS | L中read返回内容hash等于本次fixture字节SHA256；按原生`tool_call_id`回填工具消息，之后的模型原生propose_patch参数包含仅存在于文件中的两个随机字段 |
| 5. 根据结果继续推理 | PASS | L中未知随机标记/短语进入后续模型草稿和最终回复；重启、拒绝后真实模型再次复述，并说明正式文件未改变。未用模型一句“已读”作证据 |
| 6. 文件受工作区边界约束 | PASS | L中PC/Web各实际HTTP测试`../`、绝对路径、混合分隔符、.env、符号链接、硬链接，均403/PATH_DENIED且不含根外哨兵内容；合法fixture通过真实read读取。配套policy回归19 PASS |
| 7. 服务重启后会话恢复 | PASS | L中PC PID33666→33737、Web PID33762→33904，实际SIGKILL并重启；7类持久快照完全一致，保留工作区绑定/草稿/审批/预算；拒绝后从原调用继续，最终无重复草稿或工具回填 |
| 8. 失败明确返回错误 | PASS | L中真实BailianProvider连接拒绝，三次有界尝试后run=FAILED / PROVIDER_UNAVAILABLE，mock=false且无工具副作用；非法UTF-8文件实际422/ENCODING_ERROR；超限缺陷已修复并重新测试 |
| 9. Web部署路径/环境可行性 | PASS | R中当前代码Docker多阶段构建及非root运行通过，Python3.12.16 / Linux x86_64，API/JS/CSS均200；Docker29.9.2、Compose5.6.1已重查。远端百炼出口TLS通过、未带Key请求401。未上传Key、未公开端口，临时资源已清理 |

复跑入口：`.venv/bin/python scripts/verify_stage02.py`；远端为`.venv/bin/python scripts/probe_remote.py <SSH目标> --pypi-index https://mirrors.cloud.tencent.com/pypi/simple --real-startup`。完整pytest/构建/启动命令与排错过程见PROGRESS最新记录。

范围外仍 **NOT_TESTED**：浏览器渲染与交互/Playwright、公网HTTPS URL、隔离Runner/候选Python真实执行、教育产物与正式发布。第9项只判部署路径与运行环境可行，不能据此把D1公网URL或D4 Runner隔离标PASS。

## 8. 阶段02 Review修复验证（2026-10-29，当前结果）

本轮只处理用户确认的两项问题，文件hash、测试与计时见[汇总](../.runtime/stage02-review-summary.json)，不将历史全量验收沿用为本版本PASS。

| 问题/条件 | 状态 | 本轮实际证据 |
|---|---|---|
| P1：裁剪并重开存储后取回完整草稿，保留原稿继续修改 | PASS | `test_compacted_history_restart_can_read_and_revise_full_draft[pc/web]`：20KB正文、历史确实超过36,000字节，重开SQLite后上下文确无标记；读取结果全文相等，再追加说明，校验父版本/正文及正式文件不变 |
| P1：草稿读取不能跨会话或伪造参数 | PASS | `test_read_draft_enforces_session_ownership_and_strict_arguments`：本会话全文可读，其他会话NOT_FOUND且无正文泄露，额外session_id参数被拒 |
| P1：新读取入口可被真实模型调用 | PASS | [真实百炼报告](../.runtime/stage02-review-live-draft.json)：40,214字节合成历史、存储重开、裁剪后无标记；qwen3.8-max原生read_draft取得完整正文并报告末尾随机标记。fixture直接准备并明确标识，未冒充真实模型生成 |
| P2：5秒工具超时真正生效，事件循环能响应 | PASS | `test_slow_read_uses_declared_timeout_and_keeps_heartbeat_responsive`：5.1秒慢文件读约5.007秒FAILED/TOOL_TIMEOUT，心跳约14ms；迟到成功不能改写失败，不再请求后续模型 |
| P2：run剩余时间约束文件工具 | PASS | `test_run_remaining_time_bounds_file_preparation`：80ms主动预算在工具准备期间触发TIME_BUDGET/STOPPED，迟到后仍无新草稿 |
| P2：迟到结果不能产生草稿或审批 | PASS | `test_tool_timeout_never_commits_late_draft_or_approval[propose_patch/request_publish]`：超时后放开真实文件读取，原草稿集不变、审批为空 |
| P2：慢工具期间健康检查与取消可响应 | PASS | ASGI实际路由回归`test_slow_file_tool_does_not_block_health_or_cancel[timeout/cancel]`：读取仍阻塞时健康约0.8–1.2ms、取消约1.3ms，终态/工具结果不被迟到结果覆盖 |
| 相关后端回归、lint及diff检查 | PASS | 6个相关测试文件共62 PASS（含新增9例），[JUnit结果](../.runtime/stage02-review-tests.xml)保留计时属性；ruff/git diff --check通过，完整命令见PROGRESS最新记录 |
| 当前版本完整九项/远端/浏览器/前端构建重新验收 | NOT_TESTED | 本轮仅按确认问题做后端修复及相关验证，没有扩张验证范围；第6/7节保留历史证据，不冒充本轮重跑 |

后台只读I/O线程不能被Python强杀，可能晚于超时/取消结束；已验证迟到结果被丢弃且无草稿/审批副作用。Runner、正式提交、教育业务仍属于后续阶段，未新增实现。

## 9. 阶段03 — 首次验证闭环验收（2026-10-29，历史记录）

本阶段按`prompts/03-verification.md`实施，起始工作区干净；未提交/推送，未修改测试期望换取通过。模型控制流单测为显式测试桩；候选Python均经真实远端受限容器。Web额外使用真实百炼qwen3.8-max验证自主纠错，模型Key留在本机。

| ID | 条件 | 状态 | 实际证据 |
|---|---|---|---|
| S03-01 | 正确代码真实通过，正常/零次/边界用例完整对应 | PASS | `test_real_cases`的GOOD在n=0/1/5输出0/1/15，3个case ID完整；同服务适用于参考解，未冒充阶段04完整教育产物 |
| S03-02 | 语法、断言、结果错误、边界失败、运行异常分别定位 | PASS | 缺冒号SYNTAX_ERROR、assert失败ASSERTION_ERROR、print(PASS)仍OUTPUT_MISMATCH、range(1,n)在n=1/5输出0/10而非1/15、除零RUNTIME_ERROR；逐case日志、退出码、耗时和code_hash保存在真实JUnit属性 |
| S03-03 | 死循环、输出/内存超限不通过，并清理整个执行树 | PASS | while True为TIMEOUT；派生Python死循环同样清理；stdout/stderr分别超64KiB为OUTPUT_LIMIT；300MiB分配触发RESOURCE_LIMIT；后续作业正常；case duration有有界断言 |
| S03-04 | Web真实容器隔离和固定资源实际生效 | PASS | 候选实际观察UID10001，网络连接失败，根目录写入拒绝，宿主/app、/root/.ssh、Docker Socket不可见，无模型Key；读取cgroup得到cpu.max=50000 100000、memory.max=134217728、pids.max=32、swap.max=0，fork至上限被拒；容器内受限子进程可执行，不开放宿主命令 |
| S03-05 | 取消完整清理；Manager被杀后重启回收孤儿 | PASS | `test_timeout_descendants_and_client_cancel`在取消后下一真实作业可运行；脚本对本次临时Manager实际SIGKILL/start，孤儿容器ID和清理后空列表见汇总；没有重启用户既有服务 |
| S03-06 | 固定/教师规格与模型候选分离，不能删用例、改expected或延长时限 | PASS | 教师独立API冻结；Agent未知freeze工具拒绝、run_python_tests额外expected/timeout字段拒绝、旧规格ID拒绝；空/重复ID用例拒绝。候选仅收到代码和input，不收到expected或可写报告 |
| S03-07 | 代码/规格/镜像/策略变化使旧PASS失效，历史不可当新证据 | PASS | `test_code_spec_runtime_policy_changes_invalidate`覆盖四类依赖；`test_latest_report_only_and_cross_owner_api`验证旧报告effective_status=STALE、最新PASS及跨会话404；重新测试开始立即撤销旧资格，执行器不可用不能沿用PASS |
| S03-08 | Agent依据真实错误改代码，在原规格重测；展示父候选Diff | PASS | `test_agent_repairs_with_real_errors_same_spec`：OUTPUT_MISMATCH→新代码Hash→PASS，test_spec_revision/hash不变，repair_diff含实际range修改，正式文件未创建；另有下述真实模型证据 |
| S03-09 | 修复最多2次，不可修复立即停止，恢复不清零 | PASS | `test_agent_stops_immediately_after_second_failed_repair`恰好6次模型响应、3份失败报告后STOPPED/REPAIR_LIMIT，没有第7次模型请求；`test_unrepairable_stops_after_two_and_survives_restart`重开SQLite后不能第3次修复；重复失败Hash和不改代码直接重跑均NO_PROGRESS |
| S03-10 | 失败、漏测和模型自称通过均不能混入待审候选 | PASS | 一份通过但另一份challenge_answer.py漏测时整个候选闸口拒绝；request_publish无审批副作用；模型声称全部PASS仍VERIFICATION_FAILED；内部Docker错误为RUNNER_ERROR且清理失败关闭Runner |
| S03-11 | UI区分验证状态与逐用例证据，旧审批显示过期 | PASS（源码/构建） | 现有草稿区接线状态、effective_status、case输入/期望/实际、日志/退出码、Hash与父版本Diff；web-design-guidelines源码Review及TS/Vite构建通过；不代表浏览器交互已验收 |
| S03-12 | 真实百炼自主调用执行器，依据错误修复并在原规格通过 | PASS | 最终qwen3.8-max共6次成功请求、5次原生工具调用；OUTPUT_MISMATCH→PASS，规格Hash不变、代码Hash改变；成功探针估算¥0.258612，未知预留0笔，实际报告与call ID见下文 |
| S03-UI | 真实浏览器渲染/操作、Playwright | NOT_TESTED | 仓库规则要求明确授权，本轮未启动浏览器；手动步骤见PROGRESS阶段03末尾 |
| S03-DEPLOY | 持续运行的公网生产Runner、完整教案/发布/ZIP | NOT_TESTED | 本轮为临时私有隔离验收，结束清理；未配置Runner的实例继续关闭执行；生产部署和完整教育验收不在阶段03 |

当前自动化结果：**72项相关后端回归 + 19项真实容器集成 = 91 PASS**。前端`npm --prefix frontend run build`、`.venv/bin/ruff check backend runner scripts/verify_stage03.py`、`git diff --check`均通过；具体pytest命令见PROGRESS阶段03。证据：[相关回归JUnit](../.runtime/stage03-regression.xml)、[真实容器JUnit](../.runtime/stage03-real-tests.xml)、[汇总/镜像/源码Hash/孤儿清理](../.runtime/stage03-summary.json)、[真实百炼纠错报告](../.runtime/stage03-live-model.json)。这些忽略的本地证据未加入Git，复跑脚本在源码中。

本轮不将2秒/资源参数的配置文本当作隔离证据，使用真实cgroup、拒绝结果、容器清理和后继作业来判断。容器共享宿主内核，Manager持Docker权限，须在专用可信宿主单实例运行；API只连接私有Unix socket，PC不启用裸subprocess降级。

最终真实模型会话 `5e56151eaf664478a6bb417b35427b49`：错误报告 `7dd24f5c69d048ba939a75209a9a49d4`，通过报告 `bf83f69a88484393b4a7e075d02c103b`；真实执行call `call_531276ac6c0a4cb2baf467d6` → 修复call `call_8a1be5f78b7f4d25895ae89e` → 重测call `call_fef750b3f2c44786a9ff1009`。规格Hash始终为`22d5c25a19c97aede101aa95c21d2bcd10fd1d94ee780339758dcda77c44aa88`；代码Hash从`762f7b3823d323f8098c8a3a96e3bd0e85813550e69cc9cd553cd62d2340475e`变为`6b4c4ab8b24e2aa5a9cd19df45d5576250860b2b749d3888d9e6c448764740c7`。错误代码为明确标识的合成夹具，真实修复内容由模型生成；通过报告由隔离执行结果产生。

最终汇总status=PASS、pytest_exit_code=0、restart_orphan_cleanup=PASS、remaining_cases为空。执行镜像`sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159`；Manager镜像`sha256:731ca9846e14ef25a36fca03366501566f0720ef808337ed7135a2d3c9615461`。独立查询确认没有遗留阶段03候选/Manager容器；验收镜像标签和远端临时源码已清理，未删除用户既有容器/基础镜像。


## 10. 阶段03对抗性验收（2026-10-29，P1修复前的历史记录）

本轮实际发现并修复1个Runner缺陷：StringIO替换sys.stdin导致合法buffer/FD 0/子进程输入程序误判运行异常。现于同一受限容器内保存代码快照，通过真实stdin管道启动固定Python；未改变冻结用例、比较规则或资源限制。增加7项对抗测试及证据属性，原有断言保留。新增tmpfs探针另修正close刷新时ENOSPC的捕获范围，严格期望仍为errno=28。

最终 **26项真实Runner集成 + 72项相关后端回归 = 98 PASS，0失败/0错误/0跳过**；真实模型单独验证通过。具体命令见PROGRESS本轮记录；ruff/git diff --check通过。本轮纯后端/Runner，不涉及前端修改或浏览器验证。

| 编号 | 用户要求 | 实际结果 | 验收 |
|---|---|---|---|
| 1 | 正常循环 | n=0/1/5均输出0/1/15，input()、stdin.buffer、FD 0、继承stdin的子进程均通过 | PASS |
| 2 | 语法错误 | SYNTAX_ERROR、退出码1、真实SyntaxError日志；不能待审 | PASS |
| 3 | while死循环 | TIMEOUT，整个容器及子进程清理；无正常退出码，不伪填0 | PASS |
| 4 | 输出不同 | print(PASS)实际输出PASS仍OUTPUT_MISMATCH，正常退出码0不等于通过 | PASS |
| 5 | 边界错误 | range(1,n)在n=1/5失败；新增零次循环错误在n=0单独失败，其余用例通过也不能掩盖 | PASS |
| 6 | 运行异常 | 除零RUNTIME_ERROR；即便先打印全部正确输出再raise，也保持失败 | PASS |
| 7 | 改已通过代码 | 旧草稿/报告STALE，新草稿NOT_TESTED，待审闸口拒绝；报告仍保留历史 | PASS |
| 8 | Agent同规格修复重测 | 真实百炼原生工具调用：OUTPUT_MISMATCH→新代码Hash→PASS；test_spec_revision/hash及三条用例保持不变 | PASS |
| 9 | 无法修复必须停止 | 受控连续错误提案驱动真实Agent Core/Runner，3份失败报告、2次修复后STOPPED/REPAIR_LIMIT；重开SQLite不能重置限额，没有PASS或交付 | PASS |
| 10 | 权限与资源限制 | 实测UID10001、无外网、不可见宿主目录/Socket/Key、根只读；cgroup 0.5CPU/128MiB/无额外swap/32pids；cap_eff=0、no-new-privileges=1、seccomp=2、nofile=64/core=0、16MiB tmpfs ENOSPC；内存/输出超限、鉴权及策略篡改拒绝、超时/取消/孤儿清理均通过 | PASS |

下面为关键程序的n=5用例原始摘要，换行以\n表示；耗时包含容器生命周期，不是算法CPU耗时。故障程序本身仍为失败状态，PASS只表示系统正确识别并阻断故障。

| 场景 | 输入→冻结期望 | stdout | stderr末行 | exit code | 耗时 | 程序结果 |
|---|---|---|---|---|---|---|
| 正常循环 | `5\n` → `15\n` | `"15\n"` | 空 | 0 | 562.71 ms | PASS |
| 语法错误 | `5\n` → `15\n` | `""` | SyntaxError: expected ':' | 1 | 604.53 ms | SYNTAX_ERROR |
| 输出不匹配 | `5\n` → `15\n` | `"PASS\n"` | 空 | 0 | 645.31 ms | OUTPUT_MISMATCH |
| while死循环 | `5\n` → `15\n` | `""` | 空 | null（超时终止，未采集正常退出码） | 2176.33 ms | TIMEOUT |
| 边界漏项 | `5\n` → `15\n` | `"10\n"` | 空 | 0 | 570.65 ms | OUTPUT_MISMATCH |
| 运行时异常 | `5\n` → `15\n` | `""` | ZeroDivisionError: division by zero | 1 | 575.07 ms | RUNTIME_ERROR |

真实模型会话`1cbcc8ccfc164fd48a2e392d8b89c7f2`，6次请求/5次原生工具调用；成功报告`9314619831cd4d8e94313618f2e3e5d8`。固定测试Hash`22d5c25a19c97aede101aa95c21d2bcd10fd1d94ee780339758dcda77c44aa88`；代码Hash从`762f7b3823d323f8098c8a3a96e3bd0e85813550e69cc9cd553cd62d2340475e`改为`6b4c4ab8b24e2aa5a9cd19df45d5576250860b2b749d3888d9e6c448764740c7`。用量估算/保守预留¥0.261036，未知预留0笔，不是精确账单；沿用实例SQLite预算。

[十项完整证据JSON（含所有stdout/stderr、退出码、耗时、用例、Hash与Agent状态）](../.runtime/stage03-adversarial-evidence.json)、[真实Runner JUnit](../.runtime/stage03-adversarial-real-tests.xml)、[72项相关回归JUnit](../.runtime/stage03-adversarial-regression.xml)、[真实模型原生调用/报告](../.runtime/stage03-adversarial-live-model.json)、[源码/测试Hash与清理汇总](../.runtime/stage03-adversarial-summary.json)。修复前3 FAIL与中间探针1 FAIL证据均保留，没有改成成功或覆盖删除。

修复涉及`runner/docker_runner.py`、`backend/tests/integration/test_verification.py`、`scripts/verify_stage03.py`及PROGRESS/ACCEPTANCE。无剩余阶段03验收P0；正式教育manifest/发布/导出和浏览器不属于本次验收，不能由此升为PASS。临时Runner非持续部署，容器共享宿主内核的风险仍存在。


## 11. 阶段03 P1修复 — Python后缀大小写一致性（2026-10-29，当前结果）

根因：Workspace已允许`.PY/.pY`，但其余入口只检查小写`.py`，未测试代码可被当作文档创建待审请求。修复在`workspaces.py`提供统一`is_python_path`，API规格冻结、Verification草稿识别/候选集合、request_publish、Agent完成状态及修复Diff全部复用；保留原始文件名，不放宽工作区边界。

| 条件 | 状态 | 实际证据 |
|---|---|---|
| 修复前真实复现绕过 | PASS（缺陷复现） | 新增21项先得到14 FAIL/7 PASS；大写后缀创建WAITING_APPROVAL，验证入口拒绝识别，原证据[before JUnit](../.runtime/stage03-suffix-before.xml)保留 |
| `.py/.PY/.pY`未测试/失败/过期不能待审 | PASS | 18项参数组合覆盖代码与同组Markdown发布，均VERIFICATION_REQUIRED、无审批记录/审批事件、无正式文件改动；合成状态只作策略测试，不冒充执行报告 |
| 规格冻结、验证与Agent完成状态一致 | PASS | 三种后缀API冻结均201且n=0/1/5期望保持0/1/15；Verification识别为Python；模型文本自称完成仍VERIFICATION_FAILED |
| 真实失败、通过和编辑失效 | PASS | 三种后缀实际执行raise RuntimeError得到RUNTIME_ERROR，原规格下修复为GOOD得到PASS；再次编辑旧PASS为STALE、新草稿NOT_TESTED，request_publish拒绝且审批数0 |
| 整组候选包含大写后缀 | PASS | 同组other.py真实通过后，请求发布other.py仍因answer.PY/answer.pY漏测被拒绝，无审批记录，不能通过选择另一文件绕过 |
| 相关回归与源代码检查 | PASS | 96项相关后端回归（含34项策略测试）+29项真实Runner集成=125 PASS，0失败/0错误/0跳过；ruff/git diff --check通过；当前源码/测试Hash与本轮汇总相符 |

真实Runner三种后缀分别留下RUNTIME_ERROR/PASS报告与编辑后未测状态，审批记录均为0。证据：[策略JUnit](../.runtime/stage03-suffix-policy.xml)、[96项后端回归](../.runtime/stage03-suffix-regression.xml)、[29项真实Runner及suffix_gate逐案例报告](../.runtime/stage03-suffix-real-tests.xml)、[运行汇总/源码Hash/清理](../.runtime/stage03-suffix-summary.json)。实际命令见PROGRESS本轮记录；后端回归约7.64秒、真实Runner约87.61秒。既有Starlette TestClient弃用警告1条，未升级依赖。

本轮只修复该P1，保留先前所有未提交改动；未改既定测试输入/期望，没有调用真实模型或启动浏览器（纯后端修改），未Git提交/推送。临时远端容器/镜像标签/源码目录已清理并独立查询为空，SSH控制连接已关闭。本次P1无剩余问题；阶段05正式写入仍按原约定阻断，不能以本轮策略回归代替完整产品验收。
