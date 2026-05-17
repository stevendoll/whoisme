import type { Document } from '../lib/types'

const SECTION_LABELS: Record<string, string> = {
  'identity':                    'Identity',
  'role-and-responsibilities':   'Role & Responsibilities',
  'current-projects':            'Current Projects',
  'team-and-relationships':      'Team & Relationships',
  'tools-and-systems':           'Tools & Systems',
  'communication-style':         'Communication Style',
  'goals-and-priorities':        'Goals & Priorities',
  'preferences-and-constraints': 'Preferences & Constraints',
  'domain-knowledge':            'Domain Knowledge',
  'decision-log':                'Decision Log',
  'standup':                     'Standup',
  'networking':                  'Networking',
  'ideas':                       'Ideas',
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

interface Props {
  section: string
  document: Document | undefined
  onEdit: (doc: Document) => void
  onToggleVisibility: (section: string, current: string) => void
}

export default function DocsDocRow({ section, document: doc, onEdit, onToggleVisibility }: Props) {
  const label = SECTION_LABELS[section] ?? section
  const vis = doc?.visibility ?? 'public'

  return (
    <div className="docs-doc-row">
      <div className="docs-doc-info">
        <span className="docs-doc-title">{label}</span>
        {doc?.hasDraft && <span className="docs-draft-badge">draft</span>}
      </div>
      <div className="docs-doc-meta">
        <span className="docs-doc-date">{doc ? fmtDate(doc.publishedAt) : '—'}</span>
        {doc && (
          <button
            className={`profile-vis-toggle profile-vis-toggle--${vis}`}
            onClick={() => onToggleVisibility(section, vis)}
            title={vis === 'private' ? 'Private: requires bearer token' : 'Public: visible to anyone'}
          >
            {vis}
          </button>
        )}
        <button
          className="btn-ghost docs-edit-btn"
          onClick={() => doc && onEdit(doc)}
          disabled={!doc}
        >
          {doc ? 'Edit' : 'No draft'}
        </button>
      </div>
    </div>
  )
}
