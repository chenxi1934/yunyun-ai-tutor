import { FileText } from 'lucide-react'

export default function WorkspaceFiles({ files, selected, disabled, onSelect }: {
  files: { path: string }[]; selected?: string; disabled: boolean; onSelect: (path: string) => void
}) {
  return <details className="workspace-files" open>
    <summary>文件（{files.length}）<span className="muted">展开 / 收起</span></summary>
    <div className="file-list-scroll" role="region" aria-label="工作区文件列表" tabIndex={0}>
      <ul className="file-list">{files.map(file => <li key={file.path}>
        <button type="button" disabled={disabled} aria-current={selected === file.path ? 'true' : undefined} onClick={() => onSelect(file.path)}>
          <FileText size={14} aria-hidden="true" /><span>{file.path}</span>
        </button>
      </li>)}</ul>
      {!files.length && <p className="muted">工作区为空，可以请助教提出新文件草稿。</p>}
    </div>
  </details>
}
