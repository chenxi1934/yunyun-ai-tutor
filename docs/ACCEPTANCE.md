# P0 与交付验收矩阵

**修订日期：2026-10-30。阶段05双端功能、公网HTTPS、真实交付与Chrome/WebKit验收见第14节；人工教育审查和最终面试交付仍有未验项目。**

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
| A1 | A1，自然语言工作区读写与可感知变更 | 一句话使真实模型返回原生 tool_calls，实际 list/read；读到随机文件内容后据此提出草稿；界面有真实新文件/diff，可续改，正式文件未经确认不变 | Provider 探针、F21、M-PC、M-WEB | PASS | 阶段02真实工具往返；阶段05 Chrome双端真实模型、工作区草稿/Diff/修改与正式审批，见第14节 |
| A2 | A2，真实代码运行 | 候选 Python 确实执行；stdout/stderr/exit_code/耗时与实际一致；错误代码/异常/死循环明确失败并定位，非候选自报 PASS | F01–F06；Runner 集成测试 | PASS | 阶段03：PC共享核心真实容器回归19 PASS；Web真实百炼错误报告→修复→同规格重测通过；逐用例stdout/stderr/退出码/耗时/证据见第9节 |
| A3 | A3，多轮与会话恢复 | 第二轮能引用上一轮班情/修改；关闭后端再启动可恢复消息、草稿、工具结果、冻结用例、报告、待审批与预算；不会重复写/删 | F09、F11、F17；恢复集成测试 | PASS | 阶段02多轮；阶段05 Chrome PC待审/已提交两次进程重启、刷新与恢复；提交后崩溃工具回填不重写，见第14节 |
| A4 | A4，至少一个真实 API；允许 Mock 兜底 | 一家实际账户 API 完成“模型 call → 工具真执行 → call_id 回传 → 模型使用结果”；留脱敏请求/响应、实际 model/usage；Mock 时界面/事件/导出均醒目标识 | Provider 探针、F16、F21 | PASS | 百炼qwen3.8-max真实原生工具与usage；阶段05双端真实模型及Chrome/WebKit；显式Mock与导出mock元数据沿用协议 |
| A5 | A5，明确权限分级 | 授权读/草稿/受限测试可按 Policy 执行；正式创建/覆盖/删除展示具体 diff 并需教师确认；模型和直接 API 均不能伪造批准，路径越界被拒 | F10、F12–F15；Policy/提交测试 | PASS | 阶段05 Hash绑定正式创建/覆盖/删除/拒绝/恢复与权限测试；代码验证/教师审核/提交独立，见第14节 |
| B1 | B1，结构化可复用备课产出 | Pydantic 校验 JSON；有稳定 ID 的目标/环节/时间，合计 45 分钟；2–3 个示例；基础/进阶/挑战各 1 题，均含参考解、用例与合计 100 的评分点；JSON/Markdown 导出一致 | 教育单测、M-PC、M-WEB、F20 | PASS | 阶段04教育协议；阶段05双端结构界面与正式ZIP，2示例/三档题/评分/时间和Hash一致，见第14节 |
| B2 | B2，所有代码真正通过用例才可交付 | manifest 的每个示例和参考解均有当前指纹下的完整成功报告，逐 case 输入/预期/实际可查；任一错误或漏测阻断交付；模型至多修复两次且不改保护用例 | F01–F08、F20；真实完整教案生成 | PASS（技术交付闸口） | 阶段05所有示例/参考解当前真实报告、失败/过期/未审阻断提交与ZIP；人工教育判断另列NOT_TESTED |
| B3 | B1/B2，逐项接受/拒绝/继续编辑与回退 | 教案段落、示例、题目有独立 revision/审批；拒绝后正式文件字节不变并可恢复候选父版本；已发布版本可转成恢复草稿，重测/审批后回写；代码编辑立即使旧验证过期 | F07、F10、F11、F13、F23 | PASS | 阶段04逐项父版本与重新验证；阶段05实际覆盖/删除/拒绝/恢复Diff/崩溃窗口；代码变化使报告与待审批包失效，见第14节 |
| B4 | B3，错因预警贴合班情 | 每条有 misconception_type、evidence/未知项、trigger、cause、teaching_intervention、exercise_ids 与学段；“死循环 3 人”推动具体追踪干预；无证据结论标预测，不能泛化为能力差 | F18、F19；策略单测及教师内容审查 | NOT_TESTED（人工审查） | 依据链与双端错因展示/代码技术验收PASS；真实教师内容审查尚未执行，不用自动化点击替代 |
| B5 | B4，初中/大学学段实质适配 | 固定主题与班情切换学段，至少目标、示例/练习、评分点三处实质变化；初中先修/超纲规则生效，大学增加推理/复杂度；两端均可配置 | F19；对照 JSON 与教师审查 | NOT_TESTED（人工审查） | 阶段05初中A/B与大学真实程序/评分/目标差异、共享双端配置已测；真实教师适配审查仍待完成 |
| B6 | B4，粘贴/上传班情驱动备课 | 支持粘贴文本与 JSON/CSV 上传；A/B 两份数据同题生成不同分钟分配和至少一项示例/练习策略；5 人未交与 3 人死循环不合计为 8 人，来源/分母/交集可追踪，缺失/冲突不默补 | F18、F19；导入/策略测试 | PASS（API/流程） | 阶段04上传解析/规则对照；阶段05浏览器A/B选择与真实班情导入、结构化主线；大文件原文上传协议见API测试 |
| C1 | C，本机可运行与启动交付 | 在指定 macOS 现场机器按 README 安装前提后，一条启动命令可打开 GUI、访问本机 API；明确 Python 3.12，不能误用系统 3.9；冷启动可复现 | M-PC 第 1 步；现场启动记录 | PASS（当前macOS） | 一键入口实际启动并自动开GUI；CLI选仓库外目录、Python3.12、私有Runner；面试现场机器另待验收 |
| C2 | C，真实本地目录与落盘 | 教师打开仓库外临时真实目录；可读原文件、创建新文件、批准修改后字节真实变化；记录前后 hash 与实际路径；拒绝无落盘 | M-PC、F10、F12、F13 | PASS | 阶段05真实文件覆盖/删除/恢复与CRLF字节断言；Chrome PC模型备课包实际落盘，见第14节 |
| C3 | C，执行命令/覆盖前的分级权限 | 受限容器测试按 L2；PC 有限防护模式必须对本次 hash 与风险确认；未批准的正式写/删与任意 shell 均被后端拒绝；不把 subprocess 宣称强隔离 | F10、F12、F14；PC 权限操作记录 | PASS | 本机能力口令、Hash/Diff确认、拒绝不写入、私有隔离Runner；没有宿主子进程降级与任意shell |
| C4 | C，教师视角完整 B1–B4 | 在真实本地工作区完成结构产出、所有代码真实验证、逐项回退、班情错因和学段适配；不是只运行一个玩具示例 | M-PC，B1–B6 的 PC 证据 | PASS（技术流程） | PC真实模型整课、逐项审核、真实执行与正式包；两学段/班情共享核心真实容器测试；人工教学判断待教师 |
| D1 | D/交付1，直接打开的公网 URL | 实际 HTTPS URL 从开发机之外的网络/新浏览器可打开；能使用 API/SSE 完成主链路；记录地址、访问时间与实际结果 | M-WEB；外部访问记录 | PASS | https://111.229.226.186；开发机外VPS的真实HTTPS，Chrome/WebKit新上下文端到端；第三条独立网络未验 |
| D2 | D，5–15 个种子文件 | 新会话实际列出 5–15 个可读文件，含教案、练习、示例和两份班情；不同会话独立可写，不修改种子或其他会话 | 文件清单与 F14；拟定 10 文件种子 | PASS | 阶段04新Web工作区精确7个合成文件，含两班情与初中/大学结构种子；独立会话沿用既有隔离协议，见第12节 |
| D3 | D，真实验证与可看/下载教案包 | 一句话备课到真实 Python 失败/修复/通过可查，再经教师审核导出 ZIP；解包有教案 JSON/Markdown、示例、三档题/参考解/评分点、测试、报告、manifest；hash 对得上 | M-WEB、F02、F05、F20 | PASS | Chrome故意失败/修复；Chrome和WebKit真实模型、逐项审核、正式提交与ZIP解包Hash/报告验证，见第14节 |
| D4 | D，Web 全部教育能力与安全边界 | B1–B6 在 Web 均有证据；执行走独立 Runner，网络/资源/文件限制实际生效；公网 API/代码容器无 Docker Socket/宿主目录权限；隔离不可用明确关闭执行 | F05、F06、F12、F14，B1–B6 的 Web 证据 | PASS（技术边界） | 独立Manager/候选隔离沿用阶段03证据；阶段05持续部署API无Docker Socket、真实教育主线与cookie隔离；人工教学判断待教师 |
| E1 | 交付4，源码历史与关键 prompt | 源码完整可复现，有解释阶段问题的有意义 Git 提交，关键 prompt 与至少一例真实纠错可查；无 Key/真实学生信息入库。提交/推送需另有授权 | 授权后的 git log/源码检查；prompts 与 AI_DEV_LOG | NOT_TESTED（最终交付） | 源码/关键prompt和阶段实现保留；本轮未获Git提交/推送授权，完整最终交付与历史汇总留阶段06 |
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

