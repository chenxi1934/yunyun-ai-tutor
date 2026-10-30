import assert from 'node:assert/strict'
import { after, test } from 'node:test'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createElement as element } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { transformWithEsbuild } from 'vite'
import { build } from 'esbuild'

const cache = new URL('../node_modules/.tmp/', import.meta.url)
await mkdir(cache, { recursive: true })
const temporary = await mkdtemp(fileURLToPath(new URL('lesson-workflow-', cache)))
const previousLocation = globalThis.location
globalThis.location = { hash: '', pathname: '/', search: '' }
after(async () => {
  await rm(temporary, { recursive: true, force: true })
  if (previousLocation === undefined) delete globalThis.location
  else globalThis.location = previousLocation
})

async function load(name, bundle = false, extension = 'tsx') {
  const source = new URL(`../src/${name}.${extension}`, import.meta.url)
  const transformed = bundle ? await build({ entryPoints: [fileURLToPath(source)], bundle: true,
    write: false, format: 'esm', platform: 'node', packages: 'external', jsx: 'automatic' })
    : await transformWithEsbuild(await readFile(source, 'utf8'), fileURLToPath(source), {
      loader: 'tsx', jsx: 'automatic', format: 'esm',
    })
  const path = `${temporary}/${name}.mjs`
  await writeFile(path, bundle ? transformed.outputFiles[0].text : transformed.code)
  return import(pathToFileURL(path).href)
}
const { lessonSections, reviewCounts, teachingTitle, sourceLabel, MisconceptionReferences } = await load('LessonStructure')
const { default: ReviewActions } = await load('ReviewActions')
const { default: DeliveryGuidance, deliveryState } = await load('DeliveryGuidance')
const { default: WorkspaceFiles } = await load('WorkspaceFiles')
const { default: EducationWorkspace } = await load('EducationWorkspace', true)
const { default: App } = await load('App', true)
const { default: FileDraftFeedback, readDraftConflict, originalPreparationRequest } = await load('FileDraftFeedback', true)
const { default: ExecutionLog } = await load('ExecutionLog')
const { api, ApiError } = await load('api', true, 'ts')
const noop = () => {}
const render = (Component, props) => renderToStaticMarkup(element(Component, props))

function fixture() {
  const plan = {
    stage: '初中', topic: '循环结构', duration_minutes: 45, prerequisites: ['条件语句'],
    overview: ['content', 'learners', 'focus'].map(kind => ({ id: `analysis-${kind}`, kind, title: `${kind}分析`, content: '合成章节内容' })),
    goals: [{ id: 'goal', title: '循环目标', criterion: '能定位变量更新' }],
    segments: [{ id: 'segment', title: '追踪循环', minutes: 45, activity: '合成教学活动', teacher_actions: '教师示范追踪', student_actions: '学生独立填写', assessment: '检查边界情况' }],
    examples: [{ id: 'example', title: '演示：count', task_id: 'count', code: 'print(1)' }],
    exercises: [{ id: 'exercise-basic', title: '基础：even_sum', task_id: 'even_sum', level: '基础', prompt: '合成练习' }],
    misconceptions: [{ id: 'risk', title: '更新风险', basis: 'observed', evidence_ids: ['fact-infinite_loop'], exercise_ids: ['exercise-basic'], trigger: '循环未退出', cause: '遗漏更新，待核实', teaching_intervention: '补充追踪表' }],
  }
  const items = Object.fromEntries(Object.values(plan).filter(Array.isArray).flat().filter(item => item.id).map(item => [item.id, { review_status: 'PENDING' }]))
  const lesson = { lesson_id: 'lesson', revision: 2, code_status: 'NOT_DELIVERABLE', delivery_ready: false,
    profile_stale: false, curriculum_risks: [], plan, items, strategies: [],
    profile: { facts: [{ id: 'fact-infinite_loop', observation: 'while死循环：3人', source_ref: 'csv:row=4' }], unknowns: ['观察交集未知'] },
  }
  return { session: { id: 'session', revision: 4 }, lessons: [lesson], drafts: [], verification_reports: [], commits: [], approvals: [] }
}

test('教案按五节组织，审核状态不会改变章节归属或项目顺序', () => {
  const lesson = fixture().lessons[0]
  lesson.items['analysis-focus'].review_status = 'REJECTED'
  const before = structuredClone(lesson)
  const sections = lessonSections(lesson.plan, '教案')
  assert.deepEqual(sections.map(s => s.title), ['一、教学内容分析', '二、学情分析', '三、教学目标', '四、教学重点、难点与解决策略', '五、教学过程'])
  assert.deepEqual(sections.map(s => s.items[0].id), ['analysis-content', 'analysis-learners', 'goal', 'analysis-focus', 'segment'])
  assert.deepEqual(lesson, before)
})

