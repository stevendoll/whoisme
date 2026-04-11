import { useState } from 'react'
import { approveFile } from '../lib/api'

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
}

interface FileReviewProps {
  sessionId: string
  draftFiles: Record<string, string>
  approvedFiles: string[]
  onApprove: (file: string) => void
  onDraftUpdate: (file: string, draft: string) => void
}

export default function FileReview({ sessionId, draftFiles, approvedFiles, onApprove, onDraftUpdate }: FileReviewProps) {
  const [editedTexts, setEditedTexts] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState<string | null>(null)
  const approvedSet = new Set(approvedFiles)

  const getText = (file: string) => editedTexts[file] ?? draftFiles[file] ?? ''

  const handleEdit = (file: string, value: string) => {
    setEditedTexts(prev => ({ ...prev, [file]: value }))
    onDraftUpdate(file, value)
  }

  const handleApprove = async (file: string) => {
    setLoading(file)
    try {
      const text = getText(file)
      await approveFile(sessionId, file, text)
      onApprove(file)
    } finally {
      setLoading(null)
    }
  }

  const handleDownload = (file: string) => {
    const text = getText(file)
    const blob = new Blob([text], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${file}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const sections = Object.keys(draftFiles)

  if (sections.length === 0) {
    return <p className="file-review-empty">No drafts generated yet.</p>
  }

  return (
    <div className="file-review">
      {sections.map(file => {
        const isApproved = approvedSet.has(file)
        const isLoading = loading === file

        return (
          <div key={file} className={`file-review-item ${isApproved ? 'is-approved' : ''}`}>
            <div className="file-review-header">
              <h3 className="file-review-title">
                {SECTION_LABELS[file] ?? file}
                {isApproved && <span className="file-review-approved-badge">approved</span>}
              </h3>
              <div className="file-review-actions">
                <button
                  onClick={() => handleDownload(file)}
                  className="btn-ghost"
                  title="Download as .md"
                >
                  Download
                </button>
                {!isApproved && (
                  <button
                    onClick={() => handleApprove(file)}
                    disabled={isLoading}
                    className="btn-primary"
                  >
                    {isLoading ? 'Saving...' : 'Approve'}
                  </button>
                )}
              </div>
            </div>

            <textarea
              className="file-review-edit"
              value={getText(file)}
              onChange={e => handleEdit(file, e.target.value)}
              readOnly={isApproved}
              rows={12}
            />
          </div>
        )
      })}
    </div>
  )
}