## 4. 双端手动验收流程（保留供教师/现场验收）

阶段05已按用户授权运行对应自动化主线，证据见第14节。以下流程仍供真实教师与现场机器复验；自动化合成审核不能替代人工教学判断。

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

阶段05共享PC/Web完整功能、公网HTTPS、正式文件审批/提交/恢复和ZIP已实现，Chrome双端及WebKit公网主线通过。156项后端回归和5项真实容器交付通过。人工教育审查、Firefox兼容、原生选目录弹窗、未来证书续期及阶段06现场/视频尚未通过或未执行；详见第14节。阶段02–04历史记录继续保留其原有范围与限制。

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

## 12. 阶段04 — 教育协议、班情与逐项审核（2026-10-29）

本阶段不开发复杂UI，不把规则草稿、合成教师审核或代码PASS当作教师教育判断。最终源码离线回归148 PASS、真实容器37 PASS（29项既有Runner回归+8项完整教育集成），合计185 PASS，0失败/0错误/0跳过；真实模型内容生成与全代码验证PASS，详见下方最终补记。命令见PROGRESS阶段04；首轮及中间失败证据保留，不累计重复运行次数。

| ID | 条件 | 状态 | 可复查证据 |
|---|---|---|---|
| S04-01 | 45分钟结构、目标/可观察标准、2–3示例、三档各1题、答案/用例/100分评分点 | PASS | `test_lesson_structure_rejects_invalid`及完整真实课例；缺时长/档次/分数/ID/引用均拒绝；固定任务契约与每项测试一致 |
| S04-02 | 文本粘贴、JSON/CSV原文上传、缺失/异常/冲突处理 | PASS（API） | 45项教育单元测试及7项教育API测试；负数/小数/约数/布尔/超分母/重复键列/乱码/超限均拒绝；未知不当作0；教师上传不会跨会话 |
| S04-03 | 5未交与3死循环分别保留依据、不当作8个不同学生 | PASS | `test_profile_evidence_unknown_overlap_and_no_denominator`保留原文位置和Hash；未知分母不算比例，交集明确未知；JSON/CSV无关个人信息列不存储/不送模型 |
| S04-04 | 两班情导致时间、示例、练习支架/评分的实质差异 | PASS | A：5/8/10/10/10/2；B：2/8/8/15/10/2。第二演示sum→even_sum、追踪表→边界表、边界分20→40；两份完整初中课例所有5份代码均真实通过 |
| S04-05 | 初中/大学目标、任务和评分深度不同 | PASS（技术对照） | 大学有不变量/终止/复杂度目标、pairs嵌套演示、divisors/primes题、50/30/20评分；完整大学5份代码真实通过。真实教师对适配性的审查仍NOT_TESTED |
| S04-06 | 预警依据链真实、未知结论标预测、病因标假设 | PASS（结构/规则） | 同类非零事实引用、basis与证据一致性、非零观察不得遗漏、阶段/练习引用均校验；not_submitted不能直接判能力差；实际教育措辞仍由教师审核 |
| S04-07 | 每个示例和参考解经真实Runner，漏测/失败阻断 | PASS | 8项真实教育测试含3套完整课例；逐case输入/期望/实际、stderr、exit_code、duration、代码/规格/镜像/策略Hash均保留。参考解OUTPUT_MISMATCH/SYNTAX_ERROR/TIMEOUT不能成为候选，其余答案继续验证而非漏测 |
| S04-08 | 单项修订、拒绝、恢复草稿、历史与审核状态 | PASS（API/存储） | 仅改单题重测1份，其余4份报告复用；旧PASS过期、相关错因审核失效，其他项目保留；拒绝不改正式文件；恢复旧内容生成新revision；重开SQLite父版本/班情完整。正式文件/已发布版本恢复归阶段05 |
| S04-09 | 不能换题、删除失败项、删减用例、走通用草稿绕绑定 | PASS | 服务预检冻结任务/稳定ID；实际把测试减至一条并运行获得局部PASS，教育候选仍阻断；通用propose_patch被拒；自动修复2次后重提整课或base_revision=0不能重置限额 |
| S04-10 | 代码PASS不能代表课程适配与教师接受 | PASS（机制） | 真实额外函数探针输出全PASS，初中课程风险仍阻断；正常代码全PASS时全部教学项仍PENDING；accept/reject只在独立教师API，模型无此工具；班情变化禁止接受旧教案 |
| S04-11 | JSON/Markdown/代码/用例/报告/manifest导出一致 | PASS（草稿组合） | 自动化以明确合成教师动作逐项接受后导出，文件Hash逐一相等；未测/失败/过期/拒绝/待审拒绝导出。不是人工教育审查证据，也不是正式落盘或ZIP |
| S04-12 | Web种子为5–15文件、含两班情与完整结构样例 | PASS | 精确7路径断言：README.md/example.py/class_A.json/class_A.txt/class_B.csv/lesson_junior.json/lesson_university.json；均合成NOT_TESTED，不能把种子自身当作已验证课堂材料 |
| S04-MODEL | 真实模型生成有内容差异的完整教案并验证全部代码 | PASS | 最终qwen3.8-max实际改写6个环节和2个示例讲解；INVALID_LESSON(stage缺失)→模型补齐→真实Runner全部5份PASS；5次请求、4次工具，原失败完整保留，教师仍PENDING |
| S04-UI | 浏览器/Playwright、教育交互界面 | NOT_TESTED | 本轮无前端修改，遵守未明确要求不启动浏览器；API可用，手动步骤见PROGRESS |
| S04-PUBLISH | 公网HTTPS/持续Runner/正式写入/ZIP/真实教师教育审核 | NOT_TESTED | 阶段05及人工验收范围；当前只有按次临时隔离器和审核草稿文件组合 |

