import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowUp, FileText, FolderOpen, Plus, RefreshCw, Square, GraduationCap } from 'lucide-react'
import { api, type AgentEvent, type Runtime, type Session, type Snapshot } from './api'

const statuses: Record<string, string> = {
  READY: '准备中', RUNNING: '正在处理', WAITING_APPROVAL: '等待教师审核', COMPLETED: '本轮已结束',
  FAILED: '执行失败', STOPPED: '已停止', INTERRUPTED: '任务中断，可继续',
}
const eventNames: Record<string, string> = {
  'run.created': '已接收需求', 'run.started': '开始处理', 'model.requested': '正在思考…',
  'model.completed': '已收到模型回复', 'model.failed': '模型调用失败',
  'tool.started': '开始操作', 'tool.completed': '操作已完成', 'tool.failed': '操作失败',
  'verification.started': '开始验证代码', 'verification.completed': '代码验证已结束', 'test_spec.frozen': '测试规格已冻结',
  'artifact.revised': '草稿已保存', 'approval.requested': '请审核文件变更',
  'approval.decided': '已拒绝变更', 'run.paused': '已暂停，等待审核',
  'run.failed': '本轮失败', 'run.stopped': '本轮已停止', 'run.completed': '本轮已结束',
  'run.interrupted': '任务已中断', 'session.created': '工作区已准备',
}
const toolNames: Record<string, string> = {
  list_files: '列出工作区文件', read_file: '读取文件', propose_patch: '保存草稿',
  read_draft: '读取草稿', get_verification: '读取测试与报告', run_python_tests: '执行代码验证', request_publish: '请求正式变更',
}
const verificationLabels: Record<string, string> = {
  PASS: '用例通过，待教师审核', NOT_TESTED: '未测试', STALE: '验证已过期，请重新测试',
  SYNTAX_ERROR: '语法错误', ASSERTION_ERROR: '断言失败', OUTPUT_MISMATCH: '输出不匹配',
  RUNTIME_ERROR: '运行异常', TIMEOUT: '执行超时', RESOURCE_LIMIT: '资源超限',
  OUTPUT_LIMIT: '输出超限', RUNNER_ERROR: '执行器故障', INTERRUPTED: '验证中断',
}
const active = new Set(['READY', 'RUNNING', 'WAITING_APPROVAL', 'INTERRUPTED'])

