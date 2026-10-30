import type { VerificationReport } from './api'

const descriptions: Record<string, { title: string; explanation: string; next: string; tone: string }> = {
  PASS: { title: '当前固定用例通过', explanation: '当前版本已通过配套固定用例；这不能代替教学适配与文字内容审核。', next: '请继续逐项审核教学内容，再确认文件差异。', tone: 'success' },
  NOT_TESTED: { title: '当前代码尚未验证', explanation: '当前版本还没有有效的测试结果，暂不能接受或交付这份代码。', next: '请运行当前教案的全部代码测试，再根据结果审核。', tone: 'pending' },
  STALE: { title: '验证结果已过期', explanation: '现有报告不再满足当前版本的有效性要求，不能作为通过证据。', next: '请重新验证，取得当前版本的结果。', tone: 'pending' },
  OUTPUT_MISMATCH: { title: '实际输出与预期不一致', explanation: '至少一个用例的输出未通过逐字比较，空格和换行也参与比较。', next: '对照下方输入与输出，检查循环边界、输出顺序以及多余或缺少的文字、空格和换行。', tone: 'failure' },
  SYNTAX_ERROR: { title: 'Python 代码存在语法错误', explanation: '执行器未能正常解析代码。', next: '检查冒号、括号和缩进，结合错误详情修正后重新验证。', tone: 'failure' },
  ASSERTION_ERROR: { title: '代码中的断言未通过', explanation: '运行时有断言条件不成立。', next: '结合输入和错误详情检查条件及计算过程，修正后重测。', tone: 'failure' },
  RUNTIME_ERROR: { title: '代码执行时发生异常', explanation: '代码未能正常完成执行。', next: '查看错误详情，检查输入处理、变量、索引及计算过程后重测。', tone: 'failure' },
  TIMEOUT: { title: '代码运行或验证超时', explanation: '运行或整套验证超过时间限制；仅凭超时不能确定一定存在死循环。', next: '优先检查循环退出条件、变量更新与计算量，结合错误详情确认后重测。', tone: 'failure' },
  RESOURCE_LIMIT: { title: '代码使用的资源超过限制', explanation: '执行器因资源限制终止了运行。', next: '检查循环规模和内存使用，减少不必要的计算后重测。', tone: 'failure' },
  OUTPUT_LIMIT: { title: '输出内容超过限制', explanation: '程序输出过多，执行器未能保留完整结果。', next: '检查是否在循环中持续打印，或输出了不需要的调试信息。', tone: 'failure' },
  RUNNER_ERROR: { title: '执行器未能完成验证', explanation: '当前报告包含执行器或执行证据异常，不能据此判断代码正确性。', next: '查看错误详情，确认执行器与网络状态后重试。', tone: 'pending' },
  INTERRUPTED: { title: '验证被中断', explanation: '这次运行没有形成完整的通过证据。', next: '请重新运行代码测试。', tone: 'pending' },
}

export function describeVerification(status: string, report?: VerificationReport, changed = false) {
  const effective = status === 'PASS' && report?.effective_status !== 'PASS' ? 'STALE' : status
  const description = descriptions[effective] || { title: '尚不能确认验证结果', explanation: '当前状态不能作为代码通过的证据。', next: '请检查原始报告或重新验证。', tone: 'pending' }
  const current = report?.effective_status === effective && effective !== 'STALE' ? report : undefined
  const failure = current?.cases.find(item => item.status !== 'PASS')
  return {
    ...description, status: effective, failure,
    ...(effective === 'NOT_TESTED' && changed ? { title: '代码已修改，等待验证', explanation: '当前代码已修改，尚无本版本的验证结果，不能沿用旧版本结论；通过验证前不能接受或交付。' } : {}),
  }
}

export function visibleTestText(text: string, empty = '（空）') {
  return text === '' ? empty : text.replace(/ /g, '·').replace(/\t/g, '⇥').replace(/\r/g, '␍').replace(/\n/g, '↵\n')
}

type Props = { status: string; report?: VerificationReport; changed?: boolean; pending?: boolean; onVerify?: () => void }

export default function VerificationDiagnostic({ status, report, changed, pending, onVerify }: Props) {
  const diagnosis = describeVerification(status, report, changed)
  return <section className={`verification-diagnostic ${diagnosis.tone}`} aria-label="代码验证诊断">
    <strong>{diagnosis.title}</strong><p>{diagnosis.explanation}</p>
    {diagnosis.failure && <p>首个未通过用例：{diagnosis.failure.id}。具体输入与输出见下方报告。</p>}
    <p>下一步：{diagnosis.next}</p>
    {onVerify && ['NOT_TESTED', 'STALE', 'INTERRUPTED', 'RUNNER_ERROR'].includes(diagnosis.status) && <button type="button" disabled={pending} onClick={onVerify}>验证当前教案代码</button>}
    <details><summary>查看技术状态</summary><code>{diagnosis.status}</code></details>
  </section>
}

export function Report({ report }: { report: VerificationReport }) {
  const diagnosis = describeVerification(report.effective_status, report)
  const passed = report.cases.filter(item => item.status === 'PASS').length
  return <details className="report"><summary>{diagnosis.title} · {passed} / {report.cases.length} 条用例通过 <code>{report.effective_status}</code></summary>
    <p>{diagnosis.explanation}</p><p>建议：{diagnosis.next}</p>
    {report.effective_status === 'STALE' && <p className="failure">以下为历史运行记录，不能作为当前代码通过的证据。</p>}
    <p className="muted">空白标记：· 为空格，↵ 为换行，⇥ 为制表符，␍ 为回车。</p>
    {report.cases.map((item, index) => <section key={item.id} className="test-case" aria-label={`用例 ${item.id}`}>
      <strong>用例 {index + 1}：{item.status === 'PASS' ? '该次运行通过' : descriptions[item.status]?.title || '未通过'} <code>{item.status}</code></strong>
      <small> · {Math.round(item.duration_ms)} ms · 退出码 {item.exit_code ?? '无'}</small>
      <dl className="case-values">{[['测试输入', item.input], ['预期输出', item.expected], ['实际输出', item.actual]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd><pre tabIndex={0} aria-label={`${label}，可滚动`}>{visibleTestText(value)}</pre></dd></div>)}</dl>
      {(item.error || item.stderr) && <details className="case-error"><summary>查看错误详情</summary>{item.error && <p>{item.error}</p>}{item.stderr && <pre>{item.stderr}</pre>}</details>}
      <details><summary>查看原始输入输出</summary><pre>{JSON.stringify({ input: item.input, expected: item.expected, actual: item.actual }, null, 2)}</pre></details>
    </section>)}
    <details><summary>版本证据</summary><code>{report.code_hash}<br />{report.fingerprint}</code></details>
  </details>
}
