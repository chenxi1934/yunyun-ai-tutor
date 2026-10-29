export interface Session {
  id: string; workspace_id: string; revision: number; mock: boolean; created_at: string
  context: { stage: string; grade: string; topic: string }
}
export interface Run { id: string; status: string; steps: number; tool_count: number; error: null | { code: string; message: string } }
export interface Draft { id: string; path: string; revision: number; diff: string; repair_diff?: string | null; verification_status: string; operation: string; mock: boolean }
export interface VerificationReport {
  id: string; draft_id: string; status: string; effective_status: string; code_hash: string; fingerprint: string
  cases: { id: string; input: string; expected: string; actual: string; stdout: string; stderr: string
    exit_code: number | null; duration_ms: number; status: string; error: string | null }[]
}
export interface Approval { id: string; draft_id: string; status: string }
export interface AgentEvent { event_id: number; type: string; timestamp: string; payload: Record<string, unknown> }
export interface Snapshot {
  session: Session; messages: { role: string; content: string | null }[]; runs: Run[]
  drafts: Draft[]; verification_reports: VerificationReport[]; approvals: Approval[]; event_cursor: number
  usage: { cny: number; status: string }[]
}
export interface Runtime { mode: string; provider: string; model: string; mock: boolean; key_configured: boolean; runner: string }

const fragment = new URLSearchParams(location.hash.slice(1))
if (fragment.has('token')) {
  sessionStorage.setItem('yunyun_local_token', fragment.get('token')!)
  history.replaceState(null, '', location.pathname + location.search)
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const token = sessionStorage.getItem('yunyun_local_token')
  const response = await fetch('/api' + path, {
    method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin',
    headers: { ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await response.json()
  if (!response.ok) throw new Error(data.error?.message || `请求失败（${response.status}）`)
  return data as T
}
