import { useState, useEffect } from 'react'
import FileReview from '../components/FileReview'
import ProgressSteps from '../components/ProgressSteps'
import AccountMenu from '../components/AccountMenu'
import { moreQuestions, startAuth, pauseInterview } from '../lib/api'

const SESSION_STORAGE_KEY = 'whoisme_session'

function loadSession() {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY)
    return raw ? JSON.parse(raw) as {
      sessionId: string
      phase: string
      draftFiles: Record<string, string>
      approvedFiles: string[]
      generating?: boolean
    } : null
  } catch { return null }
}

function saveSession(data: { sessionId: string; phase: string; draftFiles: Record<string, string>; approvedFiles: string[]; generating?: boolean }) {
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(data))
}

export default function ReviewPage() {
  const saved = loadSession()

  // Redirect if no valid session
  useEffect(() => {
    if (!saved?.sessionId) {
      history.replaceState(null, '', '#/')
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const [draftFiles, setDraftFiles] = useState<Record<string, string>>(saved?.draftFiles ?? {})
  const [approvedFiles, setApprovedFiles] = useState<string[]>(saved?.approvedFiles ?? [])
  const [generating, setGenerating] = useState(saved?.generating === true)
  const [generateError, setGenerateError] = useState('')
  const sessionId = saved?.sessionId ?? ''

  // If we navigated here immediately from "end interview", call pause API now
  useEffect(() => {
    if (!generating || !sessionId) return
    pauseInterview(sessionId).then(res => {
      setDraftFiles(res.draftFiles)
      saveSession({ sessionId, phase: 'reviewing', draftFiles: res.draftFiles, approvedFiles, generating: false })
      setGenerating(false)
    }).catch(err => {
      setGenerateError(err instanceof Error ? err.message : 'Failed to generate files')
      setGenerating(false)
    })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const [email, setEmail] = useState('')
  const [magicLinkSent, setMagicLinkSent] = useState(false)
  const [magicLinkError, setMagicLinkError] = useState('')
  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('whoisme_user_token'))

  useEffect(() => {
    const handler = () => setIsLoggedIn(!!localStorage.getItem('whoisme_user_token'))
    window.addEventListener('storage', handler)
    const id = setInterval(() => setIsLoggedIn(!!localStorage.getItem('whoisme_user_token')), 500)
    return () => { window.removeEventListener('storage', handler); clearInterval(id) }
  }, [])

  // Persist approved files changes
  useEffect(() => {
    if (!sessionId) return
    saveSession({ sessionId, phase: 'reviewing', draftFiles, approvedFiles })
  }, [approvedFiles, draftFiles, sessionId])

  const handleMoreQuestions = async () => {
    if (!sessionId) return
    const res = await moreQuestions(sessionId, 10)
    saveSession({ sessionId, phase: 'interviewing', draftFiles, approvedFiles })
    history.replaceState(null, '', '#/interview')
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    // Pass the new question back via session so InterviewPage can resume
    void res
  }

  const handleStartOver = () => {
    if (!confirm('Start fresh? Your current session and sign-in will be cleared.')) return
    localStorage.removeItem(SESSION_STORAGE_KEY)
    localStorage.removeItem('whoisme_user_token')
    history.replaceState(null, '', '#/')
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  }

  const handleSendMagicLink = async () => {
    const trimmed = email.trim()
    if (!trimmed) return
    setMagicLinkError('')
    try {
      await startAuth(trimmed, sessionId)
      setMagicLinkSent(true)
    } catch (err) {
      setMagicLinkError(err instanceof Error ? err.message : 'Failed to send link')
    }
  }

  if (generating) {
    return (
      <div className="interview-page">
        <header className="interview-header">
          <a href="#/" className="interview-logo"><img src="/assets/whoisme-logo.png" alt="WhoIsMe" /></a>
          <ProgressSteps currentStep="review" />
          <AccountMenu />
        </header>
        <div className="interview-body">
          <main className="interview-main">
            <div className="review-generating">
              <div className="review-generating-spinner" />
              <p className="review-generating-text">Generating your profile files…</p>
            </div>
          </main>
        </div>
      </div>
    )
  }

  return (
    <div className="interview-page">
      <header className="interview-header">
        <a href="#/" className="interview-logo"><img src="/assets/whoisme-logo.png" alt="WhoIsMe" /></a>
        <ProgressSteps currentStep="review" />
        <div className="interview-header-actions">
          <button className="btn-ghost interview-start-over" onClick={handleStartOver}>start over</button>
          <AccountMenu />
        </div>
      </header>

      <div className="interview-body">
        <main className="interview-main">
          <div className="interview-review">
            {generateError && <p className="interview-error" style={{margin: '16px 0'}}>{generateError}</p>}

            <div className="interview-publish-box interview-publish-box--top">
              <p className="interview-review-explainer">
                Your profile files are ready. Edit them below to make them sound like you.
                When ready, download individual files or sign in to save and publish your profile.
              </p>

              {!isLoggedIn && !magicLinkSent && (
                <div className="interview-auth-section">
                  <p className="interview-auth-note">Enter your email to save and publish.</p>
                  <div className="interview-input-row">
                    <input
                      type="email"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      className="interview-text-input"
                      onKeyDown={e => e.key === 'Enter' && handleSendMagicLink()}
                    />
                    <button
                      className="btn-primary"
                      onClick={handleSendMagicLink}
                      disabled={!email.trim()}
                    >
                      Send link
                    </button>
                  </div>
                  {magicLinkError && <p className="interview-error">{magicLinkError}</p>}
                </div>
              )}
              {!isLoggedIn && magicLinkSent && (
                <p className="interview-auth-sent">Check your email — a sign-in link is on its way.</p>
              )}
              {isLoggedIn && (
                <div className="interview-auth-section">
                  <p className="interview-auth-note">Approve files below, then publish your profile.</p>
                  <a href="#/profile" className="btn-primary">Go to profile</a>
                </div>
              )}

              {generateError && (
                <div className="review-recovery-banner">
                  <p>Failed to generate files: {generateError}. Try going back to the interview.</p>
                </div>
              )}
            </div>

            <div className="interview-review-toolbar">
              <h2 className="interview-review-title">Your files</h2>
              <p className="interview-review-subtitle">Approved files sync to your account. You can revise any time.</p>
              <button className="btn-ghost" onClick={handleMoreQuestions}>+ more questions</button>
            </div>

            <FileReview
              sessionId={sessionId}
              draftFiles={draftFiles}
              approvedFiles={approvedFiles}
              onApprove={file => setApprovedFiles(prev => [...prev, file])}
              onDraftUpdate={(file, draft) => setDraftFiles(prev => ({ ...prev, [file]: draft }))}
            />

            <div className="review-start-over-row">
              <button className="btn-ghost review-start-over-btn" onClick={handleStartOver}>
                start over
              </button>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
