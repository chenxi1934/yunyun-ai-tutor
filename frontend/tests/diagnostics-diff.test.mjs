import assert from 'node:assert/strict'
import { after, test } from 'node:test'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { transformWithEsbuild } from 'vite'

const cacheDir = new URL('../node_modules/.tmp/', import.meta.url)
await mkdir(cacheDir, { recursive: true })
const temporary = await mkdtemp(fileURLToPath(new URL('diagnostics-diff-', cacheDir)))
after(() => rm(temporary, { recursive: true, force: true }))
const modules = {}
for (const name of ['DiffView', 'VerificationDiagnostic']) {
  const sourceUrl = new URL(`../src/${name}.tsx`, import.meta.url)
  const transformed = await transformWithEsbuild(await readFile(sourceUrl, 'utf8'), fileURLToPath(sourceUrl), {
    loader: 'tsx', jsx: 'automatic', format: 'esm',
  })
  const modulePath = `${temporary}/${name}.mjs`
  await writeFile(modulePath, transformed.code)
  modules[name] = await import(pathToFileURL(modulePath).href)
}
const { default: DiffView, parseUnifiedDiff, changedText } = modules.DiffView
const { default: Diagnostic, describeVerification, visibleTestText, Report } = modules.VerificationDiagnostic
const render = (Component, props) => renderToStaticMarkup(createElement(Component, props))
const example = '--- lessons/id/example.py\n+++ lessons/id/example.py（草稿）\n@@ -1,3 +1,3 @@\n n=int(input())\n-for i in range(1,n+1):\n+for i in range(1, n+1):\n     print(i)\n'
function report(status = 'OUTPUT_MISMATCH') {
  const actual = status === 'PASS' ? '1\n' : '2 \n'
  return { id: 'report', draft_id: 'draft', status, effective_status: status, code_hash: 'hash', fingerprint: 'fingerprint',
    cases: [{ id: 'zero', input: '0\n', expected: '', actual: '', status: 'PASS', duration_ms: 8, exit_code: 0, error: null, stderr: '', stdout: '' },
      { id: 'one', input: '1\n', expected: '1\n', actual, status, duration_ms: 12, exit_code: 0, error: status === 'PASS' ? null : '输出不匹配', stderr: '', stdout: actual }] }
}

test('截图中的空格变更有正确行号、增删数量和字符高亮', () => {
  const parsed = parseUnifiedDiff(example)
  assert.equal(parsed.supported, true)
  assert.equal(parsed.added, 1); assert.equal(parsed.removed, 1)
  assert.equal(parsed.rows.find(row => row.kind === 'remove').oldLine, 2)
  const added = parsed.rows.find(row => row.kind === 'add')
  assert.equal(added.newLine, 2); assert.equal(added.highlight.changed, ' ')
  const html = render(DiffView, { diff: example, filePath: 'lessons/id/example.py', fromLabel: '上一版代码', toLabel: '当前草稿' })
  assert.match(html, /上一版代码 → 当前草稿/)
  assert.match(html, /新增 1 行/); assert.match(html, /删除 1 行/)
  assert.match(html, /<mark title="新增的空白字符"> <\/mark>/)
  assert.match(html, /查看原始差异/)
  assert.match(html, /aria-label="差异内容，可横向滚动" tabindex="0"/)
})

test('新建文件的零行原内容不产生虚构原行号', () => {
  const parsed = parseUnifiedDiff('--- a.py\n+++ a.py\n@@ -0,0 +1,2 @@\n+print(1)\n+print(2)\n')
  assert.equal(parsed.supported, true)
  assert.equal(parsed.added, 2); assert.equal(parsed.removed, 0)
  assert.deepEqual(parsed.rows.filter(row => row.kind === 'add').map(row => [row.oldLine, row.newLine]), [[undefined, 1], [undefined, 2]])
})

test('删除文件显示删除数量，不产生新行号', () => {
  const parsed = parseUnifiedDiff('--- a.py\n+++ a.py\n@@ -1,2 +0,0 @@\n-print(1)\n-print(2)\n')
  assert.equal(parsed.supported, true)
  assert.equal(parsed.removed, 2); assert.equal(parsed.added, 0)
  assert.ok(parsed.rows.filter(row => row.kind === 'remove').every(row => row.newLine === undefined))
})

test('多段差异使用各段的起始行号', () => {
  const parsed = parseUnifiedDiff('--- a.py\n+++ a.py\n@@ -2 +2 @@\n-old\n+new\n@@ -20,1 +21,2 @@\n tail\n+added\n')
  assert.equal(parsed.supported, true)
  assert.deepEqual(parsed.rows.filter(row => row.kind === 'add').map(row => row.newLine), [2, 22])
})

test('内容中的加号或减号不会被误当作文件头', () => {
  const parsed = parseUnifiedDiff('--- a\n+++ b\n@@ -1 +1 @@\n----old\n++++new\n')
  assert.equal(parsed.supported, true)
  assert.equal(parsed.rows.find(row => row.kind === 'remove').text, '---old')
  assert.equal(parsed.rows.find(row => row.kind === 'add').text, '+++new')
})

test('空行及Python缩进保持原样', () => {
  const parsed = parseUnifiedDiff('--- a.py\n+++ a.py\n@@ -1,2 +1,2 @@\n \n-    print(1)\n+        print(1)\n')
  assert.equal(parsed.supported, true)
  assert.equal(parsed.rows.find(row => row.kind === 'context').text, '')
  assert.equal(parsed.rows.find(row => row.kind === 'add').text, '        print(1)')
})