证据：[最终148项回归](../.runtime/stage04-complete-regression.xml)、[最终37项真实容器测试](../.runtime/stage04-complete-real-tests.xml)。中间2失败保留在[修复前报告](../.runtime/stage04-regression-before-fixes.xml)，改的是全课预检顺序与按本轮需求扩为7文件的明确断言，未调整代码任务的既定输入/期望/限额。

最终真实模型证据：[完整工具/格式失败修复/5份报告](../.runtime/stage04-complete-live-model.json)、[教师待审教案JSON](../.runtime/stage04-complete-lesson.json)、[A/B/大学实际课例对照](../.runtime/stage04-complete-comparison.json)、[源码Hash/清理汇总](../.runtime/stage04-complete-summary.json)。会话`9b961324592840cea00e6f993ca85c1b`，5次模型请求/4次原生工具；真实6个activity、2个explanation有内容差异，全部5份代码PASS，教学审核仍PENDING。估算¥0.564432、未知预留0；历史超时/格式错误/预算停止均保留，没有追改成成功。

最终还修复了实际发现的同轮重复整课JSON占满输入预算问题：教育交换归档仅改变送模型的上下文，保留当前需求、最后提案完整协议、原错误索引和事实Hash，SQLite原始消息/参数/报告/费用不变；专门回归验证。对应失败探针[STOPPED/BUDGET_EXCEEDED完整记录](../.runtime/stage04-verified-live-model.json)与[FAIL汇总](../.runtime/stage04-verified-summary.json)保留，未放宽80k/12k/12步/模型时限或代码断言。最终148项后端+37项真实容器=**185 PASS**，真实容器188.54秒；源码/测试/脚本Hash核对一致。

