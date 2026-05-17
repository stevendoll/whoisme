import { useState, useEffect, useRef } from 'react'
import type { Document, DocVersion } from '../lib/types'
import { getVersions, createVersion, publishVersion, createDocument } from '../lib/api'

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

interface Props {
  doc: Document
  onClose: () => void
  onSaved: (updated: Document) => void
}

export default function DocEditorPanel({ doc, onClose, onSaved }: Props) {
  const [versions, setVersions] = useState<DocVersion[]>([])
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null)
  const [content, setContent] = useState('')
  const [saving, setSaving] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [error, setError] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Initial content: draft version if has_draft, else published content
  const initialContent = doc.hasDraft
    ? '' // will be set once versions load
    : (doc.content ?? '')

  useEffect(() => {
    setContent(initialContent)
    setSelectedVersionId(null)
    setError('')

    if (doc.documentId) {
      getVersions(doc.documentId).then(res => {
        setVersions(res.versions)
        // If has_draft, the first version (newest) is the draft
        if (doc.hasDraft && res.versions.length > 0) {
          setContent(res.versions[0].content)
          setSelectedVersionId(res.versions[0].versionId)
        } else if (res.versions.length > 0) {
          setSelectedVersionId(res.versions[0].versionId)
        }
      }).catch(() => { /* non-fatal */ })
    }
  }, [doc.documentId]) // eslint-disable-line react-hooks/exhaustive-deps

  const latestVersion = versions[0]
  const latestIsUnpublished = latestVersion && !latestVersion.isPublished
  const selectedVersion = versions.find(v => v.versionId === selectedVersionId)
  const isViewingOldVersion = selectedVersionId && selectedVersion?.isPublished && selectedVersionId !== latestVersion?.versionId

  const handleVersionSelect = (versionId: string) => {
    const v = versions.find(v => v.versionId === versionId)
    if (v) {
      setSelectedVersionId(versionId)
      setContent(v.content)
    }
  }

  const handleSaveDraft = async () => {
    setSaving(true)
    setError('')
    try {
      if (!doc.documentId) {
        // New document — create it
        const created = await createDocument(doc.title, content)
        onSaved(created)
        onClose()
        return
      }
      await createVersion(doc.documentId, content)
      // Refresh versions
      const res = await getVersions(doc.documentId)
      setVersions(res.versions)
      setSelectedVersionId(res.versions[0]?.versionId ?? null)
      onSaved({ ...doc, hasDraft: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handlePublish = async () => {
    if (!doc.documentId) return
    const versionId = latestIsUnpublished ? latestVersion.versionId : selectedVersionId
    if (!versionId) return
    setPublishing(true)
    setError('')
    try {
      const updated = await publishVersion(doc.documentId, versionId)
      onSaved(updated)
      // Refresh versions
      const res = await getVersions(doc.documentId)
      setVersions(res.versions)
      setSelectedVersionId(res.versions[0]?.versionId ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Publish failed')
    } finally {
      setPublishing(false)
    }
  }

  const canSaveDraft = !latestIsUnpublished && content.trim().length > 0 && !isViewingOldVersion
  const canPublish = (latestIsUnpublished || (selectedVersion && !selectedVersion.isPublished)) && content.trim().length > 0

  return (
    <>
      <div className="docs-editor-backdrop" onClick={onClose} />
      <div className="docs-editor-panel">
        <div className="docs-editor-header">
          <h2 className="docs-editor-title">{SECTION_LABELS[doc.title] ?? doc.title}</h2>
          <button className="docs-editor-close" onClick={onClose}>✕</button>
        </div>

        {versions.length > 0 && (
          <div className="docs-version-row">
            <label className="docs-version-label">Version</label>
            <select
              className="docs-version-select"
              value={selectedVersionId ?? ''}
              onChange={e => handleVersionSelect(e.target.value)}
            >
              {versions.map((v, i) => (
                <option key={v.versionId} value={v.versionId}>
                  {i === 0 && !v.isPublished ? 'Draft — ' : ''}{new Date(v.createdAt).toLocaleString()}
                  {v.isPublished ? ' (published)' : ''}
                </option>
              ))}
            </select>
          </div>
        )}

        <textarea
          ref={textareaRef}
          className="docs-editor-textarea"
          value={content}
          onChange={e => setContent(e.target.value)}
          placeholder="Write markdown here…"
          readOnly={!!isViewingOldVersion}
        />

        {error && <p className="interview-error" style={{ margin: '0 16px' }}>{error}</p>}

        <div className="docs-editor-footer">
          <button className="btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className="btn-ghost"
            onClick={handleSaveDraft}
            disabled={!canSaveDraft || saving}
          >
            {saving ? 'Saving…' : 'Save Draft'}
          </button>
          <button
            className="btn-primary"
            onClick={handlePublish}
            disabled={!canPublish || publishing}
          >
            {publishing ? 'Publishing…' : 'Publish'}
          </button>
        </div>
      </div>
    </>
  )
}
