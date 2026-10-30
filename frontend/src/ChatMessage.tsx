import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function ChatMessage({ role, content, mock }: { role: string; content: string | null; mock?: boolean }) {
  const teacher = role === 'user'
  return <article className={`message ${teacher ? 'teacher' : 'assistant'}`}>
    <h2>{teacher ? '我' : '耘耘AI助教'}{mock && !teacher ? ' · MOCK_LLM' : ''}</h2>
    {teacher ? <p>{content}</p> : <div className="markdown-body">
      <Markdown remarkPlugins={[remarkGfm]} components={{
        h1: 'h3', h2: 'h3', h3: 'h4', h4: 'h5', h5: 'h6', h6: 'h6',
        a: ({ href, title, children }) => href
          ? <a href={href} title={title} target="_blank" rel="noopener noreferrer">{children}</a>
          : <span>{children}</span>,
        pre: ({ children }) => <pre tabIndex={0} aria-label="代码块">{children}</pre>,
        table: ({ children }) => <div className="markdown-table" role="region" aria-label="表格，可横向滚动" tabIndex={0}>
          <table>{children}</table>
        </div>,
      }}>{content || ''}</Markdown>
    </div>}
  </article>
}
