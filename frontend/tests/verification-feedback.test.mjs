import assert from 'node:assert/strict'
import { after, test } from 'node:test'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { transformWithEsbuild } from 'vite'

const sourceUrl = new URL('../src/VerificationFeedback.tsx', import.meta.url)
const cacheDir = new URL('../node_modules/.tmp/', import.meta.url)
await mkdir(cacheDir, { recursive: true })
const temporary = await mkdtemp(fileURLToPath(new URL('verification-feedback-', cacheDir)))
after(() => rm(temporary, { recursive: true, force: true }))
const transformed = await transformWithEsbuild(await readFile(sourceUrl, 'utf8'), fileURLToPath(sourceUrl), {
  loader: 'tsx', jsx: 'automatic', format: 'esm',
})
const modulePath = `${temporary}/VerificationFeedback.mjs`
await writeFile(modulePath, transformed.code)
const { default: VerificationFeedback, summarizeVerification } = await import(pathToFileURL(modulePath).href)

function fixture() {
  const examples = [{ id: 'example', title: '循环示例' }]
  const exercises = [{ id: 'basic', title: '基础练习' }, { id: 'advanced', title: '进阶练习' }]
  const items = Object.fromEntries([...examples, ...exercises].map(item => [item.id, {
    draft_id: `draft-${item.id}`, current_pass: true, verification_status: 'PASS', review_status: 'PENDING',
  }]))
  const lesson = { lesson_id: 'lesson', revision: 3, plan: { examples, exercises }, items }
  const reports = [...examples, ...exercises].map(item => ({
    id: `report-${item.id}`, draft_id: items[item.id].draft_id, status: 'PASS', effective_status: 'PASS',
    cases: [{ id: 'zero', status: 'PASS' }, { id: 'normal', status: 'PASS' }],
  }))
  return { lesson, reports }
}
const render = (lesson, reports, props = {}) => renderToStaticMarkup(createElement(VerificationFeedback, {
  lesson, reports, onOpen: () => {}, ...props,
}))

test('汇总只统计各份当前代码的最新报告，不重复累计历史报告', () => {
  const { lesson, reports } = fixture()
  const old = { ...reports[0], id: 'old', cases: Array(20).fill({ status: 'PASS' }) }
  const unrelated = { ...old, draft_id: 'other-lesson' }
  const result = summarizeVerification(lesson, [old, unrelated, ...reports])
  assert.equal(result.passed, 3)
  assert.equal(result.total, 3)
  assert.equal(result.allPassed, true)
  assert.equal(result.caseCount, 6)
  assert.equal(result.passedCases, 6)
  assert.deepEqual(result.entries.map(item => item.tab), ['示例代码', '分层练习', '分层练习'])
})

test('全部通过时显示数量，仍提示教师审核边界', () => {
  const { lesson, reports } = fixture()
  const html = render(lesson, reports, { phase: 'complete', completedAt: Date.parse('2026-10-30T02:03:04Z') })
  assert.match(html, /验证完成，全部代码通过/)
  assert.match(html, /本次检查结束于/)
  assert.match(html, /仍有效的已有报告/)
  assert.match(html, /3 \/ 3 份代码通过/)
  assert.match(html, /6 \/ 6 条用例通过/)
  assert.match(html, /仍需逐项审核教学内容/)
  assert.match(html, /aria-label="基础练习：查看测试报告"/)
})

test('请求成功但代码用例失败时显示未通过，并展开逐项结果', () => {
  const { lesson, reports } = fixture()
  lesson.items.basic.current_pass = false
  lesson.items.basic.verification_status = 'OUTPUT_MISMATCH'
  reports[1].status = reports[1].effective_status = 'OUTPUT_MISMATCH'
  reports[1].cases[1].status = 'OUTPUT_MISMATCH'
  const html = render(lesson, reports, { phase: 'complete' })
  assert.match(html, /有代码需要处理/)
  assert.match(html, /2 \/ 3 份代码通过/)
  assert.match(html, /5 \/ 6 条用例通过/)
  assert.match(html, /输出不匹配/)
  assert.match(html, /<details open="">/)
  assert.doesNotMatch(html, /全部代码通过|当前代码验证通过/)
})