test('旧教案没有分析字段时保留空章节，不编造历史内容', () => {
  const lesson = fixture().lessons[0]
  delete lesson.plan.overview
  const sections = lessonSections(lesson.plan, '教案')
  assert.equal(sections[0].items.length, 0)
  assert.equal(sections[2].items[0].id, 'goal')
  assert.equal(sections[4].items[0].id, 'segment')
})

test('审核统计区分拒绝和接受，缺失审核状态仍是待审核', () => {
  const items = [{ id: 'a' }, { id: 'b' }, { id: 'c' }, { id: 'd' }]
  assert.deepEqual(reviewCounts(items, { a: { review_status: 'ACCEPTED' }, b: { review_status: 'REJECTED' }, c: { review_status: 'PENDING' } }), { accepted: 1, rejected: 1, pending: 2 })
})

test('旧任务编码可读化，教师自定义标题保留', () => {
  assert.equal(teachingTitle({ title: '基础：even_sum', task_id: 'even_sum' }), '正偶数求和')
  assert.equal(teachingTitle({ title: '教师设计的求和任务', task_id: 'even_sum' }), '教师设计的求和任务')
  assert.equal(sourceLabel('csv:row=4'), 'CSV 第 4 行')
  assert.equal(sourceLabel('json:$.facts[2]'), 'JSON 第 3 条观察')
  assert.equal(sourceLabel('text:8-16'), '文字班情')
})

test('错因主视图显示观察、来源与练习名称，编码仅在折叠追溯里', () => {
  const lesson = fixture().lessons[0]
  const html = render(MisconceptionReferences, { item: lesson.plan.misconceptions[0], lesson, blocked: false, onOpen: noop })
  const [main, trace] = html.split('<details')
  assert.match(main, /while死循环：3人（CSV 第 4 行）/)
  assert.match(main, /基础 · 正偶数求和/)
  assert.doesNotMatch(main, /fact-infinite_loop|exercise-basic|even_sum|csv:row/)
  assert.match(trace, /fact-infinite_loop/)
  assert.doesNotMatch(trace, /open=/)
})

test('证据或练习失配会明确提示，编辑期间不可跳转丢失草稿', () => {
  const lesson = fixture().lessons[0]
  const item = { ...lesson.plan.misconceptions[0], evidence_ids: ['missing'], exercise_ids: ['exercise-basic', 'missing'] }
  const html = render(MisconceptionReferences, { item, lesson, blocked: true, onOpen: noop })
  assert.match(html, /此观察在当前班情中缺失/)
  assert.match(html, /关联练习在当前版本中缺失/)
  assert.match(html, /disabled=""/)
})

test('拒绝状态、说明与操作集中呈现，保留内容且不假装已接受', () => {
  const html = render(ReviewActions, { status: 'REJECTED', note: '请补充边界诊断', pending: false, canAccept: true, onReview: noop, onEdit: noop })
  assert.match(html, /本项审阅状态与操作/)
  assert.match(html, /已拒绝，待修改/)
  assert.match(html, /内容保留待修订，当前不能交付/)
  assert.match(html, /审核说明：请补充边界诊断/)
  assert.match(html, /改为接受/)
  assert.doesNotMatch(html, /status success/)
})

test('正在拒绝时不提前显示成功，失败提示就近可读', () => {
  const html = render(ReviewActions, { status: 'PENDING', pending: true, busy: 'reject', canAccept: false, error: '未能保存审核', onReview: noop, onEdit: noop })
  assert.match(html, /正在拒绝…/)
  assert.match(html, /role="alert">未能保存审核/)
  assert.doesNotMatch(html, /内容保留待修订|已拒绝，待修改/)
  assert.equal((html.match(/disabled=""/g) || []).length, 3)
})

test('未通过代码不能通过改为接受绕过验证，编辑中仅保留状态', () => {
  const props = { status: 'REJECTED', pending: false, canAccept: false, onReview: noop, onEdit: noop }
  assert.match(render(ReviewActions, props), /<button type="button" disabled=""[^>]*>.*?改为接受/)
  assert.doesNotMatch(render(ReviewActions, { ...props, editing: true }), /<button/)
})

