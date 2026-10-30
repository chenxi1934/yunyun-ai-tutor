import assert from 'node:assert/strict'
import { after, test } from 'node:test'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { transformWithEsbuild } from 'vite'

const sourceUrl = new URL('../src/ChatMessage.tsx', import.meta.url)
const cacheDir = new URL('../node_modules/.tmp/', import.meta.url)
await mkdir(cacheDir, { recursive: true })
const temporary = await mkdtemp(fileURLToPath(new URL('chat-message-', cacheDir)))
after(() => rm(temporary, { recursive: true, force: true }))
const transformed = await transformWithEsbuild(await readFile(sourceUrl, 'utf8'), fileURLToPath(sourceUrl), {
  loader: 'tsx', jsx: 'automatic', format: 'esm',
})
const modulePath = `${temporary}/ChatMessage.mjs`
await writeFile(modulePath, transformed.code)
const { default: ChatMessage } = await import(pathToFileURL(modulePath).href)
const render = (content, props = {}) => renderToStaticMarkup(createElement(ChatMessage, { role: 'assistant', content, ...props }))

test('AI回复的标题、强调和行内代码渲染为语义元素', () => {
  const html = render('## 备课建议\n\n先解释 **循环条件** 和 *边界*，再运行 `range(3)`。')
  assert.match(html, /<h3>备课建议<\/h3>/)
  assert.match(html, /<strong>循环条件<\/strong>/)
  assert.match(html, /<em>边界<\/em>/)
  assert.match(html, /<code>range\(3\)<\/code>/)
})

test('有序、无序和嵌套列表保留层级', () => {
  const html = render('1. 导入\n2. 练习\n   - 基础\n   - 进阶')
  assert.match(html, /<ol>/)
  assert.match(html, /<ul>/)
  assert.match(html, /<li>基础<\/li>/)
  assert.match(html, /<li>进阶<\/li>/)
})

test('GFM表格与任务列表可读且保留语义', () => {
  const html = render('| 环节 | 分钟 |\n| --- | ---: |\n| 导入 | 5 |\n\n- [x] ~~旧稿~~\n- [ ] 教师审核')
  assert.match(html, /<table>/)
  assert.match(html, /<th>环节<\/th>/)
  assert.match(html, /<td>导入<\/td>/)
  assert.match(html, /role="region"/)
  assert.match(html, /aria-label="表格，可横向滚动"/)
  assert.match(html, /<input[^>]*type="checkbox"[^>]*disabled=""/)
  assert.match(html, /<del>旧稿<\/del>/)
})

test('代码块保留Python缩进与换行，HTML代码只显示为文本', () => {
  const html = render('```python\nfor i in range(3):\n    print("<script>")\n```')
  assert.match(html, /<pre[^>]*tabindex="0"[^>]*aria-label="代码块"/)
  assert.match(html, /<code class="language-python">for i in range\(3\):\n {4}print\(&quot;&lt;script&gt;&quot;\)\n<\/code>/)
  assert.doesNotMatch(html, /<script>/)
})

test('引用、分隔线及硬换行正常渲染', () => {
  const html = render('> 请教师审核\n\n---\n\n第一行  \n第二行')
  assert.match(html, /<blockquote>/)
  assert.match(html, /<hr\/>/)
  assert.match(html, /第一行<br\/>\n第二行/)
})

test('正常链接可打开，危险协议不生成可点击链接', () => {
  const html = render('[文档](https://example.com/lesson) [危险](javascript:alert%281%29) [数据](data:text/html,payload)')
  assert.match(html, /href="https:\/\/example.com\/lesson"/)
  assert.match(html, /target="_blank"/)
  assert.match(html, /rel="noopener noreferrer"/)
  assert.doesNotMatch(html, /href="(?:\s*(?:javascript|data|vbscript):[^"]*|)"/i)
  assert.match(html, /危险/)
  assert.match(html, /数据/)
})

test('模型输出的原始HTML只显示为文本', () => {
  const html = render('<script>alert("x")</script>\n\n<img src=x onerror=alert(1)>\n\n**安全文字**')
  assert.doesNotMatch(html, /<(?:script|img)\b/i)
  assert.match(html, /&lt;script&gt;/)
  assert.match(html, /&lt;img/)
  assert.match(html, /<strong>安全文字<\/strong>/)
})

test('教师输入继续原样展示，不被当成Markdown或HTML', () => {
  const html = render('## 需求\n\n**原始要求**\n<script>literal</script>', { role: 'user', mock: true })
  assert.match(html, /class="message teacher"/)
  assert.match(html, /<h2>我<\/h2>/)
  assert.match(html, /## 需求\n\n\*\*原始要求\*\*/)
  assert.match(html, /&lt;script&gt;literal&lt;\/script&gt;/)
  assert.doesNotMatch(html, /<strong>|<h3>|MOCK_LLM/)
})

test('Mock标识保留，空内容不报错', () => {
  assert.match(render(null, { mock: true }), /耘耘AI助教 · MOCK_LLM/)
  assert.match(render('普通回复'), /普通回复/)
})
