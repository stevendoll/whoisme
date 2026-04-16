import { useState, useEffect } from 'react'

interface ProfileData {
  username: string
  updatedAt: string
  files: Record<string, string>
  visibility: Record<string, string>
}

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

const BASE = import.meta.env.VITE_API_URL ?? ''

export default function PublicProfilePage({ username }: { username: string }) {
  const [profile, setProfile] = useState<ProfileData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${BASE}/users/profile/${username}`)
      .then(r => {
        if (!r.ok) throw new Error(r.status === 404 ? 'Profile not found' : 'Failed to load profile')
        return r.json()
      })
      .then(setProfile)
      .catch(e => setError(e.message))
  }, [username])

  const publicFiles = profile
    ? Object.entries(profile.files).filter(([key]) => (profile.visibility[key] ?? 'public') === 'public')
    : []

  return (
    <div className="public-profile-page">
      <header className="interview-header">
        <a href="/" className="interview-logo"><img src="/assets/whoisme-logo.png" alt="WhoIsMe" /></a>
        {profile && (
          <div className="interview-progress">
            <span className="interview-phase-label">{profile.username}</span>
          </div>
        )}
      </header>

      <div className="public-profile-body">
        {error && (
          <div className="public-profile-error">{error}</div>
        )}

        {!profile && !error && (
          <div className="public-profile-loading">Loading…</div>
        )}

        {profile && (
          <>
            <h1 className="public-profile-title">{profile.username}</h1>
            <div className="public-profile-files">
              {publicFiles.map(([key, content]) => (
                <section key={key} className="public-profile-section">
                  <h2 className="public-profile-section-title">{SECTION_LABELS[key] ?? key}</h2>
                  <div className="public-profile-section-body">
                    {content.split('\n').map((line, i) => (
                      <p key={i}>{line}</p>
                    ))}
                  </div>
                </section>
              ))}
            </div>
            <div className="public-profile-footer">
              <a href="/" className="public-profile-footer-link">Built with WhoIsMe</a>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
