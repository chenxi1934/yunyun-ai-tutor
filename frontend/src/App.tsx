import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowUp, ChevronDown, FolderOpen, Plus, RefreshCw, Square, GraduationCap } from 'lucide-react'
import EducationWorkspace from './EducationWorkspace'
import ChatMessage from './ChatMessage'
import DiffView from './DiffView'
import WorkspaceFiles from './WorkspaceFiles'
import VerificationDiagnostic, { Report } from './VerificationDiagnostic'
import { api, uploadProfile, type Recovery, type AgentEvent, type Runtime, type Session, type Snapshot } from './api'

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
  'approval.decided': '审批已处理', 'workspace.committed': '正式文件已写入', 'lesson.revised': '教案草稿已更新', 'lesson.item_reviewed': '教学项目已审核', 'run.paused': '已暂停，等待审核',
  'run.failed': '本轮失败', 'run.stopped': '本轮已停止', 'run.completed': '本轮已结束',
  'workspace.interrupted': '正式写入中断，须对账恢复', 'workspace.reconciled': '中断提交已对账',
  'run.interrupted': '任务已中断', 'session.created': '工作区已准备',
  'class_profile.imported': '班情已保存',
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
  const [file, setFile] = useState<{ path: string; content: string; hash: string | null }>()
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [text, setText] = useState('')
  const [profile, setProfile] = useState('')
  const [profileFormat, setProfileFormat] = useState('text')
  const [profileMode, setProfileMode] = useState<'replace' | 'supplement'>('supplement')
  const [profileFile, setProfileFile] = useState<File>()
  const [uploadError, setUploadError] = useState('')
  const [recovery, setRecovery] = useState<Recovery>()
  const [panel, setPanel] = useState('备课产物')
  const [fileEdit, setFileEdit] = useState<string>()
  const [newPath, setNewPath] = useState('')
  const [stage, setStage] = useState('初中')
  const [grade, setGrade] = useState('初二')
  const [topic, setTopic] = useState('循环结构')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const [activity, setActivity] = useState('')
  const [loadingFile, setLoadingFile] = useState(false)
  const [connected, setConnected] = useState(false)
  const [streamError, setStreamError] = useState(false)
  const [showWorkspace, setShowWorkspace] = useState(false)
  const messageRef = useRef<HTMLTextAreaElement>(null)
  const profileInputRef = useRef<HTMLInputElement>(null)
  const generation = useRef(0)
  const selectedSid = useRef<string | undefined>(undefined)
  const fileGeneration = useRef(0)
  const profileGeneration = useRef(0)
  type Scope = { id: string | undefined; epoch: number }
  const currentScope = (): Scope => ({ id: selectedSid.current, epoch: generation.current })
  const isCurrent = useCallback((scope: Scope) => selectedSid.current === scope.id && generation.current === scope.epoch, [])

  const selectSession = useCallback((id: string | undefined) => {
    generation.current += 1; selectedSid.current = id; fileGeneration.current += 1; profileGeneration.current += 1
    setSid(id); setSnapshot(undefined); setEvents([]); setFiles([]); setFile(undefined); setFileEdit(undefined)
    setRecovery(undefined); setLoadingFile(false); setStreamError(false); setPending(false); setActivity(''); setError('')
    setProfileFile(undefined); setUploadError(''); setProfile(''); setProfileFormat('text'); setProfileMode('supplement')
    if (profileInputRef.current) {
      profileInputRef.current.value = ''
    }
    if (id) localStorage.setItem('yunyun_session', id)
    else localStorage.removeItem('yunyun_session')
  }, [])

  const refresh = useCallback(async (id: string, epoch: number) => {
    const scope = { id, epoch }
    if (!isCurrent(scope)) return
    const data = await api<Snapshot>(`/sessions/${id}`)
    if (!isCurrent(scope) || data.session.id !== id) return
    const listing = await api<{ files: { path: string; size: number }[] }>(`/workspaces/${data.session.workspace_id}/files`)
    if (!isCurrent(scope) || data.session.id !== id) return
    setSnapshot(previous => !isCurrent(scope) || (previous?.session.id === id && previous.event_cursor > data.event_cursor) ? previous : data)
    setFiles(listing.files)
  }, [isCurrent])

  const connect = useCallback(async () => {
    const epoch = generation.current
    setError('')
    try {
      setRuntime(await api<Runtime>('/runtime'))
      await api('/client', {})
      const data = await api<{ sessions: Session[] }>('/sessions')
      setSessions(data.sessions)
      const saved = localStorage.getItem('yunyun_session')
      if (generation.current === epoch && saved && data.sessions.some(s => s.id === saved)) { selectSession(saved); setShowWorkspace(true) }
      setConnected(true)
    } catch (e) { setError((e as Error).message) }
  }, [selectSession])

  useEffect(() => { void connect() }, [connect])
  useEffect(() => {
    if (snapshot?.session) {
      setStage(snapshot.session.context.stage)
      setGrade(snapshot.session.context.grade)
      setTopic(snapshot.session.context.topic)
    }
  }, [snapshot?.session.id])
  useEffect(() => {
    if (!text.trim() && !profile.trim() && !profileFile && fileEdit === undefined) return
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault() }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [text, profile, profileFile, fileEdit])
  useEffect(() => {
    if (!sid) return
    const scope = { id: sid, epoch: generation.current }
    if (!isCurrent(scope)) return
    const update = () => { void refresh(sid, scope.epoch).catch(e => { if (isCurrent(scope)) setError(e.message) }) }
    update()
    const source = new EventSource(`/api/sessions/${sid}/events`)
    let timer: ReturnType<typeof setTimeout> | undefined
    source.addEventListener('agent', raw => {
      if (!isCurrent(scope)) return
      const event = JSON.parse((raw as MessageEvent).data) as AgentEvent
      setStreamError(false)
      setEvents(previous => isCurrent(scope) ? previous.some(e => e.event_id === event.event_id) ? previous : [...previous, event].slice(-200) : previous)
      clearTimeout(timer); timer = setTimeout(update, 100)
    })
    source.onopen = () => { if (isCurrent(scope)) setStreamError(false) }
    source.onerror = () => { if (isCurrent(scope)) setStreamError(true) }
    return () => { source.close(); clearTimeout(timer) }
  }, [sid, refresh, isCurrent])

  const run = snapshot?.runs.at(-1)
  const unresolved = snapshot?.commits.some(c => ['APPLYING', 'ROLLING_BACK', 'INTERRUPTED'].includes(c.status))
  const blocked = pending || !!unresolved || !!(run && active.has(run.status))
  const renderScope = { id: sid, epoch: generation.current }
  const messages = snapshot?.messages.filter(m => m.role !== 'tool' && m.content) || []
  const hasMessages = messages.length > 0
  const currentProfile = snapshot?.profiles.at(-1)?.profile
  const teachingContext = sid ? snapshot?.session.context : { stage, grade, topic }
  const contextSummary = teachingContext
    ? [teachingContext.stage, teachingContext.grade, teachingContext.topic].filter(Boolean).join(' · ')
    : '正在读取教学设置…'

  function setProfileInput(content: string, format: string) {
    profileGeneration.current += 1; setProfileFile(undefined); setUploadError(''); setProfile(content); setProfileFormat(format)
    if (profileInputRef.current) profileInputRef.current.value = ''
  }

  async function readProfile(f: File) {
    const scope = currentScope(), read = ++profileGeneration.current
    if (f.size > 1048576 || !/\.(json|csv)$/i.test(f.name)) {
      const message = f.size > 1048576 ? '上传上限为1 MiB' : '请选择JSON或CSV文件'
      setProfileFile(undefined); setUploadError(message); setError(message); return
    }
    setProfileFile(f); setProfileFormat(f.name.toLowerCase().endsWith('.csv') ? 'csv' : 'json'); setUploadError('')
    try {
      const value = await f.text()
      if (isCurrent(scope) && profileGeneration.current === read) setProfile(value)
    } catch (e) { if (isCurrent(scope) && profileGeneration.current === read) { setUploadError((e as Error).message); setError((e as Error).message) } }
  }

  async function importProfile(session: Session) {
    if (uploadError) throw new Error(uploadError)
    const scope = currentScope(), read = profileGeneration.current
    if (profileFile) await uploadProfile(session.id, profileFile, profileFormat, session.revision, profileMode)
    else await api(`/sessions/${session.id}/class-profiles`, { format: profileFormat, content: profile, mode: profileMode, expected_revision: session.revision })
    if (isCurrent(scope) && profileGeneration.current === read) setProfileInput('', 'text')
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!text.trim()) { messageRef.current?.focus(); return }
    if (uploadError) { setError(uploadError); return }
    let scope = currentScope()
    if (scope.id !== sid) return
    setPending(true); setActivity('正在发送备课需求…'); setError('')
    try {
      let session = snapshot?.session
      if (sid && !session) throw new Error('工作区仍在读取，请稍后重试。')
      if (!sid) {
        const data = await api<{ session: Session }>('/sessions', { stage, grade, topic })
        if (!isCurrent(scope)) return
        session = data.session
        if (profileFile || profile.trim()) {
          await importProfile(session)
          if (!isCurrent(scope)) return
          session = (await api<Snapshot>(`/sessions/${session.id}`)).session
          if (!isCurrent(scope)) return
        }
        setSessions(old => [...old, data.session]); selectSession(session.id); scope = currentScope()
        setPending(true); setActivity('正在发送备课需求…')
      } else if (session && (profileFile || profile.trim())) {
        await importProfile(session)
        if (!isCurrent(scope)) return
        session = (await api<Snapshot>(`/sessions/${session.id}`)).session
        if (!isCurrent(scope)) return
      }
      if (!session) throw new Error('工作区仍在读取，请稍后重试。')
      await api(`/sessions/${session.id}/messages`, { content: text,
        expected_revision: session.revision, idempotency_key: crypto.randomUUID() })
      if (!isCurrent(scope)) return
      setText(''); setShowWorkspace(true); await refresh(session.id, scope.epoch)
    } catch (e) {
      if (isCurrent(scope)) {
        setError((e as Error).message)
        if (scope.id) { try { await refresh(scope.id, scope.epoch) } catch { /* 保留发送错误，稍后可刷新。 */ } }
      }
    }
    finally { if (isCurrent(scope)) setPending(false) }
  }

  async function action(path: string, body: unknown, method?: string, operation?: () => Promise<unknown>) {
    const scope = { id: sid, epoch: generation.current }, fileEpoch = fileGeneration.current
    if (!isCurrent(scope)) return false
    setPending(true); setError('')
    setActivity(path.endsWith('/verify') ? '正在执行真实代码测试…' : path.endsWith('/recovery') ? '正在对账恢复…' : path.endsWith('/delivery') || path.endsWith('/publish-draft') ? '正在生成文件Diff…' : path.endsWith('/decision') ? '正在处理文件审批…' : path.endsWith('/reviews') ? '正在保存审核结果…' : '正在保存修改…')
    try {
      if (operation) await operation()
      else await api(path, body, method)
      if (!isCurrent(scope)) return false
      if (scope.id) await refresh(scope.id, scope.epoch)
      if (!isCurrent(scope)) return false
      if (file && snapshot && fileGeneration.current === fileEpoch) {
        try {
          const value = await api<typeof file>(`/workspaces/${snapshot.session.workspace_id}/file?path=${encodeURIComponent(file.path)}`)
          if (isCurrent(scope) && fileGeneration.current === fileEpoch) setFile(value)
        } catch { if (isCurrent(scope) && fileGeneration.current === fileEpoch) setFile(undefined) }
      }
      return isCurrent(scope) && fileGeneration.current === fileEpoch
    } catch (e) {
      if (isCurrent(scope)) {
        setError((e as Error).message)
        if (scope.id) { try { await refresh(scope.id, scope.epoch) } catch { /* 保留原操作错误，刷新可重试。 */ } }
      }
      return false
    }
    finally { if (isCurrent(scope)) setPending(false) }
  }

  async function openRecovery(cid: string) {
    const scope = { id: sid, epoch: generation.current }
    setPending(true); setActivity('正在读取文件现状与回退Diff…'); setError(''); setRecovery(undefined)
    try {
      const data = await api<{ recovery: Recovery }>(`/sessions/${sid}/commits/${cid}/recovery`)
      if (isCurrent(scope)) setRecovery(data.recovery)
    } catch (e) { if (isCurrent(scope)) setError((e as Error).message) }
    finally { if (isCurrent(scope)) setPending(false) }
  }

  return <div className="app-shell">
    <a className="skip-link" href="#conversation">跳到备课对话</a>
    <aside className="sidebar" aria-label="备课会话">
      <div className="brand"><GraduationCap aria-hidden="true" size={25} /><span>耘耘AI助教</span></div>
      <button className="new-session" onClick={() => {
        selectSession(undefined)
      }}><Plus size={16} aria-hidden="true" />新建备课会话</button>
      {runtime?.mode === 'pc' && <button disabled={pending} onClick={() => {
        const scope = currentScope()
        setPending(true); void api<{workspace_name: string}>('/local-workspace/dialog', {}).then(r => {
          if (isCurrent(scope)) { selectSession(undefined); setRuntime({...runtime, workspace_name: r.workspace_name}) }
        }).catch(e => {if(isCurrent(scope)) setError(e.message)}).finally(() => {if(isCurrent(scope)) setPending(false)})
      }}><FolderOpen size={15}/>打开本地工作区</button>}
      <h2>最近会话</h2>
      <nav aria-label="历史会话">{sessions.length ? [...sessions].reverse().map(s =>
        <button className={sid === s.id ? 'session selected' : 'session'} key={s.id} aria-current={sid === s.id ? 'page' : undefined}
          onClick={() => { selectSession(s.id); setShowWorkspace(true) }}>
          <span>{s.context.topic || '备课会话'}</span><small>{s.context.grade} · {new Date(s.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}</small>
        </button>) : <p className="muted">开始后，会话会保存在这里。</p>}</nav>
      <p className="sidebar-note">{runtime?.mode === 'pc' ? '本机授权工作区' : '独立演示工作区'}<br />{snapshot?.workspace_name || runtime?.workspace_name}<br />{runtime?.runner === 'ISOLATED' ? '隔离代码执行可用' : '隔离执行器不可用，禁止交付代码'}</p>
    </aside>

    <main id="conversation" className="conversation">
      <header className="toolbar">
        <div><h1 className="page-title">教师备课工作台</h1><span className={runtime?.mock ? 'badge mock' : 'badge'}>{runtime?.mock ? 'MOCK_LLM · 离线演示' : runtime?.model || '连接中…'}</span></div>
        <button className="subtle" onClick={() => setShowWorkspace(v => !v)} aria-expanded={showWorkspace}><FolderOpen size={16} aria-hidden="true" />工作区</button>
      </header>
      <div className="notice">先验证代码，再逐项审核教学内容，最后确认文件差异并交付。</div>
      {runtime && !runtime.mock && !runtime.key_configured && <p className="alert" role="alert">未配置百炼密钥，请完成本地配置并重启服务。</p>}
      {error && <div className="alert" role="alert">{error}{!connected && <button onClick={() => void connect()}>重新连接</button>}</div>}
      {pending && <p className="notice" role="status" aria-live="polite">{activity || '正在处理，请稍候…'}</p>}
      <div className="chat-scroll">
        {!hasMessages && <section className="welcome"><GraduationCap size={34} aria-hidden="true" /><h2>从这节课的备课需求开始</h2><p>描述本班情况和教学目标，让每一段课堂代码都有验证依据。</p></section>}
        {messages.map((m, index) => <ChatMessage key={index} role={m.role} content={m.content} mock={runtime?.mock} />)}
        {run && <section className="execution" aria-label="执行过程">
          <div className="run-status" role="status">{unresolved && run.status === 'INTERRUPTED' ? '提交中断，须对账恢复' : statuses[run.status] || run.status}<span>思考 {run.steps} 次 · 操作 {run.tool_count} 次</span></div>
          {run.error && <p className="alert" role="alert">{run.error.message}<small>{run.error.code}</small></p>}
          {['INTERRUPTED', 'FAILED'].includes(run.status) && <button disabled={pending || unresolved} onClick={() => void action(`/sessions/${sid}/resume`, { expected_revision: snapshot!.session.revision })}><RefreshCw size={14} aria-hidden="true" />继续当前任务</button>}
          {['READY', 'RUNNING', 'WAITING_APPROVAL', 'INTERRUPTED', 'FAILED'].includes(run.status) && <button className="subtle" disabled={pending} onClick={() => void action(`/runs/${run.id}/cancel`, {})}><Square size={13} aria-hidden="true" />停止任务</button>}
          <details><summary>查看执行记录（{events.length}）</summary><ol className="events">{events.map(ev => <li key={ev.event_id}>
            <span>{eventNames[ev.type] || ev.type}{typeof ev.payload.name === 'string' ? ` · ${toolNames[ev.payload.name] || ev.payload.name}` : ''}</span>
            <time>{new Date(ev.timestamp).toLocaleTimeString('zh-CN')}</time>
            {ev.type === 'tool.failed' && <details><summary>失败详情</summary><pre>{JSON.stringify(ev.payload.result, null, 2)}</pre></details>}
          </li>)}</ol></details>
          {streamError && <p className="muted" role="status">进度连接已断开，正在重连。<button className="subtle" onClick={() => sid && void refresh(sid, renderScope.epoch).catch(e => { if(isCurrent(renderScope)) setError(e.message) })}>刷新状态</button></p>}
        </section>}
      </div>
      <form className={sid ? 'composer compact' : 'composer'} onSubmit={submit}>
        <details key={sid || 'new'} className="profile-input composer-settings" open={!sid}>
          <summary>
            <span className="context-summary" title={contextSummary}>{contextSummary}</span>
            {currentProfile && <span className="profile-count">{currentProfile.facts.length} 条班情观察</span>}
            {uploadError && <span className="failure">班情待修正</span>}
            <span className="settings-label">教学设置与班情</span><ChevronDown size={14} aria-hidden="true" />
          </summary>
          <div className="composer-settings-content">
            <fieldset disabled={!!sid || pending}><legend>教学上下文</legend><div className="context-fields">
              <label>学段<select name="stage" value={stage} onChange={e => {setStage(e.target.value); setGrade(e.target.value === '大学' ? '大一' : '初二')}}><option>初中</option><option>大学</option></select></label>
              <label>年级<input name="grade" autoComplete="off" value={grade} maxLength={30} onChange={e => setGrade(e.target.value)} /></label>
              <label>主题<input name="topic" autoComplete="off" value={topic} maxLength={100} onChange={e => setTopic(e.target.value)} /></label>
            </div></fieldset>
            <p className="muted">可上传或补充班情，也可直接写进下方需求；发送时会一并处理。请只提供汇总数据，不填姓名、学号。</p>
            {currentProfile && <div className="current-profile"><strong>当前已保存班情</strong><p>{currentProfile.class_size ? `班级共 ${currentProfile.class_size} 人；` : '班级人数未知；'}{currentProfile.facts.map(fact => fact.observation).join('；') || '暂无量化观察，保留未知'}</p>{!!currentProfile.prior_knowledge?.length && <p>已知先修：{currentProfile.prior_knowledge.join('、')}</p>}</div>}
            <div className="profile-templates"><a href="/api/class-profile-templates/csv" download>下载 CSV 示例</a><a href="/api/class-profile-templates/json" download>下载 JSON 示例</a><span>合成示例，可修改人数后上传；未提供的观察保持未知。</span></div>
            <fieldset className="profile-fields" disabled={blocked}>
            <label>手动导入方式<select value={profileMode} onChange={e => setProfileMode(e.target.value as 'replace' | 'supplement')}><option value="supplement">补充当前班情，保留已有观察</option><option value="replace">整体替换班情，用于更正资料</option></select></label>
            <p className="muted">{profileMode === 'supplement' ? '同类人数不一致时会提示核实，不覆盖、不累加。' : '将用本次资料整体替换当前班情；未包含的观察会变为未知。旧版本仍保留。'}</p>
            <p className="muted">需求里的明确班情按补充处理；更正人数时，请在这里填写资料并选择整体替换。</p>
            <div className="actions"><button type="button" disabled={blocked} onClick={() => setProfileInput('班级共40人，刚学完条件语句；5人未交、3人while死循环。', 'text')}>使用A班</button><button type="button" disabled={blocked} onClick={() => setProfileInput('type,count,class_size\nnot_submitted,0,40\ninfinite_loop,0,40\nboundary_error,8,40\n', 'csv')}>使用B班</button></div>
            <label>班情格式<select value={profileFormat} onChange={e => setProfileInput(profile, e.target.value)}><option value="text">文字</option><option value="json">JSON</option><option value="csv">CSV</option></select></label>
          <label>汇总班情（可选）<textarea aria-label="汇总班情" value={profile} placeholder="例如：全班40人，5人未交，3人while死循环，刚学完条件语句。也可直接写在备课需求中…" maxLength={20000} onChange={e => setProfileInput(e.target.value, profileFormat)} rows={2}/></label>
            <label>上传班情（JSON/CSV，1 MiB以内）<input ref={profileInputRef} type="file" name="class-profile-file" accept=".json,.csv" aria-invalid={!!uploadError} aria-describedby={uploadError ? 'upload-error' : undefined} disabled={blocked} onChange={e => {const f=e.target.files?.[0]; if(f) void readProfile(f)}}/></label>
            {uploadError && <p id="upload-error" className="failure" role="status">{uploadError}。请重新选择文件或编辑汇总班情。</p>}
            {sid && <button type="button" disabled={blocked || !snapshot || !!uploadError || (!profileFile && !profile.trim())} onClick={() => void action(`/sessions/${sid}/class-profiles`, undefined, undefined, () => importProfile(snapshot!.session))}>{profileMode === 'supplement' ? '保存班情补充' : '整体替换班情'}</button>}
            </fieldset>
          </div>
        </details>
        <label htmlFor="request">备课需求</label><textarea ref={messageRef} id="request" name="request" autoComplete="off" value={text} maxLength={12000} onChange={e => setText(e.target.value)}
          placeholder={sid ? '补充教学要求或明确班情，例如：另有8人出现边界错误，请加强边界练习…' : '全班40人，5人未交、3人while死循环，刚学完条件语句。请备一节45分钟《循环结构》，包含示例与分层练习并真实验证代码…'} rows={sid ? 1 : 3} />
        <div className="composer-footer"><small>{sid ? '会话已保存，可从历史继续' : '将创建独立的备课会话'}</small><button className="primary" type="submit" disabled={!connected || blocked}><ArrowUp size={16} aria-hidden="true" />{pending ? '处理中…' : '发送需求'}</button></div>
      </form>
    </main>

    {showWorkspace && <aside className="workspace" aria-label="工作区文件与草稿" aria-busy={pending || loadingFile}>
      <h2><FolderOpen size={17} aria-hidden="true" />{snapshot?.workspace_name || '备课工作区'}</h2>
      <div className="workspace-tabs" aria-label="工作区视图">{['备课产物','文件与Diff'].map(name => <button aria-pressed={panel===name} key={name} onClick={() => setPanel(name)}>{name}</button>)}</div>
      {!sid || !snapshot ? <p className="muted">{sid ? '正在读取工作区…' : '发起任务后查看文件与修改草稿。'}</p> : <>
        {panel === '备课产物' ? <EducationWorkspace key={sid} snapshot={snapshot!} pending={blocked} act={action} onOpenFiles={() => setPanel('文件与Diff')} fail={message => { if(isCurrent(renderScope)) setError(message) }}/> : <>
        <WorkspaceFiles files={files} selected={file?.path} disabled={loadingFile} onSelect={path => {
          const scope = currentScope(), fileEpoch = ++fileGeneration.current
          setLoadingFile(true); setFile(undefined); setFileEdit(undefined)
          void api<{ path: string; content: string; hash: string | null }>(`/workspaces/${snapshot!.session.workspace_id}/file?path=${encodeURIComponent(path)}`)
            .then(value => { if (isCurrent(scope) && fileGeneration.current === fileEpoch) {setFile(value);setFileEdit(undefined)} }).catch(e => {if(isCurrent(scope) && fileGeneration.current === fileEpoch) setError(e.message)}).finally(() => {if(isCurrent(scope) && fileGeneration.current === fileEpoch) setLoadingFile(false)})
        }} />
        {loadingFile && <p className="muted" role="status">正在读取文件…</p>}
        {file && <section className="file-preview"><h3>{file.path}</h3><pre>{file.content}</pre><div className="actions"><button disabled={blocked} onClick={() => setFileEdit(file.content)}>修改草稿</button><button disabled={blocked} onClick={() => void action(`/sessions/${sid}/drafts`,{path:file.path,content:'',base_hash:file.hash,operation:'delete',expected_revision:snapshot!.session.revision})}>提出删除草稿</button></div></section>}
        <label>新文件相对路径<input value={newPath} placeholder="例如：notes/lesson.md" onChange={e => setNewPath(e.target.value)}/></label><button disabled={blocked || !newPath.trim()} onClick={() => {fileGeneration.current += 1; setFile({path:newPath,content:'',hash:null});setFileEdit('')}}>新建文件草稿</button>
        {fileEdit !== undefined && file && <section className="item-editor"><label>文件内容<textarea spellCheck={false} name="file-content" rows={8} value={fileEdit} onChange={e => setFileEdit(e.target.value)}/></label><button disabled={blocked} onClick={() => void action(`/sessions/${sid}/drafts`,{path:file.path,content:fileEdit,base_hash:file.hash,operation:'write',expected_revision:snapshot!.session.revision}).then(ok => {if(ok)setFileEdit(undefined)})}>保存草稿，待审批</button><button onClick={() => setFileEdit(undefined)}>取消编辑</button></section>}
        <h3>修改草稿</h3>{!snapshot?.drafts.length && <p className="muted">助教提出的修改会显示在这里。</p>}
        {snapshot?.drafts.filter(d => snapshot.drafts.filter(v => v.path === d.path).at(-1)?.id === d.id).map(d => <section className="draft" key={d.id}><strong>{d.path}</strong><p className="muted">版本 {d.revision} · {d.operation === 'delete' ? '待删除' : '草稿'} · {d.operation === 'delete' ? '按原文件Hash审批' : verificationLabels[d.verification_status] || '未测试'}{d.mock ? ' · MOCK_LLM' : ''}</p><details><summary>查看文件差异</summary><DiffView diff={d.diff} filePath={d.path} fromLabel="正式文件" toLabel={d.operation === 'delete' ? '删除后' : '当前草稿'} /></details>
          {d.repair_diff && <details><summary>与上一版代码对比</summary><DiffView diff={d.repair_diff} filePath={d.path} fromLabel="上一版代码" toLabel="当前草稿" /></details>}
          {d.operation !== 'delete' && /\.py$/i.test(d.path) && <VerificationDiagnostic status={d.verification_status} report={snapshot.verification_reports.filter(r => r.draft_id === d.id).at(-1)} changed={!!d.repair_diff} />}
          {snapshot.verification_reports?.filter(r => r.draft_id === d.id).map(r => <Report report={r} key={r.id} />)}
          <button disabled={blocked} onClick={() => void action(`/sessions/${sid}/publish-draft`, {draft_id:d.id,expected_revision:snapshot.session.revision})}>审核此文件变更</button>
        </section>)}
        </>}
        <div id="pending-file-approvals" tabIndex={-1}>{snapshot?.approvals.filter(a => a.status === 'PENDING').map(a => <section className="approval" key={a.id} aria-label="正式文件审批"><h3>确认正式文件变更</h3><p>接受将写入当前工作区；拒绝保持文件不变。</p>
          {a.entries ? a.entries.map(e => <details open key={e.path}><summary>{e.operation === 'delete' ? '删除' : e.base_hash ? '覆盖' : '新建'} · {e.path}</summary><DiffView diff={e.diff} filePath={e.path} fromLabel="变更前" toLabel={e.operation === 'delete' ? '删除后' : '待写入内容'} /><small>原Hash：{e.base_hash || '不存在'}<br/>新Hash：{e.content_hash || '删除'}{e.content_mode != null && <><br/>文件权限：{e.before_mode?.toString(8) || '新建'} → {e.content_mode.toString(8)}</>}</small></details>) : <DiffView diff={snapshot.drafts.find(d => d.id === a.draft_id)?.diff || ''} fromLabel="正式文件" toLabel="待写入内容" />}
          <div className="actions"><button className="primary" disabled={pending || unresolved} onClick={() => void action(`/approvals/${a.id}/decision`,{decision:'approve',expected_revision:snapshot.session.revision})}>确认接受并写入</button><button disabled={pending} onClick={() => void action(`/approvals/${a.id}/decision`,{decision:'reject',expected_revision:snapshot.session.revision})}>拒绝本次变更</button></div></section>)}</div>
        {!!snapshot?.commits.length && <details open={!!unresolved}><summary>正式文件历史与恢复</summary>{snapshot.commits.map(c => <section className="history-item" key={c.id}><p>{c.status} · {new Date(c.created_at).toLocaleString('zh-CN')}</p><small>{c.applied.join('、')}</small>{c.status === 'INTERRUPTED' ? <button disabled={pending} onClick={() => void openRecovery(c.id)}>对账恢复</button> : c.status === 'COMMITTED' && <button disabled={blocked} onClick={() => void action(`/sessions/${sid}/commits/${c.id}/restore-draft`,{expected_revision:snapshot.session.revision})}>创建回退Diff</button>}</section>)}</details>}
        {unresolved && <p className="alert" role="alert">正式写入中断。请先对账恢复，再继续任务或提交新变更。</p>}
        {recovery && snapshot.commits.some(c => c.id === recovery.commit_id && c.status === 'INTERRUPTED') && <section className="approval" aria-label="中断提交对账"><h3>核对磁盘现状并恢复</h3><p>按当前Hash确认处理范围；未知外部修改不会被自动覆盖。</p>
          {recovery.entries.map(e => <details open key={e.path}><summary>{e.path} · {({BEFORE:'原文件未变',AFTER:'已写入审批版本',UNCHANGED:'内容未变',CONFLICT:'外部变更，须人工核对'})[e.state]}</summary><DiffView diff={e.rollback_diff || ''} filePath={e.path} fromLabel="当前文件" toLabel="回退后内容" emptyMessage="无需回退内容" /><small>当前Hash：{e.current_hash || '不存在'}<br/>原Hash：{e.before_hash || '不存在'}<br/>提交目标Hash：{e.after_hash || '删除'}{e.current_mode != null && <><br/>当前权限：{e.current_mode.toString(8)} · 原权限：{e.before_mode?.toString(8) || '不存在'}</>}</small>{e.error && <p className="alert">{e.error.message}</p>}</details>)}
          <div className="actions">{(['accept','reject','rollback'] as const).map(decision => <button key={decision} disabled={pending || !recovery[`can_${decision}`]} onClick={() => void action(`/sessions/${sid}/commits/${recovery.commit_id}/recovery`,{decision,snapshot_hash:recovery.snapshot_hash,expected_revision:snapshot.session.revision}).then(ok => {if(ok)setRecovery(undefined)})}>{({accept:'确认已完整写入',reject:'确认未写入并拒绝',rollback:'确认回退已写入文件并拒绝'})[decision]}</button>)}<button disabled={pending} onClick={() => void openRecovery(recovery.commit_id)}>重新对账</button></div>
        </section>}
        {!!snapshot?.usage.length && <p className="muted">已知费用估算 ¥{snapshot.usage.reduce((total, u) => total + (u.status === 'RESERVED_UNKNOWN' ? 0 : (u.cny ?? 0)), 0).toFixed(4)}{snapshot.usage.some(u => u.cny === null || ['USAGE_UNKNOWN', 'RESERVED_UNKNOWN'].includes(u.status)) ? '（部分请求用量或费用未知）' : ''}</p>}
      </>}
    </aside>}
  </div>
}
