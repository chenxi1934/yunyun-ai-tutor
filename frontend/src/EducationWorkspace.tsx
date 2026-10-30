import { useEffect, useState } from 'react'
import { Play, Download, History, Save, Undo2 } from 'lucide-react'
import { api, download, type Lesson, type Snapshot, type TeachingItem } from './api'
import VerificationFeedback, { summarizeVerification, type VerificationPhase } from './VerificationFeedback'
import VerificationDiagnostic, { Report } from './VerificationDiagnostic'
import DiffView from './DiffView'
import { lessonSections, reviewCounts, sourceLabel, teachingTitle, MisconceptionReferences } from './LessonStructure'
import ReviewActions from './ReviewActions'
import DeliveryGuidance, { deliveryState } from './DeliveryGuidance'

export { Report } from './VerificationDiagnostic'

type Props = { snapshot: Snapshot; pending: boolean; act: (path: string, body: unknown, method?: string) => Promise<boolean>; fail: (message: string) => void; onOpenFiles: () => void }
function ItemEditor({ item, save, cancel, pending }: {item: TeachingItem; save: (item: TeachingItem) => void; cancel: () => void; pending: boolean}) {
  const [value, setValue] = useState(item)
  useEffect(() => {
    if (JSON.stringify(value) === JSON.stringify(item)) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [value, item])
  const fields: [keyof TeachingItem, string][] = [['content', '章节内容'], ['criterion', '达成标准'], ['activity', '教学活动'], ['teacher_actions', '教师活动'], ['student_actions', '学生活动'], ['assessment', '达成检查与反馈'], ['explanation', '讲解与参考论证'], ['prompt', '题目'], ['scaffolding', '学习支架'], ['code', 'Python代码'], ['trigger', '触发情况'], ['cause', '原因假设'], ['teaching_intervention', '课堂干预']]
  return <form className="item-editor" onSubmit={e => {e.preventDefault(); save(value)}}><fieldset className="editor-fields" disabled={pending}>
    <label>标题<input value={value.title} required maxLength={150} onChange={e => setValue({...value, title: e.target.value})} /></label>
    {fields.filter(([key]) => item[key] !== undefined).map(([key, label]) => <label key={key}>{label}<textarea value={String(value[key] ?? '')} rows={key === 'code' ? 8 : 3} maxLength={key === 'code' ? 8000 : key === 'content' ? 2400 : 1200} onChange={e => setValue({...value, [key]: e.target.value})} /></label>)}
    {value.scoring?.map((point, index) => <div key={index} className="scoring-edit"><label>评分点<input value={point.criterion} onChange={e => setValue({...value, scoring: value.scoring!.map((p, i) => i === index ? {...p, criterion: e.target.value} : p)})}/></label><label>分值<input type="number" min={1} max={100} value={point.points} onChange={e => setValue({...value, scoring: value.scoring!.map((p, i) => i === index ? {...p, points: Number(e.target.value)} : p)})}/></label></div>)}
    <div className="actions"><button className="primary" type="submit"><Save size={14}/>保存新版本</button><button type="button" onClick={cancel}>取消</button></div>
  </fieldset></form>
}

export default function EducationWorkspace({snapshot, pending, act, fail, onOpenFiles}: Props) {
  const lesson = snapshot.lessons.at(-1)
  const [tab, setTab] = useState('教案')
  const [editing, setEditing] = useState<string>()
  const [note, setNote] = useState('')
  const [history, setHistory] = useState<Lesson[]>([])
  const [downloading, setDownloading] = useState(false)
  const [verification, setVerification] = useState<{ lessonId: string; revision: number; phase: VerificationPhase; error?: string; completedAt?: number }>()
  const [reportTarget, setReportTarget] = useState<{ id: string; report: boolean }>()
  const [reviewing, setReviewing] = useState<{ id: string; decision: 'accept' | 'reject' }>()
  const [reviewError, setReviewError] = useState<{ id: string; revision: number; message: string }>()
  const sid = snapshot.session.id
  useEffect(() => {
    if (!reportTarget) return
    const item = document.getElementById(`teaching-${reportTarget.id}`)
    if (item) {
      const reports = item.querySelectorAll<HTMLDetailsElement>('details.report')
      const report = reportTarget.report ? reports[reports.length - 1] : undefined
      if (report) report.open = true
      const target = report || item
      target.scrollIntoView({ block: 'start' })
      const focus = report?.querySelector('summary') || item
      focus.focus({ preventScroll: true })
    }
    setReportTarget(undefined)
  }, [reportTarget, tab])
  if (!lesson) return <div className="empty-state"><h3>等待备课产物</h3><p>直接描述班情与备课需求，也可先上传汇总班情。教案、代码、练习与错因预警会在这里出现。</p></div>
  const currentVerification = verification?.lessonId === lesson.lesson_id && verification.revision === lesson.revision ? verification : undefined
  const verifying = currentVerification?.phase === 'running'
  const verificationEntries = summarizeVerification(lesson, snapshot.verification_reports).entries
  const base = `/sessions/${sid}/lessons/${lesson.lesson_id}`
  const groups: Record<string, TeachingItem[]> = {'教案': [...(lesson.plan.overview || []), ...lesson.plan.goals, ...lesson.plan.segments], '示例代码': lesson.plan.examples, '分层练习': lesson.plan.exercises, '错因预警': lesson.plan.misconceptions}
  const totals = reviewCounts(Object.values(groups).flat(), lesson.items)
  const sections = lessonSections(lesson.plan, tab)
  const delivery = deliveryState(lesson, snapshot.commits, snapshot.approvals)
  function openReview(id: string) {
    if (editing) return
    const name = Object.keys(groups).find(name => groups[name].some(item => item.id === id))
    if (name) { setTab(name); setReportTarget({ id, report: false }) }
  }
  async function reviewItem(item: TeachingItem, decision: 'accept' | 'reject') {
    if (!lesson || pending || reviewing) return
    setReviewing({ id: item.id, decision }); setReviewError(undefined)
    try {
      const ok = await act(base + '/reviews', { expected_revision: lesson.revision, item_id: item.id, decision, note: note.trim() || (decision === 'accept' ? '教师确认本项可用于课堂' : '教师拒绝，需继续修订') })
      if (!ok) setReviewError({ id: item.id, revision: lesson.revision, message: '未能保存审核，请查看页面错误提示并重试。' })
    } catch (e) {
      const message = (e as Error).message
      setReviewError({ id: item.id, revision: lesson.revision, message }); fail(message)
    } finally { setReviewing(undefined) }
  }
  async function verify() {
    if (!lesson || pending || verifying) return
    const attempt = { lessonId: lesson.lesson_id, revision: lesson.revision }
    setVerification({ ...attempt, phase: 'running' })
    try {
      const ok = await act(base + '/verify', { expected_revision: lesson.revision })
      setVerification({ ...attempt, phase: ok ? 'complete' : 'error', completedAt: Date.now() })
    } catch (e) {
      const message = (e as Error).message
      setVerification({ ...attempt, phase: 'error', error: message })
      fail(message)
    }
  }
  async function revise(item: TeachingItem, reason: string) {
    const ok = await act(base + '/items', {expected_revision: lesson!.revision, item_id: item.id, replacement: item, reason}, 'PATCH')
    if (ok) setEditing(undefined)
  }
  return <section className="lesson-workspace" aria-label="结构化备课产物">
    <div className="lesson-heading"><div><h3>{lesson.plan.stage} · {lesson.plan.topic}</h3><p className="muted">45分钟 · 教案版本 {lesson.revision}</p></div><span className={`status ${!verifying && lesson.code_status === 'PASS' ? 'success' : ''}`}>{verifying ? '代码验证中…' : lesson.code_status === 'PASS' ? '代码 PASS' : '代码待验证'}</span></div>
    <div className="review-progress" role="status">已接受 {totals.accepted} · 已拒绝 {totals.rejected} · 待审核 {totals.pending} / 共 {Object.keys(lesson.items).length} 项{lesson.profile_stale ? ' · 班情已更新，请重新备课' : ''}</div>
    <div className="actions"><button disabled={pending || verifying} onClick={() => void verify()}><Play size={14} aria-hidden="true" />{verifying ? '正在测试…' : '运行全部代码测试'}</button><button aria-describedby="delivery-diff-hint" disabled={pending || !lesson.delivery_ready} onClick={() => void act(base + '/delivery', {expected_revision: snapshot.session.revision})}>审核交付文件 Diff</button>
      <button aria-describedby="delivery-package-hint" disabled={pending || downloading || !lesson.delivery_ready || !delivery.committed} onClick={() => {setDownloading(true); void download(base + '/package', '循环结构-教案包.zip').catch(e => fail(e.message)).finally(() => setDownloading(false))}}><Download size={14}/>{downloading ? '正在打包下载…' : '下载教案包'}</button></div>
    <DeliveryGuidance lesson={lesson} commits={snapshot.commits} approvals={snapshot.approvals} busy={pending || verifying} editing={!!editing} onVerify={() => void verify()} onReview={openReview} onOpenFiles={onOpenFiles} />
    {downloading && <p role="status" aria-live="polite">正在打包下载教案，请稍候…</p>}
    <VerificationFeedback lesson={lesson} reports={snapshot.verification_reports} phase={currentVerification?.phase} error={currentVerification?.error} completedAt={currentVerification?.completedAt} navigationBlocked={!!editing} onOpen={(name, itemId) => { setTab(name); setReportTarget({ id: itemId, report: true }) }} />
    {!!lesson.curriculum_risks.length && <div className="alert">{lesson.curriculum_risks.map((risk, index) => {
      const related = typeof risk === 'string' ? undefined : Object.values(groups).flat().find(item => item.id === risk.item_id)
      return <p key={index}>{typeof risk === 'string' ? risk : `${related ? teachingTitle(related) : '当前教案'}：${risk.reason}`}</p>
    })}</div>}
    <details><summary>班情依据与教学策略</summary>{lesson.profile.facts.map(f => <p key={f.id}>{f.observation} <small>依据：{sourceLabel(f.source_ref)}</small></p>)}{lesson.profile.unknowns.map(u => <p className="muted" key={u}>{u}</p>)}{lesson.strategies.map(s => <p key={s.id}>{s.action} · {s.target}</p>)}</details>
    <div className="workspace-tabs" role="tablist" aria-label="产物分类" onKeyDown={e => {
      if (editing) return
      const names = Object.keys(groups), index = names.indexOf(tab)
      const next = e.key === 'ArrowRight' ? (index + 1) % names.length : e.key === 'ArrowLeft' ? (index + names.length - 1) % names.length : e.key === 'Home' ? 0 : e.key === 'End' ? names.length - 1 : -1
      if (next < 0) return
      e.preventDefault(); setTab(names[next]); e.currentTarget.querySelectorAll<HTMLButtonElement>('[role=tab]')[next]?.focus()
    }}>{Object.keys(groups).map(name => <button disabled={!!editing} key={name} id={`tab-${name}`} role="tab" tabIndex={tab === name ? 0 : -1} aria-selected={tab === name} aria-controls="lesson-panel" onClick={() => setTab(name)}>{name}</button>)}</div>
    {tab === '教案' && <nav className="lesson-outline" aria-label="教案目录">{sections.map(section => <a key={section.key} href={`#lesson-section-${section.key}`}>{section.title}</a>)}</nav>}
    <div id="lesson-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>{sections.map(section => {
      const counts = reviewCounts(section.items, lesson.items)
      return <section className="lesson-section" id={`lesson-section-${section.key}`} key={section.key} aria-label={section.title}>
        <header className="lesson-section-heading"><h4>{section.title}</h4>{section.items.length > 0 && <small>接受 {counts.accepted} · 拒绝 {counts.rejected} · 待审核 {counts.pending}</small>}</header>
        {!section.items.length && <p className="muted">此旧版教案未包含本节内容，可在继续备课时补充；不会自动改写历史版本。</p>}
        {section.items.map(item => {
      const state = lesson.items[item.id]
      const reports = snapshot.verification_reports.filter(r => r.draft_id === state.draft_id)
      const verificationEntry = verificationEntries.find(entry => entry.id === item.id)
      const draft = snapshot.drafts.find(value => value.id === state.draft_id)
      return <article className="teaching-item" data-review-status={state.review_status} id={`teaching-${item.id}`} tabIndex={-1} key={item.id} aria-label={item.title}>
        <ReviewActions title={<>{item.level && <span>{item.level} · </span>}{teachingTitle(item)}{item.minutes ? ` · ${item.minutes}分钟` : ''}</>} status={state.review_status} note={state.review_note} pending={pending || !!reviewing || !!editing} editing={editing === item.id} canAccept={!lesson.profile_stale && (!item.code || !!state.current_pass)} busy={reviewing?.id === item.id ? reviewing.decision : undefined} error={reviewError?.id === item.id && reviewError.revision === lesson.revision ? reviewError.message : undefined} onReview={decision => void reviewItem(item, decision)} onEdit={() => setEditing(item.id)} />
        {editing === item.id ? <ItemEditor item={item} pending={pending} cancel={() => setEditing(undefined)} save={value => void revise(value, '教师编辑教学项目')}/> : <>
          {item.content && <p>{item.content}</p>}{item.criterion && <p>{item.criterion}</p>}{item.activity && <p>{item.activity}</p>}{item.prompt && <p>{item.prompt}</p>}{item.explanation && <p>{item.explanation}</p>}
          {(item.teacher_actions || item.student_actions || item.assessment) && <dl className="teaching-steps">{item.teacher_actions && <><dt>教师活动</dt><dd>{item.teacher_actions}</dd></>}{item.student_actions && <><dt>学生活动</dt><dd>{item.student_actions}</dd></>}{item.assessment && <><dt>达成检查与反馈</dt><dd>{item.assessment}</dd></>}</dl>}
          {item.scaffolding && <p className="muted">支架：{item.scaffolding}</p>}{item.code && <pre aria-label="Python参考代码">{item.code}</pre>}
          {item.scoring && <ul className="scoring">{item.scoring.map((s, i) => <li key={i}><strong>{s.points}分</strong> {s.criterion}</li>)}</ul>}
          {item.trigger && <MisconceptionReferences item={item} lesson={lesson} blocked={!!editing} onOpen={id => { setTab('分层练习'); setReportTarget({ id, report: false }) }} />}
          {state.verification_status && <VerificationDiagnostic status={verificationEntry?.status || state.verification_status} report={verificationEntry?.report} changed={!!draft?.repair_diff} pending={pending || verifying} onVerify={() => void verify()} />}
          {reports.map(r => <Report report={r} key={r.id}/>)}
          {draft?.repair_diff && <details><summary>代码修改 Diff</summary><DiffView diff={draft.repair_diff} filePath={draft.path} fromLabel="上一版代码" toLabel="当前草稿" /></details>}
        </>}
      </article>
        })}
      </section>
    })}</div>
    <label className="review-note">审核说明（可选）<input value={note} maxLength={1000} placeholder="记录教学适配或修订原因" onChange={e => setNote(e.target.value)}/></label>
    <details onToggle={e => {if(e.currentTarget.open) void api<{history: Lesson[]}>(base).then(r => setHistory(r.history)).catch(e => fail(e.message))}}><summary><History size={14}/>历史版本与回退</summary>{history.filter(h => h.revision < lesson.revision).map(h => <details key={h.revision}><summary>版本 {h.revision}</summary>{['教案', '示例代码', '分层练习', '错因预警'].flatMap(name => lessonSections(h.plan, name)).filter(section => section.items.length).map(section => <section key={section.key} className="history-section"><h4>{section.title}</h4>{section.items.map(item => <div key={item.id} className="history-item"><p>{teachingTitle(item)}</p><details><summary>查看历史内容</summary><pre>{[item.content, item.criterion, item.activity, item.teacher_actions && `教师活动：${item.teacher_actions}`, item.student_actions && `学生活动：${item.student_actions}`, item.assessment && `达成检查：${item.assessment}`, item.prompt, item.explanation, item.code, item.teaching_intervention].filter(Boolean).join('\n\n')}</pre></details><button disabled={pending || !!editing} onClick={() => void revise(item, `从历史版本${h.revision}恢复项目`)}><Undo2 size={14}/>恢复为新草稿</button></div>)}</section>)}</details>)}</details>
  </section>
}
