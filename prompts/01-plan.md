# Codex Prompt 01：需求分析 + 架构定案（本轮不写业务代码）

阅读 `AGENTS.md`、`docs/INTERVIEW_REQUIREMENTS.md`、`docs/PLAN.md`、`docs/ACCEPTANCE.md`，检查 `git status`。

本项目完成周期只有 48 小时。主要由 Codex 编写，不考虑开发者固有技术栈。候选架构已定为：Python 3.12 + FastAPI + Pydantic + SQLite；React + TypeScript + Vite + Tailwind/shadcn；pytest + Playwright；受控 mini Agent Loop；PC 本地服务、Web 公网部署，同一个 Agent Core。除非有可验证的硬阻塞，不要泛泛重选技术栈。

本轮做以下事项，**只修改设计与跟踪文档，不启动大规模业务编码**：
1. 对照原题的 A/B/C/D 四类 P0 和交付要求，补全逐条验收矩阵，定义可观测的 PASS 标准。将初二《循环结构》作为首个打穿场景；保留大学/初中不同学段配置。
2. 设计 Agent Loop：模型工具调用→真实执行→工具结果入上下文→后续推理；支持单次请求/工具超时、取消、失败处理；能暂停待审批、重启恢复。模型调用不设置费用、累计Token、次数或总时长预算。
3. 设计模型 Provider 与工具注册表；确认备选 API 是否支持 tool calling（不能只看 OpenAI 兼容名称）。
4. 设计工作区协议、草稿→验证→教师审核→正式落盘状态机，拒绝和版本回退，以及文件内容 Hash 与测试报告关联。
5. 设计结构化 `ClassProfile/LessonPlan/Example/Exercise/Misconception/TestCase/VerificationReport/Approval/Session`；明确学情→教学策略的依据链，避免仅靠 Prompt 话术。
6. 制定代码执行隔离方案：Web 独立 Runner，资源/网络/文件权限受限，不能把 Docker Socket 暴露给公网 API；PC 本地不能宣称普通子进程是强沙箱。
7. 确认实际运行机器与公网部署方案的可行性，明确 0-5h 要完成的最小部署验证任务。
8. 设计 `workspace` 本地与 `sandbox` Web 适配边界、前后端 API 与 SSE 事件。
9. 按 6 阶段分解工作并写清每阶段验收、最危险依赖和回退路线。
10. 列出 5 个最可能导致无法交付的阻塞及优先处理顺序。

把决策写进 `docs/PLAN.md`，按实际信息修订 `docs/ACCEPTANCE.md`。不要声称不存在的环境/部署已经验证。最后给出你认为最先应该编码的纵向切片，以及我需要人工把关的 3 个决定。
