import { useEffect, useState } from 'react'
import { Check, X, Play, Download, History, Pencil, Save, Undo2 } from 'lucide-react'
import { api, download, type Lesson, type Snapshot, type TeachingItem, type VerificationReport } from './api'

type Props = { snapshot: Snapshot; pending: boolean; act: (path: string, body: unknown, method?: string) => Promise<boolean>; fail: (message: string) => void }
export function Report({ report }: { report: VerificationReport }) {
  return <details className="report"><summary>{report.effective_status} · {report.cases.length} 条用例</summary>
    {report.cases.map(c => <section key={c.id} className="test-case"><strong>{c.id} · {c.status}</strong><small> {Math.round(c.duration_ms)} ms · 退出码 {c.exit_code ?? '无'}</small>
      <pre>{`输入：${JSON.stringify(c.input)}\n期望：${JSON.stringify(c.expected)}\n实际：${JSON.stringify(c.actual)}`}</pre>
      {c.error && <p className="failure">{c.error}</p>}{c.stderr && <pre>{c.stderr}</pre>}
    </section>)}<details><summary>版本证据</summary><code>{report.code_hash}<br />{report.fingerprint}</code></details>
  </details>
}

function ItemEditor({ item, save, cancel, pending }: {item: TeachingItem; save: (item: TeachingItem) => void; cancel: () => void; pending: boolean}) {
  const [value, setValue] = useState(item)
  useEffect(() => {
    if (JSON.stringify(value) === JSON.stringify(item)) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [value, item])
  const fields: [keyof TeachingItem, string][] = [['criterion', '达成标准'], ['activity', '教学活动'], ['explanation', '讲解与参考论证'], ['prompt', '题目'], ['scaffolding', '学习支架'], ['code', 'Python代码'], ['trigger', '触发情况'], ['cause', '原因假设'], ['teaching_intervention', '课堂干预']]
  return <form className="item-editor" onSubmit={e => {e.preventDefault(); save(value)}}><fieldset className="editor-fields" disabled={pending}>
    <label>标题<input value={value.title} required maxLength={150} onChange={e => setValue({...value, title: e.target.value})} /></label>
    {fields.filter(([key]) => item[key] !== undefined).map(([key, label]) => <label key={key}>{label}<textarea value={String(value[key] ?? '')} rows={key === 'code' ? 8 : 3} maxLength={key === 'code' ? 8000 : 1200} onChange={e => setValue({...value, [key]: e.target.value})} /></label>)}
    {value.scoring?.map((point, index) => <div key={index} className="scoring-edit"><label>评分点<input value={point.criterion} onChange={e => setValue({...value, scoring: value.scoring!.map((p, i) => i === index ? {...p, criterion: e.target.value} : p)})}/></label><label>分值<input type="number" min={1} max={100} value={point.points} onChange={e => setValue({...value, scoring: value.scoring!.map((p, i) => i === index ? {...p, points: Number(e.target.value)} : p)})}/></label></div>)}
    <div className="actions"><button className="primary" type="submit"><Save size={14}/>保存新版本</button><button type="button" onClick={cancel}>取消</button></div>
  </fieldset></form>
}

export default function EducationWorkspace({snapshot, pending, act, fail}: Props) {
  const lesson = snapshot.lessons.at(-1)
  const [tab, setTab] = useState('教案')
  const [editing, setEditing] = useState<string>()
  const [note, setNote] = useState('')
  const [history, setHistory] = useState<Lesson[]>([])
  const [downloading, setDownloading] = useState(false)
  const sid = snapshot.session.id
  if (!lesson) return <div className="empty-state"><h3>等待备课产物</h3><p>导入班情后发送备课需求。教案、代码、练习与错因预警会在这里出现。</p></div>
  const base = `/sessions/${sid}/lessons/${lesson.lesson_id}`
  const groups: Record<string, TeachingItem[]> = {'教案': [...lesson.plan.goals, ...lesson.plan.segments], '示例代码': lesson.plan.examples, '分层练习': lesson.plan.exercises, '错因预警': lesson.plan.misconceptions}
  async function revise(item: TeachingItem, reason: string) {
    const ok = await act(base + '/items', {expected_revision: lesson!.revision, item_id: item.id, replacement: item, reason}, 'PATCH')
    if (ok) setEditing(undefined)
  }
  return <section className="lesson-workspace" aria-label="结构化备课产物">
    <div className="lesson-heading"><div><h3>{lesson.plan.stage} · {lesson.plan.topic}</h3><p className="muted">45分钟 · 教案版本 {lesson.revision}</p></div><span className={`status ${lesson.code_status === 'PASS' ? 'success' : ''}`}>{lesson.code_status === 'PASS' ? '代码 PASS' : '代码待验证'}</span></div>
    <div className="review-progress" role="status">已审核 {Object.values(lesson.items).filter(i => i.review_status === 'ACCEPTED').length} / {Object.keys(lesson.items).length} 项{lesson.profile_stale ? ' · 班情已更新，请重新备课' : ''}</div>
    <div className="actions"><button disabled={pending} onClick={() => void act(base + '/verify', {expected_revision: lesson.revision})}><Play size={14}/>运行全部代码测试</button><button disabled={pending || !lesson.delivery_ready} onClick={() => void act(base + '/delivery', {expected_revision: snapshot.session.revision})}>审核交付文件 Diff</button>
      <button disabled={pending || downloading || !lesson.delivery_ready || !snapshot.commits.some(c => c.status === 'COMMITTED' && c.lesson_id === lesson.lesson_id)} onClick={() => {setDownloading(true); void download(base + '/package', '循环结构-教案包.zip').catch(e => fail(e.message)).finally(() => setDownloading(false))}}><Download size={14}/>{downloading ? '正在打包下载…' : '下载教案包'}</button></div>
    {downloading && <p role="status" aria-live="polite">正在打包下载教案，请稍候…</p>}
    {!lesson.delivery_ready && <p className="muted">全部代码通过并逐项接受后，可确认文件Diff并交付。</p>}
    {!!lesson.curriculum_risks.length && <div className="alert">{lesson.curriculum_risks.map((r,i) => <p key={i}>{typeof r === 'string' ? r : JSON.stringify(r)}</p>)}</div>}
    <details><summary>班情依据与教学策略</summary>{lesson.profile.facts.map(f => <p key={f.id}>{f.observation} <small>依据：{f.source_ref}</small></p>)}{lesson.profile.unknowns.map(u => <p className="muted" key={u}>{u}</p>)}{lesson.strategies.map(s => <p key={s.id}>{s.action} · {s.target}</p>)}</details>
    <div className="workspace-tabs" role="tablist" aria-label="产物分类" onKeyDown={e => {
      const names = Object.keys(groups), index = names.indexOf(tab)
      const next = e.key === 'ArrowRight' ? (index + 1) % names.length : e.key === 'ArrowLeft' ? (index + names.length - 1) % names.length : e.key === 'Home' ? 0 : e.key === 'End' ? names.length - 1 : -1
      if (next < 0) return
      e.preventDefault(); setTab(names[next]); e.currentTarget.querySelectorAll<HTMLButtonElement>('[role=tab]')[next]?.focus()
    }}>{Object.keys(groups).map(name => <button key={name} id={`tab-${name}`} role="tab" tabIndex={tab === name ? 0 : -1} aria-selected={tab === name} aria-controls="lesson-panel" onClick={() => setTab(name)}>{name}</button>)}</div>
    <div id="lesson-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>{groups[tab].map(item => {
      const state = lesson.items[item.id]
      const reports = snapshot.verification_reports.filter(r => r.draft_id === state.draft_id)
      return <article className="teaching-item" key={item.id} aria-label={item.title}>
        <div className="item-heading"><h4>{item.level && <span>{item.level} · </span>}{item.title}{item.minutes ? ` · ${item.minutes}分钟` : ''}</h4><span className={`status ${state.review_status === 'ACCEPTED' ? 'success' : state.review_status === 'REJECTED' ? 'failure' : ''}`}>{({ACCEPTED:'已接受',REJECTED:'已拒绝',PENDING:'待审核'} as Record<string,string>)[state.review_status]}</span></div>
        {editing === item.id ? <ItemEditor item={item} pending={pending} cancel={() => setEditing(undefined)} save={value => void revise(value, '教师编辑教学项目')}/> : <>
          {item.criterion && <p>{item.criterion}</p>}{item.activity && <p>{item.activity}</p>}{item.prompt && <p>{item.prompt}</p>}{item.explanation && <p>{item.explanation}</p>}
          {item.scaffolding && <p className="muted">支架：{item.scaffolding}</p>}{item.code && <pre aria-label="Python参考代码">{item.code}</pre>}
          {item.scoring && <ul className="scoring">{item.scoring.map((s, i) => <li key={i}><strong>{s.points}分</strong> {s.criterion}</li>)}</ul>}
          {item.trigger && <dl><dt>依据</dt><dd>{item.basis === 'observed' ? '观察到的班情' : '预测风险'} · {item.evidence_ids?.join('、') || '无直接观察'}</dd><dt>触发情况</dt><dd>{item.trigger}</dd><dt>原因假设</dt><dd>{item.cause}</dd><dt>课堂干预</dt><dd>{item.teaching_intervention}</dd><dt>关联练习</dt><dd>{item.exercise_ids?.join('、')}</dd></dl>}
          {state.verification_status && <p className={state.current_pass ? 'success' : 'failure'}>验证：{state.verification_status}{state.current_pass ? ' · 当前固定用例通过' : ' · 不能交付'}</p>}
          {reports.map(r => <Report report={r} key={r.id}/>)}
          {state.draft_id && snapshot.drafts.find(d => d.id === state.draft_id)?.repair_diff && <details><summary>代码修改 Diff</summary><pre>{snapshot.drafts.find(d => d.id === state.draft_id)?.repair_diff}</pre></details>}
          <div className="actions"><button disabled={pending || (!!item.code && !state.current_pass)} onClick={() => void act(base + '/reviews', {expected_revision: lesson.revision, item_id: item.id, decision: 'accept', note: note.trim() || '教师确认本项可用于课堂'})}><Check size={14}/>接受</button><button disabled={pending} onClick={() => void act(base + '/reviews', {expected_revision: lesson.revision, item_id: item.id, decision: 'reject', note: note.trim() || '教师拒绝，需继续修订'})}><X size={14}/>拒绝</button><button disabled={pending} onClick={() => setEditing(item.id)}><Pencil size={14}/>继续修改</button></div>
        </>}
      </article>
    })}</div>
    <label className="review-note">审核说明（可选）<input value={note} maxLength={1000} placeholder="记录教学适配或修订原因" onChange={e => setNote(e.target.value)}/></label>
    <details onToggle={e => {if(e.currentTarget.open) void api<{history: Lesson[]}>(base).then(r => setHistory(r.history)).catch(e => fail(e.message))}}><summary><History size={14}/>历史版本与回退</summary>{history.filter(h => h.revision < lesson.revision).map(h => <details key={h.revision}><summary>版本 {h.revision}</summary>{Object.values(h.plan).filter(Array.isArray).flat().filter((i): i is TeachingItem => !!i && typeof i === 'object' && 'id' in i).map(item => <div key={item.id} className="history-item"><p>{item.title}</p><details><summary>查看历史内容</summary><pre>{item.code || item.activity || item.explanation || item.criterion || item.teaching_intervention}</pre></details><button disabled={pending} onClick={() => void revise(item, `从历史版本${h.revision}恢复项目`)}><Undo2 size={14}/>恢复为新草稿</button></div>)}</details>)}</details>
  </section>
}