test('代码或规格改变后，旧PASS不能算作当前通过证据', () => {
  const { lesson, reports } = fixture()
  lesson.items.example.current_pass = false
  const result = summarizeVerification(lesson, reports)
  assert.equal(result.entries[0].status, 'STALE')
  assert.equal(result.entries[0].report, undefined)
  assert.equal(result.passed, 2)
  assert.equal(result.caseCount, 4)
  assert.equal(result.allPassed, false)
})

test('报告被后端标为STALE时不显示通过或累计过期用例', () => {
  const { lesson, reports } = fixture()
  reports[0].effective_status = 'STALE'
  const html = render(lesson, reports)
  assert.match(html, /结果已过期/)
  assert.match(html, /2 \/ 3 份代码通过/)
  assert.match(html, /4 \/ 4 条用例通过/)
  assert.doesNotMatch(html, /全部代码通过|当前代码验证通过/)
})

test('新代码草稿不能继承上一版草稿的通过报告', () => {
  const { lesson, reports } = fixture()
  lesson.items.example = { ...lesson.items.example, draft_id: 'new-draft', current_pass: false, verification_status: 'NOT_TESTED' }
  const result = summarizeVerification(lesson, reports)
  assert.equal(result.entries[0].status, 'NOT_TESTED')
  assert.equal(result.entries[0].report, undefined)
  assert.equal(result.passed, 2)
  assert.match(render(lesson, reports), /aria-label="循环示例：查看代码"/)
})

test('没有报告或没有代码时不能显示全部通过', () => {
  const { lesson } = fixture()
  assert.equal(summarizeVerification(lesson, []).passed, 0)
  lesson.plan.examples = []
  lesson.plan.exercises = []
  assert.equal(summarizeVerification(lesson, []).allPassed, false)
  assert.doesNotMatch(render(lesson, []), /全部代码通过|当前代码验证通过/)
})

test('测试中显示明确等待反馈，不把已有PASS作为本次完成结果', () => {
  const { lesson, reports } = fixture()
  const html = render(lesson, reports, { phase: 'running' })
  assert.match(html, /aria-busy="true"/)
  assert.match(html, /正在检查并测试代码…/)
  assert.match(html, /有效报告会复用/)
  assert.doesNotMatch(html, /全部代码通过|当前代码验证通过|3 \/ 3|<details/)
})

test('请求失败与代码失败分开显示，已有通过报告不代表本次请求成功', () => {
  const { lesson, reports } = fixture()
  const html = render(lesson, reports, { phase: 'error', error: '执行器暂时不可用。' })
  assert.match(html, /role="alert"/)
  assert.match(html, /本次验证未完成/)
  assert.match(html, /执行器暂时不可用/)
  assert.match(html, /下方为已保存的结果/)
  assert.doesNotMatch(html, /全部代码通过|当前代码验证通过/)
})

test('未测试状态不读取其他教案的通过报告', () => {
  const { lesson, reports } = fixture()
  lesson.items = {}
  const result = summarizeVerification(lesson, reports)
  assert.equal(result.passed, 0)
  assert.equal(result.caseCount, 0)
  assert.ok(result.entries.every(item => item.status === 'NOT_TESTED'))
})

test('编辑期间报告跳转不可用，避免切换分类丢失未保存修改', () => {
  const { lesson, reports } = fixture()
  const html = render(lesson, reports, { navigationBlocked: true })
  assert.match(html, /请先保存或取消当前修改/)
  assert.match(html, /验证结果对应已保存的版本/)
  assert.equal((html.match(/disabled=""/g) || []).length, 3)
})
