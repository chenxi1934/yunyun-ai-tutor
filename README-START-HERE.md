# 耘耘AI助教 — 交付入口与开发过程

> 当前目录已包含实现源码。安装、运行和部署以 [README.md](README.md) 为准，实际通过项与未完成项以 [最终验收](docs/ACCEPTANCE.md) 为准；下方48小时安排和阶段指令保留为开发过程资料。

## 技术栈（已经从 Java 彻底替换）
- Python 3.12 + FastAPI；Pydantic；SQLite
- React + TypeScript + Vite；Tailwind CSS + shadcn/ui
- 自实现受控 mini Agent Loop；至少一个具有实际 tool-calling 能力的大模型 API
- SSE 反馈 Agent/测试进度；pytest + Playwright
- PC：本地 FastAPI + 本机浏览器 GUI，真实工作区
- Web：同一套前后端，共享 Agent Core，受控 Web 工作区，隔离 Python 执行环境
- 部署：优先有 Docker 权限的 VPS + Docker Compose + HTTPS 反向代理

## 第一次使用

1. 保留已有 Git 历史与本地修改，不需要重新初始化仓库或重做开发阶段。
2. 按 README 安装 Python 3.12 和 Node 依赖、构建前端；复制 `.env.example` 为忽略的本地 `.env` 并填写真实模型密钥。
3. 配置私有 Runner 或 README 中的 SSH 控制连接，使用 `start-desktop.sh --workspace` 启动新教学目录；公网演示入口同样见 README。
4. 在最终现场机器上重新运行完整主线；本机已测不能替代换机验收，合成审核动作不能替代专业教师审核。

## 48 小时安排（时间预算）
| 时间 | 目标 | 验收闸口 |
|---|---|---|
| 0-5h | 需求/架构 + 骨架 + 部署预验证 | 前后端最小启动；技术风险清楚 |
| 5-15h | Agent Loop / tools / sessions | 真实工具调用并反馈模型；重启恢复 |
| 15-24h | Python Runner / 用例 / 自动修复 | 有意失败可重现；未通过不得交付 |
| 24-33h | 教案/习题/班情/错因 | 两份班情有可解释差异；均有测试 |
| 33-43h | PC/Web、审批、导出与部署 | 本地真实文件；公网 URL 端到端 |
| 43-48h | 回归、视频、文档、交付 | 全套 P0 验收；保留未完成项 |

## 人工验收纪律
- 不要等全部完成再第一次部署 Web；在最初 5 小时里先打通最小部署。
- 不要以 LLM 的自述作为测试通过证据；必须真实运行测试命令。
- 不要允许 Codex 随意推翻架构，也不要让它在未验收时连续增加功能。
- 每个阶段检查 `git status`、变更 Diff、测试结果和 P0 矩阵。
- 按2026-10-30用户决定，模型调用不设置费用、累计Token、次数或总时长预算，只记录实际用量；单次请求超时和执行隔离保留。
- 模型 API Key 放在 `.env`，永不写进 Git。保留 Mock LLM 兜底可以，但要显著标注；代码执行与测试绝不允许 Mock 通过。

## 重要安全边界
- PC/Web 的教学代码均须使用真实容器隔离；隔离器不可用时阻断执行和交付，不降级到宿主子进程。
- Web 使用独立执行环境，隔离网络、文件系统和资源；**不要把 Docker Socket 直接挂给面向公网的 FastAPI 应用**。
- Web 不得接受任意服务器绝对路径；PC 仅在用户选择的工作区内访问已授权文件。
- Agent 可提出草稿/变更，但正式文件覆盖和删除必须教师确认；拒绝后保证可回退。

## 重要输入与成果
- 面试题：`docs/INTERVIEW_REQUIREMENTS.md`
- 核心约束：`AGENTS.md`
- 方案与验收：`docs/PLAN.md`、`docs/ACCEPTANCE.md`
- 进度与证据：`docs/PROGRESS.md`
- 真实 AI 开发纠错：`docs/AI_DEV_LOG.md`
- 最终一页文档：`docs/DESIGN_DECISIONS.md`
- 分阶段指令：`prompts/`

## 最终提交
公网 URL（若不可稳定部署，则录屏 + 部署说明）/ 桌面一键启动命令 / <=5 分钟视频 / Git 源码与历史 / 一页设计与教育判断 / Prompt 与错误修复实例。
