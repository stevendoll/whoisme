import { useState, useEffect } from 'react'
import { getMe, updateVisibility, publishProfile } from '../lib/api'
import type { UserProfile } from '../lib/types'

const SECTIONS = [
  'identity',
  'role-and-responsibilities',
  'current-projects',
  'team-and-relationships',
  'tools-and-systems',
  'communication-style',
  'goals-and-priorities',
  'preferences-and-constraints',
  'domain-knowledge',
  'decision-log',
]

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

const SESSION_STORAGE_KEY = 'whoisme_session'

function loadSession() {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY)
    return raw ? JSON.parse(raw) as { sessionId: string; phase: string; draftFiles: Record<string, string>; approvedFiles: string[] } : null
  } catch { return null }
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [visibility, setVisibility] = useState<Record<string, string>>({})
  const [username, setUsername] = useState('')
  const [publishing, setPublishing] = useState(false)
  const [publishError, setPublishError] = useState('')
  const [publishedUrl, setPublishedUrl] = useState('')
  const [lastPublishedAt, setLastPublishedAt] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const session = loadSession()
  const draftFiles = session?.draftFiles ?? {}
  const approvedFiles = new Set(session?.approvedFiles ?? [])
  const anyApproved = approvedFiles.size > 0

  useEffect(() => {
    getMe().then(p => {
      setProfile(p)
      setVisibility(p.visibility)
      if (p.username) setUsername(p.username)
      if (p.published && p.username) {
        setPublishedUrl(`https://whoisme.io/u/${p.username}`)
      }
      setLastPublishedAt(p.lastPublishedAt ?? null)
    }).catch(() => {
      history.replaceState(null, '', '#/interview')
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    }).finally(() => setLoading(false))
  }, [])

  const handleToggleVisibility = async (section: string) => {
    const current = visibility[section] ?? 'public'
    const next = current === 'public' ? 'private' : 'public'
    const updated = { ...visibility, [section]: next }
    setVisibility(updated)
    try {
      const res = await updateVisibility({ [section]: next })
      setVisibility(res.visibility)
    } catch {
      setVisibility(prev => ({ ...prev, [section]: current }))
    }
  }

  const handlePublish = async () => {
    const name = username.trim()
    if (!name) return
    setPublishing(true)
    setPublishError('')
    try {
      const res = await publishProfile(name)
      setPublishedUrl(res.url)
      setLastPublishedAt(res.lastPublishedAt)
      localStorage.removeItem(SESSION_STORAGE_KEY)
    } catch (err) {
      setPublishError(err instanceof Error ? err.message : 'Failed to publish')
    } finally {
      setPublishing(false)
    }
  }

  const getStatus = (section: string): 'approved' | 'draft' | 'none' => {
    if (approvedFiles.has(section)) return 'approved'
    if (draftFiles[section]) return 'draft'
    return 'none'
  }

  // A file is "changed since publish" if its approved_at timestamp is newer than last_published_at
  const isChangedSincePublish = (section: string): boolean => {
    const approvedAt = profile?.approvedFilesAt?.[section]
    if (!approvedAt || !lastPublishedAt) return false
    return approvedAt > lastPublishedAt
  }

  const anyChangedSincePublish = SECTIONS.some(s => isChangedSincePublish(s))

  const completionCount = SECTIONS.filter(s => getStatus(s) !== 'none').length
  const approvedCount = SECTIONS.filter(s => getStatus(s) === 'approved').length

  if (loading) {
    return (
      <div className="profile-page">
        <header className="interview-header">
          <a href="#/" className="interview-logo"><img src="/assets/whoisme-banner.png" alt="WhoIsMe" /></a>
        </header>
        <div className="profile-loading">Loading…</div>
      </div>
    )
  }

  return (
    <div className="profile-page">
      <header className="interview-header">
        <a href="#/" className="interview-logo"><img src="/assets/whoisme-banner.png" alt="WhoIsMe" /></a>
        <div className="interview-progress">
          <span className="interview-phase-label">{approvedCount}/{SECTIONS.length} approved</span>
        </div>
      </header>

      <div className="profile-body">

        {/* Publish section */}
        <section className="profile-publish-section">
          {publishedUrl ? (
            <div className="profile-published">
              <div className="profile-published-row">
                <span className="profile-published-label">Your profile is live at</span>
                <a href={publishedUrl} target="_blank" rel="noopener noreferrer" className="profile-published-url">{publishedUrl}</a>
              </div>
              {lastPublishedAt && (
                <span className="profile-published-date">Last published {fmtDate(lastPublishedAt)}</span>
              )}
              <div className="profile-publish-actions">
                {(anyApproved || anyChangedSincePublish) && (
                  <button
                    className={`btn-primary${anyChangedSincePublish ? ' btn-primary--active' : ''}`}
                    onClick={handlePublish}
                    disabled={publishing}
                  >
                    {publishing ? 'Publishing…' : anyChangedSincePublish ? 'Republish (changes pending)' : 'Republish'}
                  </button>
                )}
                <a href="#/interview" className="btn-ghost">Edit files</a>
              </div>
              {publishError && <p className="interview-error">{publishError}</p>}
            </div>
          ) : (
            <div className="profile-publish-form">
              <div className="profile-url-row">
                <span className="interview-username-prefix">whoisme.io/u/</span>
                <input
                  type="text"
                  value={username}
                  onChange={e => setUsername(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ''))}
                  placeholder="yourname"
                  className="interview-text-input"
                  onKeyDown={e => e.key === 'Enter' && anyApproved && handlePublish()}
                />
                {anyApproved && (
                  <button
                    className="btn-primary"
                    onClick={handlePublish}
                    disabled={publishing || !username.trim()}
                  >
                    {publishing ? 'Publishing…' : 'Publish'}
                  </button>
                )}
                <a href="#/interview" className="btn-ghost">Edit files</a>
              </div>
              {publishError && <p className="interview-error">{publishError}</p>}
              {!anyApproved && (
                <p className="profile-publish-hint">Approve at least one file to publish.</p>
              )}
            </div>
          )}
        </section>

        {/* File list */}
        <section className="profile-files">
          <div className="profile-files-summary">
            {completionCount} of {SECTIONS.length} sections drafted · {approvedCount} approved
          </div>
          <table className="profile-files-table">
            <thead>
              <tr>
                <th>File</th>
                <th>Status</th>
                <th>Last modified</th>
                <th>Visibility</th>
              </tr>
            </thead>
            <tbody>
              {SECTIONS.map(section => {
                const status = getStatus(section)
                const vis = visibility[section] ?? 'public'
                const approvedAt = profile?.approvedFilesAt?.[section]
                const changed = isChangedSincePublish(section)
                return (
                  <tr key={section} className={`profile-file-row profile-file-row--${status}${changed ? ' profile-file-row--changed' : ''}`}>
                    <td className="profile-file-name">
                      {SECTION_LABELS[section]}
                      {changed && <span className="profile-badge profile-badge--changed" title="Changed since last publish">updated</span>}
                    </td>
                    <td className="profile-file-status">
                      {status === 'approved' && <span className="profile-badge profile-badge--approved">approved</span>}
                      {status === 'draft'    && <span className="profile-badge profile-badge--draft">draft</span>}
                      {status === 'none'     && <span className="profile-badge profile-badge--none">not started</span>}
                    </td>
                    <td className="profile-file-date">
                      {approvedAt ? fmtDate(approvedAt) : '—'}
                    </td>
                    <td className="profile-file-visibility">
                      {status !== 'none' && (
                        <button
                          className={`profile-vis-toggle profile-vis-toggle--${vis}`}
                          onClick={() => handleToggleVisibility(section)}
                          title={vis === 'private' ? 'Private: requires bearer token' : 'Public: visible to anyone'}
                        >
                          {vis}
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </section>

        {profile && (
          <div className="profile-account">
            Signed in as <strong>{profile.email}</strong>
          </div>
        )}
      </div>
    </div>
  )
}