远端临时测试器、候选、镜像标签和源码目录已独立确认清理，未发布端口；孤儿回收PASS。当前没有持续可用的Runner/公网服务；正式发布/ZIP/教育UI/人工教育判断仍NOT_TESTED。本轮纯后端，无浏览器/Playwright或前端构建，避免把未执行的项目标为PASS。

## 13. 阶段04专项验收 — 真实两班情与大学对照（2026-10-29）

本轮两套班情均真实调用qwen3.8-max，并以同A数据真实生成大学教案。原始生成后再逐段审校，通过逐项修订接口修正实际文字错误；保留原稿/父版本/每项before-after，最终重新执行所有代码。不是把规则模板或自动合成教师接受动作当作真实生成/教师审查。

| 用户检查项 | 结果 | 实际证据 |
|---|---|---|
| 1. 结构完整、时间正确 | PASS | 三套严格Pydantic结构；A 5+8+10+10+10+2，B 2+8+8+15+10+2，大学同A，均45分钟；目标/可观察标准/先修/环节齐全 |
| 2. 2–3课堂示例 | PASS | 每套2个：A count/sum；B count/even_sum；大学sum/pairs；全部有代码和独立固定用例 |
| 3. 基础/进阶/挑战 | PASS | 初中countdown/even_sum/multiples各一档；大学sum/divisors/primes各一档，唯一稳定ID |
| 4. 参考答案、评分、用例完整 | PASS（产物/自动验收） | 每题代码、固定测试规格与评分合计100；大学补齐初始化/保持/退出、终止性和复杂度参考论证，Markdown不再丢解题说明；真实教师仍须审核 |
| 5. 全部示例与参考解真实执行 | PASS | 最终新报告：A 5程序17用例、B 5程序18用例、大学5程序16用例，全部PASS/exit_code=0；共15程序51用例；新报告ID不同于原生成报告，非历史复用 |
| 6. 5未交/3死循环正确理解 | PASS | A两条独立观察、分母40、来源JSON位置与Hash齐全；5未交支持诊断/补交，不据此断定能力差；3死循环支持终止追踪 |
| 7. 不推断成8个不同学生 | PASS | 交集明确未知，比较协议unique_affected_students=null；不相加，也不据此计算合并比例 |
| 8. 班情改变实际安排/练习重点 | PASS | A先修5/终止10/边界10分钟，B变2/8/15；第二示例while累加→for偶数累加；追踪支架→边界表；边界分20→40；B 0未交不安排补交流程 |
| 9. 初中/大学有实质深度差异 | PASS（技术/产物） | 初中变量追踪/计数/累加，大学嵌套计数、约数/素数题及具体不变量/终止性证明；大学评分50程序/30论证/20复杂度，非只换术语 |
| 10. 预警含证据/原因/干预 | PASS（结构与依据链） | misconception_type、evidence_ids→事实count/source_ref、trigger、cause、cause_status=hypothesis、teaching_intervention、exercise_ids、stage齐全；无依据标predicted，病因不伪装为事实 |

