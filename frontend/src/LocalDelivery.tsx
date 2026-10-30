import { useEffect, useState } from 'react'
import { BookOpen, FolderOpen } from 'lucide-react'
import { api } from './api'

type Location = { directory: string; entry: string; relative_directory: string }

export default function LocalDelivery({ base, busy }: { base: string; busy: boolean }) {
  const [location, setLocation] = useState<Location>()
  const [error, setError] = useState('')
  const [opening, setOpening] = useState<'read' | 'folder'>()
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let cancelled = false
    setLocation(undefined); setError('')
    if (!busy) void api<Location>(base + '/local-package').then(value => {
      if (!cancelled) setLocation(value)
    }).catch(e => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [base, busy, retry])
  async function open(target: 'read' | 'folder') {
    if (busy || opening || !location) return
    setOpening(target); setError('')
    try { await api(base + '/local-package/open', { target }) }
    catch (e) { setError((e as Error).message) }
    finally { setOpening(undefined) }
  }
  return <aside className="delivery-guidance" aria-label="本机教案保存位置">
    <strong>教案已保存到本地工作区</strong>
    {location ? <>
      <p className="saved-directory">{location.directory}</p>
      <div className="actions"><button className="primary" disabled={busy || !!opening} onClick={() => void open('read')}><BookOpen size={14} aria-hidden="true" />{opening === 'read' ? '正在打开…' : '开始阅读'}</button>
        <button disabled={busy || !!opening} onClick={() => void open('folder')}><FolderOpen size={14} aria-hidden="true" />{opening === 'folder' ? '正在打开…' : '打开文件夹'}</button></div>
      <p>无需再次下载或选择目录。需要转发时，可另行下载 ZIP。</p>
    </> : !error && <p role="status">{busy ? '操作结束后显示保存位置。' : '正在核对已保存的教案…'}</p>}
    {error && <p role="alert">{error} <button className="subtle" disabled={busy || !!opening} onClick={() => setRetry(value => value + 1)}>重新核对</button></p>}
  </aside>
}
