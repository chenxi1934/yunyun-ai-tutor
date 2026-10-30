export interface Session {
  id: string; workspace_id: string; revision: number; mock: boolean; created_at: string
  context: { stage: string; grade: string; topic: string }
}
export interface Run { id: string; status: string; steps: number; tool_count: number; error: null | { code: string; message: string } }
export interface Draft { id: string; path: string; revision: number; diff: string; repair_diff?: string | null; verification_status: string; operation: string; mock: boolean; content: string; base_hash: string | null; status: string }
export interface VerificationReport {
  id: string; draft_id: string; status: string; effective_status: string; code_hash: string; fingerprint: string
  cases: { id: string; input: string; expected: string; actual: string; stdout: string; stderr: string
    exit_code: number | null; duration_ms: number; status: string; error: string | null }[]
}
export interface Approval { id: string; draft_id: string | null; status: string; entries?: Entry[]; snapshot_hash?: string; commit_id?: string; lesson_id?: string; lesson_revision?: number }
export interface AgentEvent { event_id: number; type: string; timestamp: string; payload: Record<string, unknown> }
export interface Snapshot {
  session: Session; messages: { role: string; content: string | null }[]; runs: Run[]
  drafts: Draft[]; verification_reports: VerificationReport[]; approvals: Approval[]; event_cursor: number
  lessons: Lesson[]; commits: Commit[]; profiles: {profile: Lesson["profile"]}[]; workspace_name: string
  usage: { cny: number | null; status: string }[]
}
export interface Runtime { mode: string; provider: string; model: string; mock: boolean; key_configured: boolean; runner: string; workspace_name?: string }

const fragment = new URLSearchParams(location.hash.slice(1))
if (fragment.has('token')) {
  sessionStorage.setItem('yunyun_local_token', fragment.get('token')!)
  history.replaceState(null, '', location.pathname + location.search)
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const token = sessionStorage.getItem('yunyun_local_token')
  const response = await fetch('/api' + path, {
    ...init, credentials: 'same-origin',
    headers: { ...init.headers, ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  })
  const data = await response.json()
  if (!response.ok) throw new Error(data.error?.message || `请求失败（${response.status}）`)
  return data as T
}

export function api<T>(path: string, body?: unknown, method?: string): Promise<T> {
  return request(path, { method: method || (body === undefined ? 'GET' : 'POST'),
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body) })
}

export function uploadProfile(sid: string, file: File, format: string, revision: number, mode: 'replace' | 'supplement' = 'replace'): Promise<unknown> {
  const query = new URLSearchParams({ format, expected_revision: String(revision), mode })
  return request(`/sessions/${sid}/class-profiles/upload?${query}`, {
    method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: file,
  })
}

export interface Recovery {
  commit_id: string; snapshot_hash: string; can_accept: boolean; can_reject: boolean; can_rollback: boolean
  entries: { path: string; state: 'BEFORE' | 'AFTER' | 'UNCHANGED' | 'CONFLICT'; rollback_diff?: string
    current_hash?: string | null; current_mode?: number | null; before_hash?: string | null; after_hash?: string | null
    before_mode?: number | null; after_mode?: number | null; error?: { message: string } }[]
}

export interface TeachingItem {
  id: string; title: string; criterion?: string; minutes?: number; activity?: string
  kind?: string; content?: string; teacher_actions?: string; student_actions?: string; assessment?: string
  task_id?: string; knowledge_points?: string[]; explanation?: string; code?: string
  level?: string; prompt?: string; scaffolding?: string; scoring?: { criterion: string; points: number }[]
  basis?: string; evidence_ids?: string[]; trigger?: string; cause?: string
  teaching_intervention?: string; exercise_ids?: string[]; cause_status?: string
}
export interface Lesson {
  lesson_id: string; revision: number; content_hash: string; code_status: string
  candidate_ready: boolean; delivery_ready: boolean; profile_stale: boolean; curriculum_risks: (string | { item_id: string; reason: string })[]
  plan: { stage: string; topic: string; prerequisites: string[]; duration_minutes: number
    overview?: TeachingItem[]; goals: TeachingItem[]; segments: TeachingItem[]; examples: TeachingItem[]; exercises: TeachingItem[]; misconceptions: TeachingItem[] }
  items: Record<string, { review_status: string; review_note?: string | null; reviewed_at?: string | null; current_pass?: boolean; verification_status?: string; draft_id?: string }>
  profile: { class_size?: number | null; prior_knowledge?: string[]; revision?: number
    facts: { id: string; observation: string; count: number; source_ref: string; source_hash?: string | null }[]; unknowns: string[]
    sources?: { format: string; origin: string; source_hash: string }[] }
  strategies: { id: string; action: string; target: string; evidence_ids: string[] }[]
}
export interface Commit { id: string; status: string; created_at: string; applied: string[]; lesson_id?: string; lesson_revision?: number }
export interface Entry { path: string; operation: string; base_hash: string | null; content_hash: string | null; diff: string; before_mode?: number | null; content_mode?: number | null }

export async function download(path: string, name: string) {
  const response = await fetch('/api' + path, { credentials: 'same-origin' })
  if (!response.ok) { const data = await response.json(); throw new Error(data.error?.message || '下载失败') }
  const href = URL.createObjectURL(await response.blob())
  const link = document.createElement('a'); link.href = href; link.download = name; link.click()
  setTimeout(() => URL.revokeObjectURL(href), 1000)
}