发现并修复的具体问题：①归档阈值未覆盖单份教案+规则模板，且旧逐文件验证指令与整课批量工具冲突；提前归档并明确工具适用范围，未提高预算；②0未交仍可能安排补交，现按事实区分0与未知；③大学参考解原先只有评分术语，无相应参考论证，新增具体说明与课程风险闸口；④Markdown遗漏练习解题说明；⑤实际模型文案混淆for迭代器耗尽与while退出、循环执行/条件判断次数、变量更新后不变量形式、素数计数保守上界。最终通过单项修订纠正，**没有改代码/冻结用例以换取通过**。

最终151项后端回归+8项真实教育集成PASS，0失败/0错误/0跳过；另有最终15份代码/51条真实用例PASS（这51条不重复累计为pytest数量）。代码Hash、原冻结规格ID/Hash在修订前后保持一致；旧报告、旧错误文本和预算/连接失败均保留。A/B/大学最终revision为2/5/7，教师审核仍PENDING、delivery_ready=false；自动验收审校不代表真人教师批准。

可核查：[最终结构化差异](../.runtime/stage04-acceptance-corrected-artifact-recheck-comparison.json)、[完整修订与新执行证据](../.runtime/stage04-acceptance-corrected-artifact-recheck.json)、[三套原始真实模型记录](../.runtime/stage04-acceptance-final2-live-model.json)、[151项后端JUnit](../.runtime/stage04-acceptance-final2-backend.xml)、[8项真实Runner集成JUnit](../.runtime/stage04-acceptance-final2-real-tests.xml)、[来源Hash与清理汇总](../.runtime/stage04-acceptance-corrected-summary.json)。完整命令、每套教案JSON及已知网络限制见PROGRESS专项验收末节。

浏览器/Playwright、真实教师最终教育审核、公网/持续Runner/正式发布/ZIP仍NOT_TESTED。临时容器/镜像标签/远端源码已独立确认清理；模型长响应直连不稳定，本轮明示采用本机证书校验的SSH TLS字节转发，Key未上传。最终recheck阶段model_called=false，只修订现有真实生成稿并实际重测；其pytest=NOT_TESTED与前面的独立回归证据分开记录。

## 14. 阶段05 — PC/Web正式交付（2026-10-29–30）

功能实现与自动化验收已完成，人工教育判断不在自动化PASS中。命令、失败修复经过、源码与运行证据见PROGRESS末节；下表不借用模型自述判断执行成功。

