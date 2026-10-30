import { useEffect, useRef } from 'react'
import type { AgentEvent } from './api'

export default function ExecutionLog({ events, labels, tools }: {
  events: AgentEvent[]; labels: Record<string, string>; tools: Record<string, string>
}) {
  const detailsRef = useRef<HTMLDetailsElement>(null)
  const summaryRef = useRef<HTMLElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const container = detailsRef.current?.closest<HTMLElement>('.chat-scroll')
    const summary = summaryRef.current, list = listRef.current
    if (!container || !summary || !list) return
    const resize = () => {
      const style = getComputedStyle(container)
      const padding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom)
      const available = container.clientHeight - padding - summary.offsetHeight - 12
      list.style.maxHeight = `${Math.max(0, Math.min(300, available))}px`
    }
    resize()
    const observer = new ResizeObserver(resize)
    observer.observe(container); observer.observe(summary)
    return () => observer.disconnect()
  }, [])
  return <details className="execution-log" ref={detailsRef} onToggle={event => {
    if (event.target !== event.currentTarget || !event.currentTarget.open) return
    requestAnimationFrame(() => {
      if (detailsRef.current?.open) detailsRef.current.scrollIntoView({ block: 'nearest' })
    })
  }}>
    <summary ref={summaryRef}>查看执行记录（{events.length}）</summary>
    <div className="execution-log-scroll" ref={listRef} role="region" aria-label="执行记录列表" tabIndex={0}>
      {events.length ? <ol className="events">{events.map(event => <li key={event.event_id}>
        <span>{labels[event.type] || event.type}{typeof event.payload.name === 'string' ? ` · ${tools[event.payload.name] || event.payload.name}` : ''}</span>
        <time dateTime={event.timestamp}>{new Date(event.timestamp).toLocaleTimeString('zh-CN')}</time>
        {event.type === 'tool.failed' && <details><summary>失败详情</summary><pre>{JSON.stringify(event.payload.result, null, 2)}</pre></details>}
      </li>)}</ol> : <p className="muted">暂无执行记录。</p>}
    </div>
  </details>
}
