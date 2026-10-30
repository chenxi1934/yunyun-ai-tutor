import DiffView from './DiffView'
import type { Draft, Snapshot } from './api'

export type FileDraftConflict = {
  draft_id: string; reason: 'created' | 'modified' | 'deleted' | 'already_current'; message: string
  current_file: { path: string; content: string; hash: string | null }; diff: string
}

export function readDraftConflict(error: unknown, draft: Draft): FileDraftConflict | undefined {
  if (!(error instanceof Error) || !('code' in error) || !['REVISION_CONFLICT', 'DRAFT_ALREADY_CURRENT'].includes(String(error.code))
    || !('details' in error) || !error.details || typeof error.details !== 'object') return
  const details = error.details as Record<string, unknown>
  const file = details.current_file as Record<string, unknown> | undefined
  if (details.kind !== 'FILE_DRAFT_CONFLICT' || details.draft_id !== draft.id || !file || file.path !== draft.path
    || typeof file.content !== 'string' || (file.hash !== null && typeof file.hash !== 'string')
    || typeof details.diff !== 'string' || !['created', 'modified', 'deleted', 'already_current'].includes(String(details.reason))) return
  return { draft_id: draft.id, reason: details.reason as FileDraftConflict['reason'],
    message: error.message, current_file: file as FileDraftConflict['current_file'], diff: details.diff }
}

export function originalPreparationRequest(messages: Snapshot['messages']) {
  return messages.find(message => message.role === 'user' && message.content?.trim())?.content || undefined
}

export default function FileDraftFeedback({ draft, conflict, notice, busy, belongsToLesson, originalRequest, continuationBlocked, onRefresh, onContinue, onLesson }: {
  draft: Draft; conflict?: FileDraftConflict; notice?: string; busy: boolean; belongsToLesson: boolean
  originalRequest?: string; continuationBlocked: boolean; onRefresh: () => void; onContinue: () => void; onLesson: () => void
}) {
  if (!conflict && !notice) return null
  const same = conflict?.reason === 'already_current'
  return <div className={`file-draft-feedback ${conflict && !same ? 'conflict' : ''}`} role={conflict && !same ? 'alert' : 'status'}>
    {notice && <p>{notice}</p>}
    {conflict && <>
      <p><strong>{same ? '当前文件已符合草稿目标' : '文件版本需要重新核对'}</strong></p>
      <p>{conflict.message}</p>
      {!same && <>
        <details><summary>查看当前文件与草稿的差异</summary><DiffView diff={conflict.diff} filePath={draft.path} fromLabel="本次检查的正式文件" toLabel={draft.operation === 'delete' ? '删除后' : '保留的草稿候选'} /></details>
        {belongsToLesson ? <><p>此代码属于备课产物，请在教学项目中修改和验证，完成逐项审阅后通过“审核交付文件 Diff”整包交付。</p><button type="button" disabled={busy} onClick={onLesson}>返回备课产物</button></>
          : <><p>核对差异后，可保留这份候选内容，基于当前文件生成新草稿。此操作仅保存草稿，正式写入仍需再次确认；Python 新草稿需重新验证。</p><button type="button" disabled={busy} onClick={onRefresh}>{draft.operation === 'delete' ? '基于当前文件重新生成删除草稿' : '基于当前文件重新生成草稿'}</button></>}
      </>}
    </>}
    {originalRequest && <><p>如需助教继续处理，可带入原备课需求，补充本次修改要求后发送。</p><button type="button" disabled={busy || continuationBlocked} onClick={onContinue}>带入原备课需求</button>{continuationBlocked && <p className="muted">请先处理输入框中未发送的内容或当前文件编辑，再带入需求。</p>}</>}
  </div>
}