| 项目 | 结果 | 实际证据 |
|---|---|---|
| PC一键启动、真实本地目录、共享GUI/Core | PASS | `start-desktop.sh --workspace <仓库外真实目录> --runner-ssh ... --port 18007`实际运行；Python3.12、真实百炼、私有ISOLATED Runner；自动开GUI。macOS原生目录弹窗另列NOT_TESTED |
| PC正式文件创建/覆盖/删除及拒绝 | PASS | `test_delivery.py`真实UTF-8/CRLF文件：覆盖拒绝前后字节一致；确认后字节变化；删除拒绝文件仍在、接受后消失、恢复Diff接受后重新出现 |
| 文件Hash/版本/权限/路径/审批闸口 | PASS | 旧草稿/外部改文件/跨会话/无PC能力口令/链接外跳拒绝；代码新版本未测、待审整包变旧均不能写入；旧PASS不直接恢复 |
| 多文件部分中断、持久提交后崩溃恢复 | PASS | 注入第二文件写入失败：首文件保留现场、第二文件未写，不自动重放；恢复Diff经确认再回退。提交完成但工具尚未回填时重开SQLite，补齐一次工具消息、mtime不变 |
| PC真实模型完整主线与进程重启 | PASS | Chrome初中A班5程序/17用例；逐项接受、正式Diff拒绝/再接受、真实落盘、ZIP；待审批与已提交各杀进程重启，快照、文件、审核与会话保留 |
| Web真实模型完整主线与故意失败 | PASS | Chrome初中B班5程序/18用例；故意错误实际stdout不匹配，恢复原代码后同规格PASS；逐项接受、正式Diff、ZIP、刷新与新cookie资源404 |
| 公网第二浏览器引擎与大学配置 | PASS | WebKit26.5从新上下文访问 `https://111.229.226.186`，真实大学A班5程序/16用例、逐项接受、正式提交、ZIP、刷新和归属隔离；`.runtime/stage05-webkit-browser.json` |
| 两学段、两班情教育结构/代码交付 | PASS（技术/内容协议） | 5项真实容器交付测试覆盖初中A/B、大学；固定规格、45分钟、三档评分及完整包；浏览器真实模型三场景共15程序/51条初始用例。人工内容适配判断仍待教师 |
| ZIP内容/报告/版本Hash | PASS | 三份浏览器实际下载包独立解包：各5份Python与5份PASS报告；JSON/Markdown/题目评分/规格/manifest齐全，Hash全匹配；当前包另有正式提交凭据 |
| 持续部署与外网HTTPS | PASS | 实际证书链、IP SAN、外网curl、Chrome/WebKit；API无Docker Socket且只绑定127.0.0.1，Manager无公网端口；数据持久卷与重启策略；原默认站点保留 |
| 156后端、前端类型/构建、静态Review | PASS | `.runtime/stage05-final-backend.xml`；ruff；TypeScript/Vite；ui-ux与ui-ux-pro-max认知/布局取舍、web-design-guidelines源码/截图Review |
| Firefox兼容性 | FAIL（本机测试环境） | Firefox图形子进程启动超时，未进入产品页面；保留 `.runtime/stage05-chrome-pass-firefox-launch-fail.json` 的整体FAIL。该文件内两个Chrome场景独立PASS，第二引擎由WebKit补齐 |
| 真实教师教育审查/现场机器/≤5分钟视频 | NOT_TESTED | 审核点击均为明确标识的自动化合成动作；阶段06继续完成真实教学审查与最终面试交付 |
| 原生目录弹窗、第三条独立网络、证书未来续期 | NOT_TESTED | CLI选目录已测；现有PC网络到VPS的HTTPS已测；证书首次签发、当前有效期和每日续期定时器已检查，未来运行尚未观测 |

本轮明确限制：多文件逐文件原子替换，整组可能部分写入，须依提交日志和恢复Diff人工确认；不声称整组文件系统事务。Web为有限预算演示，非生产多租户部署。IP证书到期为2026-11-05 14:07（Asia/Shanghai），每日续期检查已启用。无Git提交/推送，无密钥进入仓库。最终三份文档与命令在本轮更新，不将阶段06尚未交付的视频/现场验收标PASS。

最终运行汇总：[stage05-summary.json](../.runtime/stage05-summary.json)。业务源码与部署逐文件Hash核对PASS；最后一次156项后端/5项真实容器回归均无失败、无skip。重部署后历史正式包仍可导出。运行证据仅保存在本机忽略目录，不包含模型Key或SSH口令。

## 15. 阶段05专项验收 — 全新工作区复验（2026-10-30）

本轮重新执行，不把第14节的历史结果直接计为本轮通过。PC使用仓库外全新真实目录 `/private/tmp/yunyun-stage05-teacher-d8m6_ob2`；Web使用新的浏览器上下文、cookie和沙箱工作区。未复用上轮会话。审核点击为自动化合成教师动作，不能代替人工教育判断。

| PC步骤 | 结果 | 本轮实际证据 |
|---|---|---|
| 1 启动本地服务 | PASS | 新PC API进程监听127.0.0.1:18006；独立验收数据库避免恢复探针影响原PC会话；继承并合并原费用预留 |
| 2 打开真实教案目录 | PASS（运行配置绑定） | 绑定上述真实目录，文件树与实际文件一致；原生目录选择对话框未操作，另列NOT_TESTED |
| 3 提出备课需求 | PASS | Chrome发送自然语言，真实百炼调用get_education_context/propose_lesson/verify_lesson |
| 4 生成并查看文件 | PASS | 生成完整教案、示例与三档题；批准后在界面打开实际published教案文件并核对“教学目标”内容 |
| 5 执行真实代码测试 | PASS | 5程序、17条固定用例通过；报告不是模型自报 |
| 6 拒绝一次文件修改 | PASS | 界面修改已有formal.md、查看覆盖Diff、拒绝；文件bytes与原始值完全相等，不仅仅拒绝新建文件 |
| 7 接受一次修改 | PASS | 对同一草稿重新审批并接受；正式文件字节与编辑值完全一致 |
| 8 重启后恢复会话 | PASS | 待审批、已提交教案包、已有文件接受后三次SIGKILL重启；原会话恢复、正式文件内容保留且mtime未变化，无重复写入 |

