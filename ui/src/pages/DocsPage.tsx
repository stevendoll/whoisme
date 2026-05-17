import { useState, useEffect } from 'react'
import { getMe, getDocuments, getMyFiles, updateVisibility } from '../lib/api'
import type { Document, UserProfile } from '../lib/types'
import AccountMenu from '../components/AccountMenu'
import DocsGroup from '../components/DocsGroup'
import DocEditorPanel from '../components/DocEditorPanel'

const IA_GROUPS: Record<string, string[]> = {
  'Profile': [
    'identity', 'role-and-responsibilities', 'current-projects',
    'team-and-relationships', 'tools-and-systems', 'communication-style',
    'goals-and-priorities', 'preferences-and-constraints',
    'domain-knowledge', 'decision-log',
  ],
  'Productivity': ['standup', 'networking'],
  'Create': ['ideas'],
}

export default function DocsPage() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [documents, setDocuments] = useState<Document[]>([])
  const [approvedFiles, setApprovedFiles] = useState<Record<string, string>>({})
  const [editingDoc, setEditingDoc] = useState<Document | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('whoisme_user_token')
    if (!token) {
      history.replaceState(null, '', '#/interview')
      window.dispatchEvent(new HashChangeEvent('hashchange'))
      return
    }

    Promise.all([getMe(), getDocuments(), getMyFiles()])
      .then(([me, docsRes, filesRes]) => {
        if (!me.published) {
          history.replaceState(null, '', '#/profile')
          window.dispatchEvent(new HashChangeEvent('hashchange'))
          return
        }
        setProfile(me)
        setDocuments(docsRes.documents)
        setApprovedFiles(filesRes.files)
      })
      .catch(() => {
        history.replaceState(null, '', '#/interview')
        window.dispatchEvent(new HashChangeEvent('hashchange'))
      })
      .finally(() => setLoading(false))
  }, [])

  const docsByTitle = Object.fromEntries(documents.map(d => [d.title, d]))

  const handleEdit = (doc: Document) => setEditingDoc(doc)

  const handleToggleVisibility = async (section: string, current: string) => {
    const next = current === 'public' ? 'private' : 'public'
    try {
      await updateVisibility({ [section]: next })
      setDocuments(prev => prev.map(d =>
        d.title === section ? { ...d, visibility: next } : d
      ))
    } catch { /* ignore */ }
  }

  const handleSaved = (updated: Document) => {
    setDocuments(prev => {
      const idx = prev.findIndex(d => d.documentId === updated.documentId)
      if (idx >= 0) {
        const next = [...prev]
        next[idx] = updated
        return next
      }
      return [...prev, updated]
    })
  }

  if (loading) {
    return (
      <div className="docs-page">
        <header className="interview-header">
          <a href="#/" className="interview-logo"><img src="/assets/whoisme-logo.png" alt="WhoIsMe" /></a>
          <AccountMenu />
        </header>
        <div className="profile-loading">Loading…</div>
      </div>
    )
  }

  return (
    <div className="docs-page">
      <header className="interview-header">
        <a href="#/" className="interview-logo"><img src="/assets/whoisme-logo.png" alt="WhoIsMe" /></a>
        <nav className="docs-nav">
          <a href="#/profile" className="btn-ghost">Profile</a>
          <a href="#/context" className="btn-ghost">Add</a>
        </nav>
        <AccountMenu />
      </header>

      <div className="docs-body">
        {profile?.username && (
          <div className="docs-header-row">
            <h1 className="docs-page-title">Documents</h1>
            <a
              href={`https://whoisme.io/u/${profile.username}`}
              target="_blank"
              rel="noopener noreferrer"
              className="docs-live-link"
            >
              whoisme.io/u/{profile.username} ↗
            </a>
          </div>
        )}

        <div className="docs-list">
          {Object.entries(IA_GROUPS).map(([groupLabel, sections]) => (
            <DocsGroup
              key={groupLabel}
              label={groupLabel}
              sections={sections}
              docsByTitle={docsByTitle}
              onEdit={handleEdit}
              onToggleVisibility={handleToggleVisibility}
            />
          ))}
        </div>
      </div>

      {editingDoc && (
        <DocEditorPanel
          doc={editingDoc}
          fallbackContent={approvedFiles[editingDoc.title]}
          onClose={() => setEditingDoc(null)}
          onSaved={updated => {
            handleSaved(updated)
            setEditingDoc(null)
          }}
        />
      )}
    </div>
  )
}
