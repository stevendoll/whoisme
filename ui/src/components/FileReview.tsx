import { useState } from 'react'
import { approveFile, submitFeedback } from '../lib/api'

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
  const [feedbackFile, setFeedbackFile] = useState<string | null>(null)
  const [feedbackText, setFeedbackText] = useState('')
  const [loading, setLoading] = useState<string | null>(null)
  const approvedSet = new Set(approvedFiles)

  const handleApprove = async (file: string) => {
    setLoading(file)
    try {
      await approveFile(sessionId, file)
      onApprove(file)
    } finally {
      setLoading(null)
    }
  }

  const handleFeedbackSubmit = async (file: string) => {
    if (!feedbackText.trim()) return
    setLoading(file)
    try {
      const result = await submitFeedback(sessionId, file, feedbackText)
      onDraftUpdate(file, result.draft)
      setFeedbackFile(null)
      setFeedbackText('')
    } finally {
      setLoading(null)
    }
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
        const showFeedback = feedbackFile === file

        return (
          <div key={file} className={`file-review-item ${isApproved ? 'is-approved' : ''}`}>
            <div className="file-review-header">
              <h3 className="file-review-title">
                {SECTION_LABELS[file] ?? file}
                {isApproved && <span className="file-review-approved-badge">✓ approved</span>}
              </h3>
              {!isApproved && (
                <div className="file-review-actions">
                  <button
                    onClick={() => { setFeedbackFile(showFeedback ? null : file); setFeedbackText('') }}
                    disabled={isLoading}
                    className="btn-ghost"
                  >
                    {showFeedback ? 'Cancel' : 'Give feedback'}
                  </button>
                  <button
                    onClick={() => handleApprove(file)}
                    disabled={isLoading}
                    className="btn-primary"
                  >
                    {isLoading ? 'Saving...' : 'Approve'}
                  </button>
                </div>
              )}
            </div>

            <pre className="file-review-draft">{draftFiles[file]}</pre>

            {showFeedback && (
              <div className="file-review-feedback">
                <textarea
                  value={feedbackText}
                  onChange={e => setFeedbackText(e.target.value)}
                  placeholder="What doesn't sound right? What's missing?"
                  rows={3}
                  className="file-review-feedback-input"
                  autoFocus
                />
                <button
                  onClick={() => handleFeedbackSubmit(file)}
                  disabled={isLoading || !feedbackText.trim()}
                  className="btn-primary"
                >
                  {isLoading ? 'Revising...' : 'Revise draft'}
                </button>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