| Web步骤 | 结果 | 本轮实际证据 |
|---|---|---|
| 1 打开部署地址 | PASS | 实际HTTPS地址 https://111.229.226.186；证书校验开启；Chrome/WebKit完整链路，不仅检查HTTP200 |
| 2 导入班级练习数据 | PASS | 文件输入控件实际选择class_B.csv；服务端只读核对source_hash与上传文件SHA256一致；观察为0未交/0死循环/8边界错误 |
| 3 输入循环结构备课要求 | PASS | 新会话真实模型处理45分钟自然语言需求 |
| 4 查看教案与分层练习 | PASS | 界面切换教案、示例、三档练习；45分钟、2示例/3练习、每题100分结构断言通过 |
| 5 展示真实验证失败 | PASS | 候选改为print("intentional-wrong")；n=0实际输出不为空，真实OUTPUT_MISMATCH，退出0也不算通过 |
| 6 修复或阻止错误交付 | PASS | 失败代码“接受”按钮禁用；package与delivery直接请求均409且无新审批；恢复代码后原固定规格不变、真实重测通过 |
| 7 查看错因预警 | PASS | 展开错因页，逐条核对触发条件、原因假设和课堂干预；观察/预测标签及班情依据可查看 |
| 8 审核并导出教案包 | PASS | 逐项接受、查看Diff、拒绝/再接受正式交付后下载ZIP；5份Python/固定规格/教案JSON与Markdown/评分/报告/manifest/提交凭据齐全且Hash一致 |

附加验收：

- **UI与状态 PASS（本轮范围）**：浅紫白色、历史/对话/可展开工作区、Lucide、文件Diff与逐项审核符合UI_GUIDELINES。修复长操作只有置灰反馈：运行测试/保存/审批增加明确状态；下载增加加载状态、防重复触发；文件读取有状态；编辑保存时禁止重复操作。真实非法评分返回422，明确显示错误并保留编辑值/原版本；测试与下载加载态通过仅延迟真实请求的自动化检查，未伪造执行结果。
- **共享核心 PASS**：本机与部署容器实际导入的Agent、教育服务、工具、验证、提交、工作区模块逐文件Hash一致；三场景使用相同Runner策略Hash和同一原生工具链。两端React业务源代码一致，构建产物分别核验；未将不同构建环境的压缩产物声称为逐字节相同。
- **权限边界 PASS（已测入口）**：每场景7种越界/绝对/敏感/混合路径请求均403；跨cookie读取会话/文件、修改草稿均404；Web本地目录接口403、客户端指定服务器root为422、跨源写入403。实际API容器仅挂/data及私有Runner socket，无Docker Socket。真实候选容器观察无宿主/app、/root/.ssh、模型Key与Docker Socket、不能写根目录/访问外网；资源限额及派生进程清理通过。此结论只覆盖已测接口和隔离策略，不是任意敌意代码的强隔离证明。

本轮命令：

```bash
.venv/bin/python -m pytest backend/tests/unit backend/tests/integration/test_api.py backend/tests/integration/test_education_api.py backend/tests/integration/test_session_resume.py backend/tests/integration/test_delivery.py -q -o junit_family=xunit1 --junitxml=.runtime/stage05-acceptance-backend.xml
.venv/bin/python scripts/verify_stage05.py root@<授权宿主> --browser --url https://111.229.226.186 --evidence-prefix stage05-acceptance
.venv/bin/python scripts/verify_stage05.py root@<授权宿主> --tests-only --evidence-prefix stage05-acceptance
npm --prefix frontend run build
.venv/bin/ruff check backend scripts
```

结果：**156项后端通过**；其中安全/恢复专项78通过是子集，不重复计数；**6项真实容器交付/隔离通过**；Chrome PC A班/Chrome Web B班/WebKit大学A班三场景通过，15程序/51条初始用例，另有故意失败及修复执行；所有三份ZIP均15文件，Hash全匹配。无失败/skip，后端保留1条既有Starlette弃用警告。

本轮证据：[汇总](../.runtime/stage05-acceptance-summary.json)、[浏览器逐项结果](../.runtime/stage05-acceptance-browser.json)、[156项JUnit](../.runtime/stage05-acceptance-backend.xml)、[6项真实容器JUnit](../.runtime/stage05-acceptance-real-delivery.xml)、[上传文件Hash](../.runtime/stage05-acceptance-upload.json)、[ZIP核对](../.runtime/stage05-acceptance-packages.json)、[失败截图](../.runtime/stage05-acceptance-web-chrome-B-failure.png)、[处理中截图](../.runtime/stage05-acceptance-web-chrome-B-verifying.png)、[实际文件覆盖Diff](../.runtime/stage05-acceptance-pc-chrome-A-overwrite-diff.png)。均为本机忽略的运行证据。

