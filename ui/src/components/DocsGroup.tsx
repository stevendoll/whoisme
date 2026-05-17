import { useState } from 'react'
import type { Document } from '../lib/types'
import DocsDocRow from './DocsDocRow'

interface Props {
  label: string
  sections: string[]
  docsByTitle: Record<string, Document>
  onEdit: (doc: Document) => void
  onToggleVisibility: (section: string, current: string) => void
}

export default function DocsGroup({ label, sections, docsByTitle, onEdit, onToggleVisibility }: Props) {
  const [open, setOpen] = useState(true)

  return (
    <div className="docs-group">
      <button className="docs-group-header" onClick={() => setOpen(o => !o)}>
        <span>{label}</span>
        <span className={`docs-chevron${open ? ' docs-chevron--open' : ''}`}>›</span>
      </button>
      {open && (
        <div className="docs-group-content">
          {sections.map(section => (
            <DocsDocRow
              key={section}
              section={section}
              document={docsByTitle[section]}
              onEdit={onEdit}
              onToggleVisibility={onToggleVisibility}
            />
          ))}
        </div>
      )}
    </div>
  )
}