test('审批说明与文件名作为文本转义，不渲染上传内容中的HTML', () => {
  const html = render(ReviewActions, { status: 'ACCEPTED', note: '<img src=x onerror=alert(1)>', pending: false, canAccept: true, onReview: noop, onEdit: noop })
  assert.match(html, /&lt;img/)
  assert.doesNotMatch(html, /<img/)
  const files = render(WorkspaceFiles, { files: [{ path: '<svg>.md' }], disabled: false, onSelect: noop })
  assert.match(files, /&lt;svg&gt;\.md/)
})

test('交付引导同时解释代码、拒绝、待审核与班情过期的具体阻塞', () => {
  const snapshot = fixture(), lesson = snapshot.lessons[0]
  lesson.items.goal.review_status = 'REJECTED'
  lesson.profile_stale = true
  const html = render(DeliveryGuidance, { lesson, commits: [], approvals: [], busy: false, editing: false, onVerify: noop, onReview: noop, onOpenFiles: noop })
  assert.match(html, /班情已更新/)
  assert.match(html, /代码尚未全部通过当前验证/)
  assert.match(html, /1 项已拒绝/)
  assert.match(html, /定位拒绝项/)
  assert.match(html, /继续逐项审阅/)
  assert.match(html, /先完成以上步骤，再审核文件 Diff 并确认写入/)
})

test('已接受但未正式写入时，明确下载前仍需确认Diff', () => {
  const lesson = fixture().lessons[0]
  lesson.delivery_ready = true
  lesson.code_status = 'PASS'
  const html = render(DeliveryGuidance, { lesson, commits: [], approvals: [], busy: false, editing: false, onVerify: noop, onReview: noop, onOpenFiles: noop })
  assert.match(html, /本版尚未正式交付/)
  assert.match(html, /查看差异并确认写入/)
  assert.doesNotMatch(html, /可以下载教案包/)
})

test('上一版本、其他教案和回退提交不能解锁当前版本下载', () => {
  const lesson = fixture().lessons[0]
  const commits = [
    { status: 'COMMITTED', lesson_id: 'lesson', lesson_revision: 1 },
    { status: 'COMMITTED', lesson_id: 'other', lesson_revision: 2 },
    { status: 'ROLLED_BACK', lesson_id: 'lesson', lesson_revision: 2 },
    { status: 'COMMITTED', lesson_id: 'lesson' },
  ]
  assert.equal(deliveryState(lesson, commits, []).committed, false)
  commits.push({ status: 'COMMITTED', lesson_id: 'lesson', lesson_revision: 2 })
  assert.equal(deliveryState(lesson, commits, []).committed, true)
})

test('当前版本待审批时提供入口，其他版本审批不冒充本版完成', () => {
  const lesson = fixture().lessons[0]
  lesson.delivery_ready = true
  const props = { lesson, commits: [], approvals: [{ status: 'PENDING', lesson_id: 'lesson', lesson_revision: 2 }], busy: false, editing: false, onVerify: noop, onReview: noop, onOpenFiles: noop }
  const html = render(DeliveryGuidance, props)
  assert.match(html, /确认接受并写入/)
  assert.match(html, /href="#pending-file-approvals"/)
  const editing = render(DeliveryGuidance, { ...props, editing: true })
  assert.match(editing, /请先保存或取消当前编辑/)
  assert.doesNotMatch(editing, /href="#pending-file-approvals"/)
  assert.equal(deliveryState(lesson, [], [{ status: 'PENDING', lesson_id: 'lesson', lesson_revision: 1 }]).approvalPending, false)
})

test('操作中与中断恢复会说明当前按钮不可用的原因', () => {
  const lesson = fixture().lessons[0]
  lesson.delivery_ready = true
  const props = { lesson, commits: [], approvals: [], busy: true, editing: false, onVerify: noop, onReview: noop, onOpenFiles: noop }
  assert.match(render(DeliveryGuidance, props), /请完成后再下载/)
  const recovery = render(DeliveryGuidance, { ...props, commits: [{ status: 'INTERRUPTED' }] })
  assert.match(recovery, /完成对账恢复/)
  assert.doesNotMatch(recovery, /可以下载教案包/)
})

test('文件列表使用原生折叠和可聚焦滚动区域，当前选中文件可辨认', () => {
  const html = render(WorkspaceFiles, { files: [{ path: 'lesson.md' }, { path: 'example.py' }], selected: 'example.py', disabled: false, onSelect: noop })
  assert.match(html, /<details class="workspace-files" open="">/)
  assert.match(html, /<summary>文件（2）/)
  assert.match(html, /class="file-list-scroll" role="region" aria-label="工作区文件列表" tabindex="0"/)
  assert.equal((html.match(/aria-current="true"/g) || []).length, 1)
})

