# Codex Prompt 02：工程骨架 + 真实 Agent Core + 会话恢复

先检查 `git status`，阅读 `AGENTS.md`、原题、`docs/PLAN.md`、`docs/PROGRESS.md`，仅在本阶段范围内修改。此轮直接编码、运行和修复，不要只给思路。

交付：
1. 创建 Python 3.12 FastAPI 后端、Pydantic 模型、SQLite 持久化、pytest；创建 React + TS + Vite 前端，基本页面和健康检查。
2. 完成至少一个真实大模型 API 的 Provider：Key/URL/Model 通过 `.env` 配置，严禁写进代码和 Git；可准备 Mock LLM 兜底，但必须醒目标识。
3. 实现真实 `AgentLoop`：模型返回结构化 tool calls、系统按工具白名单执行、把真实结果返回模型再推理，不是一个固定的生成流水线。记录调用次数、耗时和实际用量，不设置最多步数、累计总时长、工具总次数或费用/Token预算；保留单次请求/工具超时和异常处理。
4. 至少实现 `list_files`、`read_file`、`propose_patch`/草稿写入、`run_python_tests` 接口（Runner 可由阶段 3 完善，但不能伪造测试通过）。
5. 实现 Workspace、path 校验、工具参数 Pydantic 校验和权限 Policy；读取授权文件和临时草稿自动执行，正式覆写/删除走待审批，不允许 Agent 用其他工具绕过审批。
6. 实现 Session 的消息、工具记录、工作区与审批状态最小持久化；服务重启能够 resume，不能只还原聊天文本。
7. React 显示聊天、文件列表、Agent 事件、失败状态；通过 SSE 或等效流式事件展示真实执行步骤。
8. 初始化最低可行的本地 PC 启动入口与 Web 部署骨架；现在就验证远端服务器是否可以运行 backend/frontend，尽早暴露网络和 Docker 限制。

必须实际运行并记录：
- 前后端编译/启动成功；
- 自然语言调用真实文件读取工具，并把结果返回 LLM 后继续下一步；
- 触发不允许路径时拒绝；
- 中断/重启会话后能恢复既有工作区与消息；
- API 不可用时清楚返回错误，不伪造功能；
- 自动化测试实际执行。

更新 `docs/PROGRESS.md` 与 `docs/ACCEPTANCE.md`，汇报命令、结果和未完成 P0。不要跨阶段美化 UI 或实现完整教学业务。