**NOT_TESTED**：原生目录选择对话框的人工点击、真实教师对教学内容/难度/评分的专业审核、第三条独立外部网络。Firefox本轮未重跑，不借用Chrome/WebKit通过结论声称Firefox兼容。PC自动化验收进程结束后已清理，真实目录、文件和证据保留。未提交/推送Git，未增加业务功能。


## 16. 阶段05评审五项缺陷回归（2026-10-30）

范围为评审列出的两项P1、三项P2修复，优先恢复完整流程，没有继续增加业务功能。第15节的公网主线PASS为历史证据，本轮未重新发布，不能据此宣称线上已包含修复。

| 问题 | 结果 | 可复查条件 |
|---|---|---|
| 提交中断无法恢复 | PASS | 真实子进程在写前、首文件替换后、全部文件替换后但日志未完成时os._exit(73)；重开SQLite/Agent后四类记录同步INTERRUPTED；恢复/新提交（含同目录另一会话）返回RECOVERY_REQUIRED。全未写拒绝、部分回退、全已写确认均可继续原任务；后者mtime不变，原调用仅一个最终工具结果/一个提交日志 |
| 迟到响应污染会话 | PASS（界面控制流） | Chrome/WebKit延迟A保存/验证/审批及文件响应，切B并发起B审批，再释放A；选中会话/消息/预览/审批始终为B，B的pending不被清除。A游标100、B游标2；迟到班情读取也被丢弃，文件选择不残留 |
| Python删除入口分歧 | PASS | 使用真实Agent工具协议的脚本Provider提出.py删除，能进入PENDING；拒绝保持原字节，接受后真实文件消失；存在其他未通过Python时仍VERIFICATION_REQUIRED。6项真实容器回归额外覆盖失败代码/过期验证不得交付 |
| 覆盖扩大读取权限 | PASS | 实际0600文件批准覆盖、历史回退后内容/权限均正确；新文件0600；模拟旧待审批无权限字段，600/640均在实际新提交时记录并正确回退 |
| 1 MiB上传协议 | PASS | 前端File原字节POST /class-profiles/upload，CSV/中文转义JSON/540065字节/1048576字节/BOM均核对Hash，超过上限明确报错。真实后端测试普通及BOM JSON三个大小，返回与持久化source_hash均为上传原始字节Hash，1048577字节413 |
| 对账边界与UI | PASS | 新GET/POST入口检查会话所有权、跨cookie404、版本冲突、磁盘快照Hash及未知外部修改；未知外部文件不被覆盖。界面显示Diff/Hash/权限、可用与禁用操作、加载/错误提示，完成后解除继续任务的阻断 |

实际命令：

```bash
.venv/bin/python -m pytest backend/tests/unit backend/tests/integration/test_api.py backend/tests/integration/test_education_api.py backend/tests/integration/test_session_resume.py backend/tests/integration/test_delivery.py backend/tests/integration/test_stage05_review.py -q -o junit_family=xunit1 --junitxml=.runtime/stage05-review-backend.xml
.venv/bin/python scripts/verify_stage05.py root@111.229.226.186 --tests-only --evidence-prefix stage05-review
YUNYUN_PLAYWRIGHT_MODULE=/Users/chenxi/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright node scripts/review-stage05-browser.cjs
.venv/bin/python scripts/smoke_startup.py
npm --prefix frontend run build
.venv/bin/ruff check backend scripts
git diff --check
```

结果：**172项后端PASS**（新增16项；1条既有Starlette弃用警告）、**6项真实容器PASS**、**22项Chrome/WebKit界面控制流PASS**；PC/Web进程启动/重启冒烟PASS（显式Mock）。浏览器HTTP后端为显式夹具，仅检验竞态、传输与对账交互；真实文件、数据库、API所有权与真实代码执行分别由后端/容器回归证明，没有把夹具响应当作真实验证证据。后端需按以上显式集合运行：直接混合收集全目录会遇到既有同名test_education模块；真实集成另需Runner socket配置，未配置不应计PASS。

证据：[后端JUnit](../.runtime/stage05-review-backend.xml)、[真实容器JUnit](../.runtime/stage05-review-real-delivery.xml)、[浏览器逐项结果](../.runtime/stage05-review-browser.json)、[会话归属截图](../.runtime/stage05-review-chrome-session-scope.png)、[对账界面](../.runtime/stage05-review-chrome-recovery.png)。UI检查采用本轮截图及源码，遵循UI_GUIDELINES，保持浅紫/白色、历史/对话/可展开工作区，突出恢复Diff与明确审核按钮。

**NOT_TESTED/剩余边界**：本轮代码的公网部署和公网完整备课未做；真实模型整课未重跑；真实教师教育审核、原生目录选择器人工操作未做。修复前历史日志缺失的原权限无法推断，采用保守0600；未知外部文件变更仍需人工核对后重新对账。未Git提交、推送或更新生产配置。