test('空文件列表有明确提示，读取中禁止重复选择文件', () => {
  assert.match(render(WorkspaceFiles, { files: [], disabled: false, onSelect: noop }), /工作区为空/)
  assert.match(render(WorkspaceFiles, { files: [{ path: 'lesson.md' }], disabled: true, onSelect: noop }), /disabled=""/)
})

test('实际产物组件把状态与操作放在正文之前，按章节显示丰富过程', () => {
  const snapshot = fixture()
  snapshot.lessons[0].items['analysis-content'] = { review_status: 'REJECTED', review_note: '合成审核说明' }
  const html = render(EducationWorkspace, { snapshot, pending: false, act: async () => true, fail: noop, onOpenFiles: noop })
  const start = html.indexOf('id="teaching-analysis-content"')
  const article = html.slice(start, html.indexOf('</article>', start))
  const heading = article.slice(article.indexOf('<div class="item-heading">'), article.indexOf('</div></div>') + 12)
  assert.match(heading, /<h5 class="item-title">content分析<\/h5>/)
  assert.match(heading, /class="review-toolbar"/)
  assert.ok(article.indexOf('review-toolbar') < article.indexOf('合成章节内容'))
  assert.match(article, /已拒绝，待修改/)
  assert.match(article, /继续修改/)
  assert.match(html, /一、教学内容分析/)
  assert.match(html, /五、教学过程/)
  assert.match(html, /教师示范追踪/)
  assert.match(html, /学生独立填写/)
  assert.match(html, /检查边界情况/)
  assert.match(html, /已接受 0 · 已拒绝 1 · 待审核 7/)
  assert.match(html, /aria-describedby="delivery-diff-hint" disabled=""/)
  assert.match(html, /aria-describedby="delivery-package-hint" disabled=""/)
})

test('交付被课程适配提示阻塞时，正文显示项目名称与原因', () => {
  const snapshot = fixture()
  snapshot.lessons[0].curriculum_risks = [{ item_id: 'example', reason: '当前学段不包含嵌套循环，请修改。' }]
  const html = render(EducationWorkspace, { snapshot, pending: false, act: async () => true, fail: noop, onOpenFiles: noop })
  assert.match(html, /顺序计数：当前学段不包含嵌套循环，请修改。/)
  assert.doesNotMatch(html, /&quot;item_id&quot;|&quot;reason&quot;/)
})

test('教学设置去掉A/B快捷填充，保留上传、文字和模板入口', () => {
  const html = render(App, {})
  assert.doesNotMatch(html, /使用A班|使用B班/)
  assert.doesNotMatch(html, /条班情观察|class="profile-count"/)
  assert.match(html, /本会话只为一个班级备课/)
  assert.match(html, /下载 CSV 示例/)
  assert.match(html, /下载 JSON 示例/)
  assert.match(html, /上传班情/)
  assert.match(html, /汇总班情（可选）/)
})

function conflictFixture(reason = 'modified') {
  const draft = { id: 'file-draft', path: 'lesson.md', operation: 'write', content: '候选教案' }
  const details = { kind: 'FILE_DRAFT_CONFLICT', reason, draft_id: draft.id,
    current_file: { path: draft.path, content: '当前教案', hash: 'current-hash' },
    diff: '--- lesson.md\n+++ lesson.md\n@@ -1 +1 @@\n-当前教案\n+候选教案\n' }
  const error = new ApiError('文件“lesson.md”：正式文件版本不同。', reason === 'already_current' ? 'DRAFT_ALREADY_CURRENT' : 'REVISION_CONFLICT', 409, details)
  return { draft, error, conflict: readDraftConflict(error, draft) }
}
const feedbackProps = { busy: false, belongsToLesson: false, continuationBlocked: false, onRefresh: noop, onContinue: noop, onLesson: noop }

test('客户端保留后端错误编码和差异详情，不丢失文件定位', async () => {
  const oldFetch = globalThis.fetch, oldStorage = globalThis.sessionStorage
  const { draft, error } = conflictFixture()
  globalThis.sessionStorage = { getItem: () => null }
  globalThis.fetch = async () => new Response(JSON.stringify({ error: { code: error.code, message: error.message, details: error.details } }), { status: 409 })
  try {
    await assert.rejects(api('/sessions/test/publish-draft', { draft_id: draft.id }), failure => {
      assert.equal(failure.code, 'REVISION_CONFLICT')
      assert.equal(failure.status, 409)
      assert.equal(readDraftConflict(failure, draft).current_file.content, '当前教案')
      return true
    })
  } finally {
    globalThis.fetch = oldFetch
    if (oldStorage === undefined) delete globalThis.sessionStorage
    else globalThis.sessionStorage = oldStorage
  }
})

