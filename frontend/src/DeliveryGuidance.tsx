import type { Approval, Commit, Lesson } from './api'

export function deliveryState(lesson: Lesson, commits: Commit[], approvals: Approval[]) {
  const entries = Object.entries(lesson.items)
  return {
    rejected: entries.filter(([, state]) => state.review_status === 'REJECTED').map(([id]) => id),
    pending: entries.filter(([, state]) => state.review_status !== 'ACCEPTED' && state.review_status !== 'REJECTED').map(([id]) => id),
    committed: commits.some(commit => commit.status === 'COMMITTED' && commit.lesson_id === lesson.lesson_id && commit.lesson_revision === lesson.revision),
    approvalPending: approvals.some(approval => approval.status === 'PENDING' && approval.lesson_id === lesson.lesson_id && approval.lesson_revision === lesson.revision),
    recoveryRequired: commits.some(commit => ['APPLYING', 'ROLLING_BACK', 'INTERRUPTED'].includes(commit.status)),
  }
}

export default function DeliveryGuidance({ lesson, commits, approvals, busy, editing, onVerify, onReview, onOpenFiles }: {
  lesson: Lesson; commits: Commit[]; approvals: Approval[]; busy: boolean; editing: boolean
  onVerify: () => void; onReview: (id: string) => void; onOpenFiles: () => void
}) {
  const state = deliveryState(lesson, commits, approvals)
  return <aside className="delivery-guidance" aria-label="交付与下载指引">
    <div id="delivery-diff-hint">
      <strong>{lesson.delivery_ready ? '本版验证与教学审核已完成' : '审核交付文件 Diff 前，还需完成：'}</strong>
      {!lesson.delivery_ready && <ul>
        {lesson.profile_stale && <li>班情已更新，请在对话中重新备课，再审核新版本。</li>}
        {lesson.code_status !== 'PASS' && <li>代码尚未全部通过当前验证。<button type="button" className="subtle" disabled={busy} onClick={onVerify}>运行代码测试</button></li>}
        {!!state.rejected.length && <li>{state.rejected.length} 项已拒绝，请修订后重新审阅。<button type="button" className="subtle" disabled={editing || busy} onClick={() => onReview(state.rejected[0])}>定位拒绝项</button></li>}
        {!!state.pending.length && <li>{state.pending.length} 项待审核。<button type="button" className="subtle" disabled={editing || busy} onClick={() => onReview(state.pending[0])}>继续逐项审阅</button></li>}
        {!!lesson.curriculum_risks.length && <li>请处理下方课程适配提示，再重新验证与审核。</li>}
        {!lesson.profile_stale && lesson.code_status === 'PASS' && !state.rejected.length && !state.pending.length && !lesson.curriculum_risks.length && <li>后端尚未确认本版可交付，请刷新后核对状态。</li>}
      </ul>}
      {state.recoveryRequired ? <p>工作区有中断的文件操作，请先在“文件与Diff”的正式文件历史中完成对账恢复。</p> : busy && <p>当前操作进行中，请完成后继续。</p>}
    </div>
    <p id="delivery-package-hint">{busy && !state.recoveryRequired ? '当前操作进行中，请完成后再下载。' : !lesson.delivery_ready ? '下载教案包：先完成以上步骤，再审核文件 Diff 并确认写入。' : state.recoveryRequired ? '下载教案包：先完成文件对账恢复。' : state.committed ? '本版已正式交付，可以下载教案包；下载时会再次核对文件。' : state.approvalPending ? '下载教案包：文件 Diff 已生成，请逐份查看后“确认接受并写入”。' : '下载教案包：先点击“审核交付文件 Diff”，查看差异并确认写入。本版尚未正式交付。'}</p>
    {state.approvalPending && (editing ? <p>请先保存或取消当前编辑，再查看待确认的文件 Diff。</p> : <a href="#pending-file-approvals" onClick={onOpenFiles}>查看待确认的文件 Diff</a>)}
    {state.recoveryRequired && <button type="button" className="subtle" disabled={editing} onClick={onOpenFiles}>打开文件与Diff</button>}
  </aside>
}
