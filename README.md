# 耘耘AI助教

教师备课 mini Agent，PC/Web 共享 **React / TypeScript / Vite UI** 和 **Python 3.12 / FastAPI / Pydantic / SQLite Agent Core**。首版聚焦45分钟《循环结构》，支持初中与大学，单个会话为一个班级备课。

**Web 演示：[https://111.229.226.186](https://111.229.226.186)**。当前配置真实百炼 `qwen3.8-max`，已连接独立容器 Runner，非 Mock。演示只使用汇总/合成班情，不上传学生姓名、学号或真实学生代码。

2026-10-30 交付修复已上线：`delivery-20261030050342-d490cddca8`。下载包新增6份可离线阅读/打印的HTML、独立学生练习与教师答案、易读逐用例报告；保留原始Python及可复用数据。全量后端284项（含42真实容器）、前端70项与构建通过；最终下载代码再次真实执行22条原/上界用例通过。功能提交`88e9774`已推送公开master，应用源码Hash与线上26模块及静态资源实测一致，详见验收第33节；完整证据见[验收第31节](docs/ACCEPTANCE.md#31-交付封闭离线教师包与最终复验2026-10-30)。真实教师专业审核、现场换机、视频成片/链接仍待完成。源码[GitHub仓库](https://github.com/chenxi1934/yunyun-ai-tutor)已公开并通过匿名访问核验。

## 安装

需要 Python **3.12**、Node **22.19+**、npm；不要误用 macOS 系统 Python 3.9。

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --index-url https://pypi.org/simple -e '.[dev]'
npm --prefix frontend install --package-lock=false
npm --prefix frontend run build
```

安装命令显式使用官方 PyPI，避免本机已有镜像配置缺少构建依赖；无需修改全局 pip 配置。

参照 `.env.example` 在本地 `.env` 配置 `DASHSCOPE_API_KEY`；保留已有配置，不将凭据提交 Git。默认百炼兼容地址 `https://dashscope.aliyuncs.com/compatible-mode/v1`、`qwen3.8-max`，关闭 thinking；输入/输出价格仅用于可选费用估算，未配置价格不阻断模型调用。默认失败不会切换 Mock；只有显式 `LLM_PROVIDER=mock` 才进入带 `MOCK_LLM` 标记的演示，代码仍须真实执行。

```bash
if [ ! -e .env ]; then cp .env.example .env; fi  # 已有文件不覆盖
chmod 600 .env
# 用编辑器填写密钥，避免写入命令历史；不要添加到 Git
```

## PC 一键运行

在仓库外创建教师教学目录，放入 UTF-8 Markdown / TXT / JSON / CSV / Python 文件。

本轮验证的是当前macOS arm64，用户已确认现场会换机器；现场须重新安装依赖/构建、配置密钥与SSH并完成真实主线，不能沿用本机PASS。Windows启动未验。

```bash
# 已有本机私有Runner配置时
bash scripts/start-desktop.sh --workspace /绝对路径/教师教学目录

# 复用本项目服务器上的私有Runner，无需本机安装Docker
# 密码登录示例：首次核对主机指纹，再输入密码；不将密码写进命令或文件
mkdir -p .runtime
ssh -M -S "$PWD/.runtime/ssh_control" -o ControlPersist=3600 \
  -o UserKnownHostsFile="$PWD/.runtime/ssh_known_hosts" \
  -o PreferredAuthentications=password -fN root@111.229.226.186
# 也可使用已配置好的 SSH agent；普通一次性 SSH 登录不会保存后续脚本的鉴权
bash scripts/start-desktop.sh \
  --workspace /绝对路径/教师教学目录 --runner-ssh root@111.229.226.186
```

启动后自动打开浏览器。macOS 省略 `--workspace` 会弹出原生目录选择器；页面的“打开本地工作区”也可为新会话选择目录，旧会话继续绑定原目录。`--port 8001` 更换端口；`--no-browser` 供进程探针使用。原生选择器尚未人工验收，CLI指定真实目录已实际验证。

本机服务只监听 loopback；能力口令通过 URL fragment 传入标签页，随即清除并保存在 sessionStorage，不进入日志。重启后通过启动入口重新打开页面以获得新口令，会话与历史继续保留。工作区不能包含应用数据库；密钥/隐藏文件、路径越界、符号/硬链接均拒绝。支持范围为教学文本，每文件64 KiB、最多200个可见文件。

`--runner-ssh` 仅经加密SSH读取私有Runner配置并建立权限受限的Unix socket转发，退出清理转发；不把Token打印或写入前端。未连接有效隔离器时，PC/Web均明确显示执行器不可用，禁止代码交付，不降级到宿主子进程。

## 教师操作流程

1. 选择学段、年级、主题，粘贴本班汇总情况或上传JSON/CSV；可下载合成模板参考格式。发送“根据班情备一节45分钟循环结构，生成示例和三档练习并真实测试”等自然语言需求。
2. 查看对话和工具执行进度；右侧工作区按教案、示例代码、分层练习、错因预警展开。每条程序报告显示输入、期望、实际、stdout/stderr、退出码、耗时与Hash；失败不能接受或导出。
3. 逐项接受、拒绝或继续修改；可编辑文字、代码与评分点。代码变更使旧PASS失效，重新运行后才能接受。历史版本可恢复为新草稿，重新验证/审核。
4. 全部代码通过且全部教学项目接受后，点击“审核交付文件 Diff”。检查每个文件的新建/覆盖/删除、原Hash与新Hash，再“确认接受并写入”或拒绝。正式内容写入 `published/<lesson_id>/`；拒绝不改变文件字节。
5. 下载ZIP后解压并双击“开始阅读.html”：离线查看教案、课堂示例、独立学生练习、教师答案与评分点、逐用例验证报告。学生只需“学生练习.html”，不要整包发放。保留5份Python代码及可选JSON/Markdown/测试规格/Hash清单和正式提交回执。文件被外部修改、教案/用例/报告变更、验证过期或审核撤销后，下载被阻断；更新导出格式后，旧交付也需重新审核文件Diff并确认，才能下载新格式。

模型若只回复文字而未生成教案，该次备课没有完成；以教案和真实报告为准。教材内的样本编号只是资料，模型误读时须明确澄清。连接/超时错误如实显示，可点击“继续当前任务”恢复；保留失败和未知usage，不将重试前的失败算作通过。

“文件与Diff”视图可读真实文件、创建/修改草稿、提出删除和审核单文件变更。待写入的Python内容需要冻结测试与真实验证；删除Python仅核对路径、原文件Hash及教师审批，其他失败或漏测代码仍阻断交付；它不提供任意shell或完整IDE。普通文件提交历史可创建回退Diff，再确认写入；历史代码不能直接恢复旧PASS，须先恢复教学项目为新版本并重测。

多文件提交**逐文件原子替换，不承诺整组文件系统事务**。写入失败或重启恢复时，提交、审批、关联任务和工具调用同步中断，不自动重放。在“正式文件历史与恢复”点击“对账恢复”：全部未写入可确认拒绝；全部已写入可确认完成（不重写）；部分写入须查看回退Diff、明确确认后只回退已写入项并拒绝。内容或权限出现未知外部修改时保留现场，人工核对后重新对账。对账绑定磁盘Hash、权限及会话版本，解决前同一真实目录禁止新提交/导出，原任务须先完成对账再继续。

覆盖保留原文件rwx权限；新文件默认 `0600`，提交日志记录回退所需权限。修复前的历史日志若未记录权限，无法推断原权限，回退采用保守 `0600`；旧待审批记录在本轮代码实际提交时会补齐权限。普通已完成提交仍通过新审批Diff回退，历史Python恢复仍须验证；中断对账回退只撤销未完成提交，不产生代码PASS证据。单API worker，同一实例串行执行Agent与验证任务。

## Web 部署

当前API容器只绑定 `127.0.0.1:18005`，Nginx提供HTTPS；现有默认站点保留。私有Manager不发布TCP端口；API无Docker Socket。新会话复制7个合成种子文件，资源绑定HttpOnly / SameSite=Strict / Secure cookie；刷新恢复，本浏览器之外的会话不能读取它的资源。

在已授权、已安装Docker/Nginx/OpenSSL的宿主上，先通过SSH登录，再从本机运行：

```bash
.venv/bin/python scripts/deploy-web.py root@111.229.226.186 --domain 111.229.226.186
curl -fsS https://111.229.226.186/api/runtime
```

脚本只替换本项目命名的API/Manager容器，保留 `/opt/yunyun-tutor/data`；凭据通过SSH stdin写入宿主0600配置，不进入源码包、构建参数或日志。会话数据库与工作区持续保存，容器配置自动重启。部署需要现有SSH鉴权，不在参数中提供口令。

阶段05/06增量更新仅切换API/React镜像：先构建独立版本、隔离数据探针、停机备份，再切换；保留现有Runner、运行配置、Nginx/证书与原工作区。旧API停止并保留为回退容器，SQLite及数据归档备份存于版本目录。阶段06-2从干净副本启动PC并对公网API/Manager冷重启的证据保留在ACCEPTANCE第20节。本轮UAT已发布新API/React镜像，生产逻辑记录及334个工作区文件Hash一致；当前ABCD版本公网与隔离验收见第30节，前轮见第28节。空白VPS首次安装、实际切回演练和真正现场换机仍未测试，第17–20节历史不改写。

HTTPS采用 [acme-tiny（MIT）](https://github.com/diafygi/acme-tiny) 与Nginx；部署脚本下载官方客户端，并为IP证书做最小的IP identifier / shortlived profile / SAN适配。当前IP证书有效至 **2026-11-05 14:07（Asia/Shanghai）**，每日systemd任务在剩余2天内尝试续期；已验证首次签发和定时器启用，未来真实续期尚未观测。临时域名曾被云厂商备案拦截，当前使用已实测可访问的IP HTTPS入口。首次部署可用 `--domain` 指定自有域名；迁移域名还须重新核验HTTP验证路由与证书。

模型调用不设置费用、累计Token、调用次数、累计时长或单次输出Token预算，不预扣费用。只记录实际usage及已知价格估算，超时/未知价格标为未知。单次请求/工具超时、失败重试、无进展停止、代码修复次数及沙箱隔离保留。历史调用与旧失败证据不删除。

## 私有 Runner

Manager镜像入口 `runner/Dockerfile`；只有可信Manager可访问Docker Socket，API与候选容器均无此权限。API只配置私有 `RUNNER_SOCKET` / `RUNNER_TOKEN`。自建Manager使用 `python -m runner.manager`，须显式配置预拉取Python 3.12镜像的不可变 `RUNNER_IMAGE`。

每条用例在一次性非root容器运行：无网络、只读根、cap-drop=ALL、no-new-privileges、默认seccomp、0.5CPU、128MiB、32pids、16MiB tmpfs、单case2秒、整程序30秒、stdout/stderr各64KiB。可信外部比对stdout，不信任候选自报PASS；超时/取消回收容器，清理失败关闭Runner。模型Key、教师目录、数据库和其他会话文件不挂入候选。

## API 要点

所有资源校验cookie归属、Host/Origin；PC变更另需本机能力口令。变更带 `expected_revision`；聊天另带幂等键。模型工具不包含教师批准/正式提交能力。

| 接口 | 功能 |
|---|---|
| `POST /api/sessions`、`GET /api/sessions/{sid}` | 学段配置；恢复消息、草稿、报告、班情、教案、审批与提交历史 |
| `POST .../class-profiles` | `{format,content,expected_revision}` 导入文字/JSON/CSV汇总班情 |
| `POST .../class-profiles/upload?format=csv&expected_revision=0` | File原始字节上传，1 MiB上限；UTF-8解析支持BOM，source_hash保留原始字节Hash；不接收multipart |
| `POST .../messages`、`POST .../resume`、`GET .../events` | 自然语言Agent；检查点继续；持久化SSE与游标回放 |
| `PATCH .../lessons/{lid}/items` | `{expected_revision,item_id,replacement,reason}`；稳定ID、时间/评分/冻结任务约束 |
| `POST .../lessons/{lid}/verify`、`POST .../reviews` | 整课真实验证；逐项接受/拒绝，代码PASS不能替代教学审核 |
| `GET .../lessons/{lid}/export`、`GET .../json` | 经审核内容映射；或带未测/失败状态的草稿JSON快照，均不代替正式提交 |
| `POST .../lessons/{lid}/delivery` | 生成精确文件Diff与待审批快照，暂不写入 |
| `POST /api/approvals/{aid}/decision` | `{decision: approve/reject,expected_revision}`；再次核对版本/Hash/验证与审核 |
| `GET .../lessons/{lid}/package` | 仅下载当前仍有效的正式提交ZIP |
| `POST .../drafts`、`POST .../publish-draft` | 文件草稿；请求单文件正式审批 |
| `POST .../commits/{cid}/restore-draft` | 已完成提交生成回退Diff，须再次审核；未解决中断不可走此入口 |
| `GET .../commits/{cid}/recovery` | 中断对账：返回每项 BEFORE/AFTER/UNCHANGED/CONFLICT、现状Hash/权限、回退Diff、snapshot_hash及允许操作 |
| `POST .../commits/{cid}/recovery` | `{expected_revision,snapshot_hash,decision: accept/reject/rollback}`；确认完整写入/确认未写入并拒绝/回退已写入并拒绝；拒绝未知外部修改 |
| `POST .../test-specs` | 教师冻结独立Python文件用例；模型不能改规格 |

上表 `...` 为 `/api/sessions/{sid}`，教案审核为 `.../lessons/{lid}/reviews`。冻结累加基准示例：`{"path":"sum.py","expected_revision":0,"baseline":"sum_1_to_n"}`；固定输入0/1/5分别输出0/1/15并带换行。自定义规格使用 `cases:[{id,input,expected}]`。教学任务有独立固定契约，不能减用例绕过验证。

## 实际验证命令

阶段06完整验收（不自动部署、不提交或推送）：

```bash
# 一次运行全部后端测试，含真实容器；修复同名测试模块收集冲突
# 前提：已通过SSH agent/控制连接登录指定测试宿主
.venv/bin/python scripts/verify_stage06.py root@111.229.226.186 --evidence-prefix stage06-unlimited
npm --prefix frontend run build
.venv/bin/ruff check backend runner scripts

# 真实模型、Chrome/WebKit、全新PC目录/公网会话，会调用真实模型并记录usage
YUNYUN_PLAYWRIGHT_MODULE=/你的现有模块目录/playwright \
  .venv/bin/python scripts/verify_stage05.py root@111.229.226.186 \
  --browser --url https://111.229.226.186 --evidence-prefix stage06-unlimited
```

本轮还以明确教师要求验证模型实际改写至少2个活动/2个讲解；请求正文、usage与原始稿在`stage06-release-*`证据中。已观察的文字错误可在独立公网会话按既有API复验：

```bash
.venv/bin/python scripts/recheck_stage06.py \
  --source .runtime/stage06-release-browser.json --prefix stage06-content
```

该脚本重放本机已有真实模型原稿，**不重新调用模型**；它只修订已观察的具体错误，源稿不同会明确停止。它不是通用教学正确性检测器；合成审核不代替专业教师。源JSON/ZIP在忽略目录，换机须另行保留合成运行证据或重新真实生成，不能凭空运行这个历史来源命令。

全量脚本使用临时私有Manager，不发布端口、不传模型Key；连接真实容器，测试后清理，并记录孤儿回收、镜像/策略与源码Hash。原有两份同名`test_education.py`通过importlib和显式测试路径共同收集，未删除测试或改既定断言。不要在同一专用宿主上并行运行两套Runner故障注入；生产演示空闲时再运行完整验收。

以下为此前阶段保留的专项命令；结果不与全量测试重复计数：

```bash
# 不消费模型Key：当前176项控制流/教育协议/权限/提交/恢复回归
.venv/bin/python -m pytest backend/tests/unit \
  backend/tests/integration/test_api.py backend/tests/integration/test_education_api.py \
  backend/tests/integration/test_session_resume.py backend/tests/integration/test_delivery.py \
  backend/tests/integration/test_stage05_review.py \
  -q -o junit_family=xunit1 --junitxml=.runtime/stage06-offline.xml
.venv/bin/ruff check backend scripts
npm --prefix frontend run build
.venv/bin/python scripts/smoke_startup.py

# React界面专项：显式HTTP夹具，只证明会话/上传/对账UI控制流，不能作为真实LLM/Runner证据
# 若Playwright不在Node解析路径，通过YUNYUN_PLAYWRIGHT_MODULE指向现有安装；不修改项目依赖
node scripts/review-stage05-browser.cjs

# 真实容器交付及隔离：初中A/B、大学、失败/修复/审批过期、网络/文件/进程边界；6项，无模型费用
.venv/bin/python scripts/verify_stage05.py root@111.229.226.186 --tests-only

# 真实模型+真实浏览器，产生真实API用量；已有Chrome时，按需安装项目内测试依赖
npm install --prefix .runtime/browser --no-save --package-lock=false playwright
env -u PLAYWRIGHT_DOWNLOAD_HOST .runtime/browser/node_modules/.bin/playwright install webkit
# 用YUNYUN_PLAYWRIGHT_MODULE指向已有Playwright模块，YUNYUN_CHROME_PATH指定Chrome
YUNYUN_PLAYWRIGHT_MODULE="$PWD/.runtime/browser/node_modules/playwright" \
  .venv/bin/python scripts/verify_stage05.py root@111.229.226.186 --browser --url https://111.229.226.186
```

真实容器测试无Runner时失败，不skip、不使用假报告。浏览器脚本创建全新工作区并实际重启PC进程；审核点击显式标为“自动化合成教师动作”，不是人工教育审查。已通过Chrome双端与WebKit公网主线；本机Firefox因图形进程启动错误未完成，不能据此声称Firefox兼容。证据在忽略的 `.runtime/stage05-*` 下；未将运行凭据或模型Key提交Git。

阶段02–04原生工具/故障/教育探针仍保留在 `scripts/probe_provider.py`、`verify_stage02.py`、`verify_stage03.py`、`accept_stage04.py`；旧阶段证据的适用范围以PROGRESS与ACCEPTANCE历史记录为准。

2026-10-30专项验收使用全新PC目录和Web会话，逐项结果见 [ACCEPTANCE第15节](docs/ACCEPTANCE.md#15-阶段05专项验收--全新工作区复验2026-10-30)。可为上述验证命令追加 `--evidence-prefix stage05-acceptance` 保存独立证据；本轮补测已有正式文件的界面覆盖拒绝/接受与字节核对、实际CSV文件选择导入、失败交付409、加载/错误状态及真实容器越界限制。人工选目录弹窗和教师教育审核保持NOT_TESTED。

## 面试交付材料

- Web：[HTTPS演示](https://111.229.226.186)，实际版本及本轮逐项状态见[最终验收](docs/ACCEPTANCE.md)。
- 源码：origin配置为[chenxi1934/yunyun-ai-tutor](https://github.com/chenxi1934/yunyun-ai-tutor)。最终变更已按用户授权整理为本地Git提交，尚未推送；`git ls-remote origin HEAD`因缺少非交互鉴权失败，面试方能否访问仍未确认，仓库地址不等于远端代码已同步。
- 一页：[设计与教育判断源码](docs/DESIGN_DECISIONS.md)、[A4单页PDF](docs/DESIGN_DECISIONS.pdf)。
- AI使用：[关键Prompt与真实纠错案例](docs/AI_DEV_LOG.md)，保留失败、发现方式、修订范围及回归证据。
- 演示：[4分50秒分段脚本](docs/DEMO_SCRIPT.md)。**尚无录制成片和上传链接**，脚本不代替视频交付。
- PC：按上文一条`start-desktop.sh`命令运行；CLI指定目录已测。用户确认现场另换机器，其运行、原生选目录弹窗和真实教师专业审核仍未验，不用合成审核点击代替。

已知限制：仅《循环结构》与已批准固定任务，不能据新措辞声称支持任意学科/任意题目；用例通过不等于教学正确。单worker与Docker共享内核、Manager高权限、PC依赖SSH/模型网络、短期IP证书续期、未实现会话自动到期清理，均是演示边界。依赖没有锁定完整间接版本；已有Git历史保留，最终提交与外部访问权限由用户处理。