export default function App() {
  const [runtime, setRuntime] = useState<Runtime>()
  const [sessions, setSessions] = useState<Session[]>([])
  const [sid, setSid] = useState<string>()
  const [snapshot, setSnapshot] = useState<Snapshot>()
  const [files, setFiles] = useState<{ path: string; size: number }[]>([])
  const [file, setFile] = useState<{ path: string; content: string }>()
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [text, setText] = useState('')
  const [stage, setStage] = useState('初中')
  const [grade, setGrade] = useState('初二')
  const [topic, setTopic] = useState('循环结构')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const [connected, setConnected] = useState(false)
  const [streamError, setStreamError] = useState(false)
  const [showWorkspace, setShowWorkspace] = useState(true)
  const messageRef = useRef<HTMLTextAreaElement>(null)
  const generation = useRef(0)

  const refresh = useCallback(async (id: string) => {
    const current = generation.current
    const data = await api<Snapshot>(`/sessions/${id}`)
    const listing = await api<{ files: typeof files }>(`/workspaces/${data.session.workspace_id}/files`)
    if (generation.current === current) {
      setSnapshot(previous => previous && previous.event_cursor > data.event_cursor ? previous : data)
      setFiles(listing.files)
    }
  }, [])

  const connect = useCallback(async () => {
    setError('')
    try {
      setRuntime(await api<Runtime>('/runtime'))
      await api('/client', {})
      const data = await api<{ sessions: Session[] }>('/sessions')
      setSessions(data.sessions)
      const saved = localStorage.getItem('yunyun_session')
      if (saved && data.sessions.some(s => s.id === saved)) setSid(saved)
      setConnected(true)
    } catch (e) { setError((e as Error).message) }
  }, [])

  useEffect(() => { void connect() }, [connect])
  useEffect(() => {
    if (snapshot?.session) {
      setStage(snapshot.session.context.stage)
      setGrade(snapshot.session.context.grade)
      setTopic(snapshot.session.context.topic)
    }
  }, [snapshot?.session.id])
  useEffect(() => {
    if (!text.trim()) return
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault() }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [text])
  useEffect(() => {
    generation.current += 1
    setSnapshot(undefined); setEvents([]); setFiles([]); setFile(undefined); setStreamError(false)
    if (!sid) return
    localStorage.setItem('yunyun_session', sid)
    const current = generation.current
    void refresh(sid).catch(e => setError(e.message))
    const source = new EventSource(`/api/sessions/${sid}/events`)
    let timer: ReturnType<typeof setTimeout> | undefined
    source.addEventListener('agent', raw => {
      if (generation.current !== current) return
      const event = JSON.parse((raw as MessageEvent).data) as AgentEvent
      setStreamError(false)
      setEvents(previous => previous.some(e => e.event_id === event.event_id) ? previous : [...previous, event].slice(-200))
      clearTimeout(timer)
      timer = setTimeout(() => { void refresh(sid).catch(e => setError(e.message)) }, 100)
    })
    source.onopen = () => setStreamError(false)
    source.onerror = () => setStreamError(true)
    return () => { source.close(); clearTimeout(timer) }
  }, [sid, refresh])

  const run = snapshot?.runs.at(-1)
  const blocked = pending || !!(run && active.has(run.status))
  const messages = snapshot?.messages.filter(m => m.role !== 'tool' && m.content) || []
  const hasMessages = messages.length > 0

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!text.trim()) { messageRef.current?.focus(); return }
    setPending(true); setError('')
    try {
      let session = snapshot?.session
      if (!sid) {
        const data = await api<{ session: Session }>('/sessions', { stage, grade, topic })
        session = data.session; setSessions(old => [...old, data.session]); setSid(session.id)
      }
      if (!session) throw new Error('工作区仍在读取，请稍后重试。')
      await api(`/sessions/${session.id}/messages`, { content: text,
        expected_revision: session.revision, idempotency_key: crypto.randomUUID() })
      setText(''); await refresh(session.id)
    } catch (e) { setError((e as Error).message) }
    finally { setPending(false) }
  }

  async function action(path: string, body: unknown) {
    setPending(true); setError('')
    try { await api(path, body); if (sid) await refresh(sid) }
    catch (e) { setError((e as Error).message) }
    finally { setPending(false) }
  }

  return <div className="app-shell">
    <a className="skip-link" href="#conversation">跳到备课对话</a>
    <aside className="sidebar" aria-label="备课会话">
      <div className="brand"><GraduationCap aria-hidden="true" size={25} /><span>耘耘AI助教</span></div>
      <button className="new-session" onClick={() => {
        generation.current += 1; setSid(undefined); localStorage.removeItem('yunyun_session'); setError('')
      }}><Plus size={16} aria-hidden="true" />新建备课会话</button>
      <h2>最近会话</h2>
      <nav aria-label="历史会话">{sessions.length ? [...sessions].reverse().map(s =>
        <button className={sid === s.id ? 'session selected' : 'session'} key={s.id} aria-current={sid === s.id ? 'page' : undefined}
          onClick={() => { setSid(s.id); setError('') }}>
          <span>{s.context.topic || '备课会话'}</span><small>{s.context.grade} · {new Date(s.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}</small>
        </button>) : <p className="muted">开始后，会话会保存在这里。</p>}</nav>
      <p className="sidebar-note">{runtime?.mode === 'pc' ? '本机授权工作区' : '独立演示工作区'}<br />{runtime?.runner === 'ISOLATED' ? '隔离代码执行可用' : '隔离执行器不可用，禁止交付代码'}</p>
    </aside>

    <main id="conversation" className="conversation">
      <header className="toolbar">
        <div><h1 className="page-title">教师备课工作台</h1><span className={runtime?.mock ? 'badge mock' : 'badge'}>{runtime?.mock ? 'MOCK_LLM · 离线演示' : runtime?.model || '连接中…'}</span></div>
        <button className="subtle" onClick={() => setShowWorkspace(v => !v)} aria-expanded={showWorkspace}><FolderOpen size={16} aria-hidden="true" />工作区</button>
      </header>
      <div className="notice">代码须通过冻结用例后交由教师审核；正式写入与教案包尚未开放。</div>
      {runtime && !runtime.mock && !runtime.key_configured && <p className="alert" role="alert">未配置百炼密钥，请完成本地配置并重启服务。</p>}
      {error && <div className="alert" role="alert">{error}{!connected && <button onClick={() => void connect()}>重新连接</button>}</div>}
      <div className="chat-scroll">
        {!hasMessages && <section className="welcome"><GraduationCap size={34} aria-hidden="true" /><h2>从这节课的备课需求开始</h2><p>让助教读取工作区，提出可检查的修改草稿。</p></section>}
        {messages.map((m, index) => <article key={index} className={`message ${m.role === 'user' ? 'teacher' : 'assistant'}`}>
          <h2>{m.role === 'user' ? '我' : '耘耘AI助教'}{runtime?.mock && m.role !== 'user' ? ' · MOCK_LLM' : ''}</h2><p>{m.content}</p>
        </article>)}
        {run && <section className="execution" aria-label="执行过程">
          <div className="run-status" role="status">{statuses[run.status] || run.status}<span>思考 {run.steps} 次 · 操作 {run.tool_count} 次</span></div>
          {run.error && <p className="alert" role="alert">{run.error.message}<small>{run.error.code}</small></p>}
          {['INTERRUPTED', 'FAILED'].includes(run.status) && <button disabled={pending} onClick={() => void action(`/sessions/${sid}/resume`, { expected_revision: snapshot!.session.revision })}><RefreshCw size={14} aria-hidden="true" />继续当前任务</button>}
          {['READY', 'RUNNING', 'WAITING_APPROVAL', 'INTERRUPTED', 'FAILED'].includes(run.status) && <button className="subtle" disabled={pending} onClick={() => void action(`/runs/${run.id}/cancel`, {})}><Square size={13} aria-hidden="true" />停止任务</button>}
          <details><summary>查看执行记录（{events.length}）</summary><ol className="events">{events.map(ev => <li key={ev.event_id}>
            <span>{eventNames[ev.type] || ev.type}{typeof ev.payload.name === 'string' ? ` · ${toolNames[ev.payload.name] || ev.payload.name}` : ''}</span>
            <time>{new Date(ev.timestamp).toLocaleTimeString('zh-CN')}</time>
            {ev.type === 'tool.failed' && <details><summary>失败详情</summary><pre>{JSON.stringify(ev.payload.result, null, 2)}</pre></details>}
          </li>)}</ol></details>
          {streamError && <p className="muted" role="status">进度连接已断开，正在重连。<button className="subtle" onClick={() => sid && void refresh(sid).catch(e => setError(e.message))}>刷新状态</button></p>}
        </section>}
      </div>
      <form className="composer" onSubmit={submit}>
        <fieldset disabled={!!sid || pending}><legend>教学上下文</legend><div className="context-fields">
          <label>学段<select name="stage" value={stage} onChange={e => setStage(e.target.value)}><option>初中</option><option>大学</option></select></label>
          <label>年级<input name="grade" autoComplete="off" value={grade} maxLength={30} onChange={e => setGrade(e.target.value)} /></label>
          <label>主题<input name="topic" autoComplete="off" value={topic} maxLength={100} onChange={e => setTopic(e.target.value)} /></label>
        </div></fieldset>
        <label htmlFor="request">备课需求</label><textarea ref={messageRef} id="request" name="request" autoComplete="off" value={text} maxLength={12000} onChange={e => setText(e.target.value)}
          placeholder="例如：读取工作区的示例代码，检查循环边界并提出修改草稿…" rows={3} />
        <div className="composer-footer"><small>{sid ? '会话已保存，可从历史继续' : '将创建独立的备课会话'}</small><button className="primary" type="submit" disabled={!connected || blocked}><ArrowUp size={16} aria-hidden="true" />{pending ? '发送中…' : '发送需求'}</button></div>
      </form>
    </main>

    {showWorkspace && <aside className="workspace" aria-label="工作区文件与草稿">
      <h2><FolderOpen size={17} aria-hidden="true" />工作区</h2>
      {!sid ? <p className="muted">发起任务后查看文件与修改草稿。</p> : <>
        <h3>文件（{files.length}）</h3><ul className="file-list">{files.map(f => <li key={f.path}><button onClick={() => {
          const current = generation.current
          void api<{ path: string; content: string }>(`/workspaces/${snapshot!.session.workspace_id}/file?path=${encodeURIComponent(f.path)}`)
            .then(value => { if (generation.current === current) setFile(value) }).catch(e => setError(e.message))
        }}><FileText size={14} aria-hidden="true" />{f.path}</button></li>)}</ul>
        {!files.length && <p className="muted">{snapshot ? '工作区为空，可以请助教提出新文件草稿。' : '正在读取工作区…'}</p>}
        {file && <details open><summary>{file.path}</summary><pre>{file.content}</pre></details>}
        <h3>修改草稿</h3>{!snapshot?.drafts.length && <p className="muted">助教提出的修改会显示在这里。</p>}
        {snapshot?.drafts.map(d => <section className="draft" key={d.id}><strong>{d.path}</strong><p className="muted">版本 {d.revision} · {d.operation === 'delete' ? '待删除' : '草稿'} · {verificationLabels[d.verification_status] || '未测试'}{d.mock ? ' · MOCK_LLM' : ''}</p><details><summary>查看文件差异</summary><pre>{d.diff || '内容无差异'}</pre></details>
          {d.repair_diff && <details><summary>与上一版代码对比</summary><pre>{d.repair_diff}</pre></details>}
          {snapshot.verification_reports?.filter(r => r.draft_id === d.id).map(r => <details key={r.id}>
            <summary>验证报告：{verificationLabels[r.effective_status] || r.effective_status}</summary>
            <p className="muted">{r.effective_status === 'STALE' ? '历史结果不能作为当前交付依据。' : '仅覆盖这些输入；教学适用性仍需教师审核。'}</p>
            {r.cases.map(c => <section key={c.id} aria-label={`用例 ${c.id}`}>
              <strong>{c.id} · {verificationLabels[c.status] || c.status}</strong>
              <p>耗时 {Math.round(c.duration_ms)} ms · 退出码 {c.exit_code ?? '无'}</p>
              <pre>{`输入：${c.input}\n期望：${c.expected}\n实际：${c.actual}`}</pre>
              {c.error && <p className="alert">{c.error}</p>}
              {(c.stdout || c.stderr) && <details><summary>运行日志</summary><pre>{`stdout:\n${c.stdout}\nstderr:\n${c.stderr}`}</pre></details>}
            </section>)}
            <details><summary>版本证据</summary><pre>{`代码 SHA256：${r.code_hash}\n验证指纹：${r.fingerprint}`}</pre></details>
          </details>)}
          {snapshot.approvals.filter(a => a.draft_id === d.id).map(a => <div key={a.id}>{a.status === 'PENDING' ? <><p>已请求正式变更；暂不开放批准写入。</p><button disabled={pending} onClick={() => void action(`/approvals/${a.id}/decision`, { decision: 'reject', expected_revision: snapshot.session.revision })}>拒绝本次变更</button></> : <p className="muted">{a.status === 'REJECTED' ? '已拒绝，正式文件未改变' : a.status === 'STALE' ? '版本已变更，审批已过期' : '请求已取消'}</p>}</div>)}
        </section>)}
        {!!snapshot?.usage.length && <p className="muted">累计估算 / 预留 ¥{snapshot.usage.reduce((total, u) => total + u.cny, 0).toFixed(4)}{snapshot.usage.some(u => u.status === 'RESERVED_UNKNOWN') ? '（含用量未知请求）' : ''}</p>}
      </>}
    </aside>}
  </div>
}
