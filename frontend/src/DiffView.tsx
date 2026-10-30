type Highlight = { before: string; changed: string; after: string }
type DiffLine = { kind: 'context' | 'add' | 'remove' | 'hunk' | 'note'; text: string; oldLine?: number; newLine?: number; highlight?: Highlight }

export function changedText(before: string, after: string): [Highlight, Highlight] {
  const left = Array.from(before), right = Array.from(after)
  let start = 0, end = 0
  while (start < Math.min(left.length, right.length) && left[start] === right[start]) start++
  while (end < Math.min(left.length, right.length) - start && left[left.length - end - 1] === right[right.length - end - 1]) end++
  const parts = (value: string[]) => ({ before: value.slice(0, start).join(''), changed: value.slice(start, value.length - end).join(''), after: end ? value.slice(-end).join('') : '' })
  return [parts(left), parts(right)]
}

export function parseUnifiedDiff(diff: string) {
  const rows: DiffLine[] = []
  const invalid = () => ({ supported: false, rows: [] as DiffLine[], added: 0, removed: 0 })
  if (!diff) return { supported: true, rows, added: 0, removed: 0 }
  const lines = diff.split('\n')
  if (lines.at(-1) === '') lines.pop()
  let oldLine = 0, newLine = 0, oldRemaining = 0, newRemaining = 0, seenHunk = false
  for (const raw of lines) {
    const line = raw.endsWith('\r') ? raw.slice(0, -1) : raw
    const hunk = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:.*)?$/.exec(line)
    if (hunk) {
      if (oldRemaining || newRemaining) return invalid()
      oldLine = Number(hunk[1]); newLine = Number(hunk[3])
      oldRemaining = hunk[2] === undefined ? 1 : Number(hunk[2])
      newRemaining = hunk[4] === undefined ? 1 : Number(hunk[4])
      rows.push({ kind: 'hunk', text: `变更位置：原第 ${oldLine} 行 → 新第 ${newLine} 行` })
      seenHunk = true
    } else if (line === '\\ No newline at end of file') {
      if (!seenHunk) return invalid()
      rows.push({ kind: 'note', text: '该行末尾没有换行符' })
    } else if (!oldRemaining && !newRemaining) {
      if (seenHunk || !/^(--- |\+\+\+ )/.test(line)) return invalid()
    } else if (line.startsWith(' ') && oldRemaining > 0 && newRemaining > 0) {
      rows.push({ kind: 'context', text: line.slice(1), oldLine: oldLine++, newLine: newLine++ })
      oldRemaining--; newRemaining--
    } else if (line.startsWith('-') && oldRemaining > 0) {
      rows.push({ kind: 'remove', text: line.slice(1), oldLine: oldLine++ })
      oldRemaining--
    } else if (line.startsWith('+') && newRemaining > 0) {
      rows.push({ kind: 'add', text: line.slice(1), newLine: newLine++ })
      newRemaining--
    } else return invalid()
  }
  if (!seenHunk || oldRemaining || newRemaining) return invalid()
  for (let index = 0; index < rows.length; index++) {
    if (rows[index].kind !== 'remove') continue
    const removed: DiffLine[] = [], added: DiffLine[] = []
    while (rows[index]?.kind === 'remove') removed.push(rows[index++])
    while (rows[index]?.kind === 'add') added.push(rows[index++])
    for (let pair = 0; pair < Math.min(removed.length, added.length); pair++) {
      const [left, right] = changedText(removed[pair].text, added[pair].text)
      removed[pair].highlight = left; added[pair].highlight = right
    }
    index--
  }
  return { supported: true, rows, added: rows.filter(row => row.kind === 'add').length, removed: rows.filter(row => row.kind === 'remove').length }
}

type Props = { diff: string; fromLabel?: string; toLabel?: string; filePath?: string; emptyMessage?: string }

export default function DiffView({ diff, fromLabel = '原内容', toLabel = '修改后内容', filePath, emptyMessage = '内容无差异' }: Props) {
  const parsed = parseUnifiedDiff(diff)
  if (!diff) return <p className="muted">{emptyMessage}</p>
  if (!parsed.supported) return <div className="diff-view"><p className="muted">此差异无法按行解析，以下保留原始内容供核对。</p><pre className="diff" tabIndex={0} aria-label="原始差异，可滚动">{diff}</pre></div>
  return <div className="diff-view">
    <div className="diff-heading"><strong title={filePath}>{filePath?.split('/').at(-1) || '内容变更'}</strong><span><span className="success">新增 {parsed.added} 行</span> · <span className="failure">删除 {parsed.removed} 行</span></span></div>
    <p className="diff-versions">{fromLabel} → {toLabel}；红色 − 为删除，绿色 + 为新增，深色标记为改动字符。</p>
    <div className="diff-scroll" role="region" aria-label="差异内容，可横向滚动" tabIndex={0}>
      <table className="diff-table"><thead><tr><th scope="col">原行</th><th scope="col">新行</th><th scope="col">变更</th><th scope="col">内容</th></tr></thead><tbody>{parsed.rows.map((row, index) => {
        if (row.kind === 'hunk' || row.kind === 'note') return <tr className={`diff-${row.kind}`} key={index}><td colSpan={4}>{row.text}</td></tr>
        const marker = row.kind === 'add' ? '+' : row.kind === 'remove' ? '−' : ''
        return <tr className={`diff-${row.kind}`} key={index}>
          <td className="diff-line-number">{row.oldLine}</td><td className="diff-line-number">{row.newLine}</td><td className="diff-marker" aria-label={row.kind === 'add' ? '新增' : row.kind === 'remove' ? '删除' : '未变'}>{marker}</td>
          <td className="diff-code"><code>{row.highlight ? <>{row.highlight.before}{row.highlight.changed && <mark title={`${row.kind === 'add' ? '新增' : '删除'}${/^\s+$/.test(row.highlight.changed) ? '的空白字符' : '字符'}`}>{row.highlight.changed}</mark>}{row.highlight.after}</> : row.text}</code></td>
        </tr>
      })}</tbody></table>
    </div>
    <details className="diff-raw"><summary>查看原始差异</summary><pre className="diff" tabIndex={0} aria-label="原始差异，可滚动">{diff}</pre></details>
  </div>
}
