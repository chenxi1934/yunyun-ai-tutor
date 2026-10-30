import { AlertCircle, CheckCircle2, LoaderCircle } from 'lucide-react'
import type { Lesson, VerificationReport } from './api'

export type VerificationPhase = 'running' | 'complete' | 'error'

const statusLabels: Record<string, string> = {
  PASS: '通过', NOT_TESTED: '未测试', STALE: '结果已过期', SYNTAX_ERROR: '语法错误',
  ASSERTION_ERROR: '断言失败', OUTPUT_MISMATCH: '输出不匹配', RUNTIME_ERROR: '运行异常',
  TIMEOUT: '执行超时', RESOURCE_LIMIT: '资源超限', OUTPUT_LIMIT: '输出超限',
  RUNNER_ERROR: '执行器故障', INTERRUPTED: '验证中断',
}

export function summarizeVerification(lesson: Lesson, reports: VerificationReport[]) {
  const entries = [
    ...lesson.plan.examples.map(item => ({ item, tab: '示例代码' })),
    ...lesson.plan.exercises.map(item => ({ item, tab: '分层练习' })),
  ].map(({ item, tab }) => {
    const state = lesson.items[item.id]
    const latest = reports.filter(report => report.draft_id === state?.draft_id).at(-1)
    const currentPass = state?.current_pass && latest?.effective_status === 'PASS'
    const status = currentPass ? 'PASS' : state?.verification_status === 'PASS'
      ? 'STALE' : state?.verification_status || 'NOT_TESTED'
    const report = latest?.effective_status === status && status !== 'STALE' ? latest : undefined
    return { id: item.id, title: item.title, tab, status, report }
  })
  const cases = entries.flatMap(entry => entry.report?.cases || [])
  const passed = entries.filter(entry => entry.status === 'PASS').length
  return {
    entries, passed, total: entries.length, allPassed: entries.length > 0 && passed === entries.length,
    caseCount: cases.length, passedCases: cases.filter(item => item.status === 'PASS').length,
  }
}

type Props = {
  lesson: Lesson; reports: VerificationReport[]; phase?: VerificationPhase; error?: string; completedAt?: number
  navigationBlocked?: boolean
  onOpen: (tab: string, itemId: string) => void
}

export default function VerificationFeedback({ lesson, reports, phase, error, completedAt, navigationBlocked, onOpen }: Props) {
  const result = summarizeVerification(lesson, reports)
  const running = phase === 'running'
  const failed = result.entries.some(entry => !['PASS', 'NOT_TESTED', 'STALE'].includes(entry.status))
  const tone = running ? 'running' : phase === 'error' || failed ? 'failure' : result.allPassed ? 'success' : 'pending'
  const title = running ? '正在检查并测试代码…' : phase === 'error' ? '本次验证未完成'
    : result.allPassed ? phase === 'complete' ? '验证完成，全部代码通过' : '当前代码验证通过'
      : failed ? phase === 'complete' ? '验证完成，有代码需要处理' : '有代码需要处理' : '代码尚未全部通过验证'
  const Icon = running ? LoaderCircle : result.allPassed && phase !== 'error' ? CheckCircle2 : AlertCircle
  return <section className={`verification-feedback ${tone}`} aria-label="代码验证反馈" aria-busy={running}>
    <div role={phase === 'error' ? 'alert' : 'status'} aria-live={phase === 'error' ? 'assertive' : 'polite'} aria-atomic="true">
      <p className="verification-heading"><Icon className={running ? 'verification-spinner' : undefined} size={17} aria-hidden="true" />{title}</p>
      {running ? <p>正在检查 {result.total} 份代码，有效报告会复用，其余代码重新测试。请稍候。</p> : <>
        {phase === 'error' && <p>{error || '验证请求未完成，请查看页面错误提示并重试。'}下方为已保存的结果。</p>}
        <p>{result.passed} / {result.total} 份代码通过{result.caseCount > 0 ? ` · 当前有效报告中 ${result.passedCases} / ${result.caseCount} 条用例通过` : ''}</p>
        {phase === 'complete' && completedAt !== undefined && <p className="verification-next">本次检查结束于 <time dateTime={new Date(completedAt).toISOString()}>{new Date(completedAt).toLocaleTimeString('zh-CN')}</time>；通过结果包含仍有效的已有报告。</p>}
        <p className="verification-next">{result.allPassed ? '固定用例通过后，仍需逐项审核教学内容，再确认文件 Diff 交付。' : '请查看未通过、未测试或已过期的代码，处理后重新验证。'}</p>
      </>}
    </div>
    {!running && <details key={`${lesson.lesson_id}:${lesson.revision}:${phase || 'saved'}`} open={phase === 'error' || (phase === 'complete' && !result.allPassed)}>
      <summary>查看 {result.total} 份代码的结果</summary>
      {navigationBlocked && <p>请先保存或取消当前修改，再查看代码或报告。验证结果对应已保存的版本。</p>}
      <ul className="verification-results">{result.entries.map(entry => <li key={entry.id}>
        <div><strong>{entry.title}</strong><span className={entry.status === 'PASS' ? 'success' : 'failure'}>{statusLabels[entry.status] || '验证未通过'}</span></div>
        <button type="button" className="subtle" disabled={navigationBlocked} aria-label={`${entry.title}：${entry.report ? '查看测试报告' : '查看代码'}`} onClick={() => onOpen(entry.tab, entry.id)}>{entry.report ? '查看报告' : '查看代码'}</button>
      </li>)}</ul>
    </details>}
  </section>
}
