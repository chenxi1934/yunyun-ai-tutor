import { Check, X, Pencil } from 'lucide-react'

type Props = {
  status: string; note?: string | null; pending: boolean; canAccept: boolean; busy?: 'accept' | 'reject'; error?: string
  editing?: boolean; onReview: (decision: 'accept' | 'reject') => void; onEdit: () => void
}

export default function ReviewActions({ status, note, pending, canAccept, busy, error, editing, onReview, onEdit }: Props) {
  const showNote = note && !['教师确认本项可用于课堂', '教师拒绝，需继续修订'].includes(note)
  return <>
    <div className="review-toolbar" role="group" aria-label="本项审阅状态与操作">
      <span className={`status ${status === 'ACCEPTED' ? 'success' : status === 'REJECTED' ? 'failure' : ''}`} role="status">{({ ACCEPTED: '已接受', REJECTED: '已拒绝，待修改', PENDING: '待审核' } as Record<string, string>)[status] || '待审核'}</span>
      {!editing && <>
        <button type="button" disabled={pending || !canAccept || status === 'ACCEPTED'} onClick={() => onReview('accept')}><Check size={14} aria-hidden="true" />{busy === 'accept' ? '正在接受…' : status === 'REJECTED' ? '改为接受' : '接受'}</button>
        <button type="button" disabled={pending || status === 'REJECTED'} onClick={() => onReview('reject')}><X size={14} aria-hidden="true" />{busy === 'reject' ? '正在拒绝…' : '拒绝'}</button>
        <button type="button" disabled={pending} onClick={onEdit}><Pencil size={14} aria-hidden="true" />继续修改</button>
      </>}
    </div>
    {(status === 'REJECTED' || (status === 'ACCEPTED' && showNote)) && <div className={`review-feedback ${status === 'REJECTED' ? 'rejected' : 'accepted'}`}>
      {status === 'REJECTED' && <p>本项已拒绝，内容保留待修订，当前不能交付。</p>}
      {showNote && <p>审核说明：{note}</p>}
    </div>}
    {error && <p className="failure" role="alert">{error}</p>}
  </>
}