test('普通会话冲突与其他草稿错误不冒充当前文件冲突', () => {
  const { draft, error } = conflictFixture()
  assert.equal(readDraftConflict(new ApiError('会话已变化', 'REVISION_CONFLICT', 409), draft), undefined)
  assert.equal(readDraftConflict(error, { ...draft, id: 'other' }), undefined)
  assert.equal(readDraftConflict(error, { ...draft, path: 'other.md' }), undefined)
  assert.equal(readDraftConflict(new ApiError('故障', 'SERVER_ERROR', 500, error.details), draft), undefined)
})

test('文件冲突提供当前差异和生成新草稿入口，不要求重发整份需求', () => {
  const value = conflictFixture()
  const html = render(FileDraftFeedback, { ...feedbackProps, ...value, originalRequest: '合成原需求，仅回填时使用' })
  assert.match(html, /lesson\.md/)
  assert.match(html, /查看当前文件与草稿的差异/)
  assert.match(html, /基于当前文件重新生成草稿/)
  assert.match(html, /此操作仅保存草稿/)
  assert.match(html, /Python 新草稿需重新验证/)
  assert.match(html, /带入原备课需求/)
  assert.doesNotMatch(html, /合成原需求，仅回填时使用/)
})

test('文件已符合候选内容时为状态提示，不重复生成或声称新写入成功', () => {
  const value = conflictFixture('already_current')
  const html = render(FileDraftFeedback, { ...feedbackProps, ...value })
  assert.match(html, /role="status"/)
  assert.match(html, /当前文件已符合草稿目标/)
  assert.doesNotMatch(html, /基于当前文件重新生成|role="alert"|写入成功/)
})

test('教案关联代码引导回教学项目，不能通过独立文件重建绕过绑定', () => {
  const html = render(FileDraftFeedback, { ...feedbackProps, ...conflictFixture(), belongsToLesson: true })
  assert.match(html, /返回备课产物/)
  assert.match(html, /完成逐项审阅/)
  assert.doesNotMatch(html, /基于当前文件重新生成草稿/)
})

test('删除草稿保持删除意图，已有输入或编辑时不能覆盖回填', () => {
  const value = conflictFixture()
  const html = render(FileDraftFeedback, { ...feedbackProps, ...value, draft: { ...value.draft, operation: 'delete' }, originalRequest: '原需求', continuationBlocked: true })
  assert.match(html, /基于当前文件重新生成删除草稿/)
  assert.match(html, /<button type="button" disabled="">带入原备课需求/)
  assert.match(html, /未发送的内容或当前文件编辑/)
})

test('原始备课需求回填保持完整原文，不选择模型文字或截断长需求', () => {
  const original = '  全班40人，请备课。\n' + '补充教学条件。'.repeat(1200)
  assert.equal(originalPreparationRequest([{ role: 'assistant', content: '模型文字' }, { role: 'user', content: ' ' }, { role: 'user', content: original }, { role: 'user', content: '后续修改' }]), original)
  assert.equal(originalPreparationRequest([{ role: 'assistant', content: '模型文字' }]), undefined)
})

test('执行记录标题位于滚动区域外，长记录不截断且支持键盘进入', () => {
  const events = Array.from({ length: 120 }, (_, index) => ({ event_id: index + 1, type: 'tool.completed', timestamp: '2026-10-30T03:30:00Z', payload: { name: 'read_file' } }))
  const html = render(ExecutionLog, { events, labels: { 'tool.completed': '操作已完成' }, tools: { read_file: '读取文件' } })
  assert.match(html, /<details class="execution-log"><summary>查看执行记录（120）<\/summary><div class="execution-log-scroll"/)
  assert.match(html, /role="region" aria-label="执行记录列表" tabindex="0"/)
  assert.equal((html.match(/<li>/g) || []).length, 120)
  assert.match(html, /操作已完成 · 读取文件/)
  assert.doesNotMatch(html, /<details class="execution-log" open/)
})

test('执行记录保留空状态与失败追溯，错误内容安全转义', () => {
  assert.match(render(ExecutionLog, { events: [], labels: {}, tools: {} }), /暂无执行记录/)
  const html = render(ExecutionLog, { events: [{ event_id: 1, type: 'tool.failed', timestamp: '2026-10-30T03:30:00Z', payload: { result: { message: '<img src=x onerror=alert(1)>' } } }], labels: { 'tool.failed': '操作失败' }, tools: {} })
  assert.match(html, /失败详情/)
  assert.match(html, /&lt;img/)
  assert.doesNotMatch(html, /<img/)
})