test('字符高亮不会拆坏Unicode字符', () => {
  const [left, right] = changedText('print("😀")', 'print("😁")')
  assert.equal(left.changed, '😀'); assert.equal(right.changed, '😁')
  assert.equal(right.before + right.changed + right.after, 'print("😁")')
})

test('行数不完整的差异明确展示原文，不伪造格式化结果', () => {
  const diff = '--- a\n+++ a\n@@ -1 +1 @@\n-old+new'
  assert.equal(parseUnifiedDiff(diff).supported, false)
  const html = render(DiffView, { diff })
  assert.match(html, /无法按行解析/)
  assert.match(html, /-old\+new/)
  assert.doesNotMatch(html, /<table|新增 0 行/)
})

test('无末尾换行标记不计入代码行数', () => {
  const parsed = parseUnifiedDiff('--- a\n+++ a\n@@ -1 +1 @@\n-old\n\\ No newline at end of file\n+new\n\\ No newline at end of file')
  assert.equal(parsed.supported, true)
  assert.equal(parsed.added, 1); assert.equal(parsed.removed, 1)
  assert.equal(parsed.rows.filter(row => row.kind === 'note').length, 2)
})

test('CRLF输入与空差异均可处理', () => {
  assert.equal(parseUnifiedDiff(example.replaceAll('\n', '\r\n')).supported, true)
  assert.equal(parseUnifiedDiff('').rows.length, 0)
  assert.match(render(DiffView, { diff: '', emptyMessage: '无需回退内容' }), /无需回退内容/)
})

test('差异中的HTML和脚本只作为文本显示', () => {
  const html = render(DiffView, { diff: '--- a\n+++ a\n@@ -1 +1 @@\n-old\n+<script>alert(1)</script>\n' })
  assert.doesNotMatch(html, /<script>/)
  assert.match(html, /&lt;script&gt;/)
})

test('代码修改后未测试显示等待验证，不诊断为代码错误', () => {
  const diagnosis = describeVerification('NOT_TESTED', undefined, true)
  assert.equal(diagnosis.title, '代码已修改，等待验证')
  assert.equal(diagnosis.tone, 'pending')
  const html = render(Diagnostic, { status: 'NOT_TESTED', changed: true, pending: true, onVerify: () => {} })
  assert.match(html, /不能沿用旧版本结论/)
  assert.match(html, /disabled=""/)
  assert.match(html, /验证当前教案代码/)
  assert.doesNotMatch(html, /class="verification-diagnostic failure"/)
})

test('初次验证前不声称代码已经被修改', () => {
  assert.equal(describeVerification('NOT_TESTED').title, '当前代码尚未验证')
})

test('输出不匹配诊断依据真实失败用例，并给出检查建议', () => {
  const diagnosis = describeVerification('OUTPUT_MISMATCH', report())
  assert.equal(diagnosis.failure.id, 'one')
  assert.match(diagnosis.explanation, /逐字比较/)
  assert.match(diagnosis.next, /循环边界/)
  const html = render(Report, { report: report() })
  assert.match(html, /测试输入/); assert.match(html, /预期输出/); assert.match(html, /实际输出/)
  assert.match(html, /2·↵/)
  assert.match(html, /查看原始输入输出/)
})

test('超时诊断不会断言一定为死循环', () => {
  const diagnosis = describeVerification('TIMEOUT', report('TIMEOUT'))
  assert.match(diagnosis.explanation, /不能确定一定存在死循环/)
  assert.match(diagnosis.next, /循环退出条件/)
})

test('旧PASS报告过期时保留历史信息，不称当前通过', () => {
  const old = report('PASS'); old.effective_status = 'STALE'
  const diagnosis = describeVerification('PASS', old)
  assert.equal(diagnosis.status, 'STALE')
  assert.equal(diagnosis.failure, undefined)
  const html = render(Report, { report: old })
  assert.match(html, /以下为历史运行记录/)
  assert.doesNotMatch(html, /当前固定用例通过/)
})

test('缺失有效报告不能显示当前通过', () => {
  assert.equal(describeVerification('PASS').status, 'STALE')
})

test('有效PASS仍保留教师审核边界，不显示重测按钮', () => {
  const html = render(Diagnostic, { status: 'PASS', report: report('PASS'), onVerify: () => {} })
  assert.match(html, /当前固定用例通过/)
  assert.match(html, /不能代替教学适配与文字内容审核/)
  assert.doesNotMatch(html, /<button/)
})

test('执行器异常与中断不会被诊断为候选代码错误', () => {
  for (const status of ['RUNNER_ERROR', 'INTERRUPTED', 'STALE', 'NOT_TESTED', 'UNRECOGNIZED']) {
    assert.equal(describeVerification(status).tone, 'pending')
  }
  for (const status of ['SYNTAX_ERROR', 'ASSERTION_ERROR', 'RUNTIME_ERROR', 'RESOURCE_LIMIT', 'OUTPUT_LIMIT']) {
    assert.equal(describeVerification(status).tone, 'failure')
  }
})

test('输入输出区分空文本、空格、制表符及换行，原始数据不变', () => {
  assert.equal(visibleTestText(''), '（空）')
  assert.equal(visibleTestText(' \t\r\n'), '·⇥␍↵\n')
  const value = report(), before = structuredClone(value)
  render(Report, { report: value }); describeVerification(value.effective_status, value)
  assert.deepEqual(value, before)
})

test('报告中的HTML错误输出不能执行', () => {
  const value = report('RUNTIME_ERROR')
  value.cases[1].stderr = '<img src=x onerror=alert(1)>'
  const html = render(Report, { report: value })
  assert.doesNotMatch(html, /<img/)
  assert.match(html, /&lt;img/)
})
