import { useState, useCallback, useEffect, useRef } from 'react'
import InterviewBox, { type InterviewBoxHandle } from '../components/InterviewBox'
import SectionFill from '../components/SectionFill'
import FileReview from '../components/FileReview'
import { moreQuestions, startAuth } from '../lib/api'
import type { InterviewPhase } from '../lib/types'

const SESSION_STORAGE_KEY = 'whoisme_session'

function saveSession(data: {
  sessionId: string
  phase: InterviewPhase
  draftFiles: Record<string, string>
  approvedFiles: string[]
}) {
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(data))
}

function loadSession(): {
  sessionId: string
  phase: InterviewPhase
  draftFiles: Record<string, string>
  approvedFiles: string[]
} | null {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export default function InterviewPage() {
  const boxRef = useRef<InterviewBoxHandle>(null)

  const saved = loadSession()
  const [sessionId, setSessionId] = useState<string | null>(saved?.sessionId ?? null)
  const [phase, setPhase] = useState<InterviewPhase>(saved?.phase ?? 'interviewing')
  const [questionsRemaining, setQuestionsRemaining] = useState<number | null>(null)
  const [sectionDensity, setSectionDensity] = useState<Record<string, number>>({})
  const [skippedSections, setSkippedSections] = useState<string[]>([])
  const [draftFiles, setDraftFiles] = useState<Record<string, string>>(saved?.draftFiles ?? {})
  const [approvedFiles, setApprovedFiles] = useState<string[]>(saved?.approvedFiles ?? [])

  // Auth
  const [email, setEmail] = useState('')
  const [magicLinkSent, setMagicLinkSent] = useState(false)
  const [magicLinkError, setMagicLinkError] = useState('')

  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('whoisme_user_token'))

  // Re-check login state when storage changes (e.g. after magic link verify in same tab)
  useEffect(() => {
    const handler = () => setIsLoggedIn(!!localStorage.getItem('whoisme_user_token'))
    window.addEventListener('storage', handler)
    // Also poll once — storage events don't fire in the same tab
    const id = setInterval(() => setIsLoggedIn(!!localStorage.getItem('whoisme_user_token')), 500)
    return () => { window.removeEventListener('storage', handler); clearInterval(id) }
  }, [])

  // Persist session state whenever key values change
  useEffect(() => {
    if (!sessionId) return
    saveSession({ sessionId, phase, draftFiles, approvedFiles })
  }, [sessionId, phase, draftFiles, approvedFiles])

  const handlePhaseChange = useCallback((
    newPhase: InterviewPhase,
    drafts?: Record<string, string>,
    skipped?: string[],
  ) => {
    setPhase(newPhase)
    if (drafts) setDraftFiles(prev => ({ ...prev, ...drafts }))
    if (skipped) setSkippedSections(skipped)
  }, [])

  const handleSectionsTouched = useCallback((sections: string[]) => {
    setSectionDensity(prev => {
      const next = { ...prev }
      sections.forEach(s => { next[s] = (next[s] ?? 0) + 1 })
      return next
    })
  }, [])

  const handleMoreQuestions = async (count = 10) => {
    if (!sessionId) return
    const res = await moreQuestions(sessionId, count)
    setPhase('interviewing')
    boxRef.current?.resumeWithQuestion(res.message, res.heckle, res.questionsRemaining)
  }

  const handleSendMagicLink = async () => {
    const trimmed = email.trim()
    if (!trimmed || !sessionId) return
    setMagicLinkError('')
    try {
      await startAuth(trimmed, sessionId)
      setMagicLinkSent(true)
    } catch (err) {
      setMagicLinkError(err instanceof Error ? err.message : 'Failed to send link')
    }
  }


  return (
    <div className="interview-page">
      <header className="interview-header">
        <a href="#/" className="interview-logo"><img src="/assets/whoisme-banner.png" alt="WhoIsMe" /></a>
        <div className="interview-progress">
          {phase === 'interviewing' && questionsRemaining !== null && (
            <span className="interview-questions-left">{questionsRemaining} questions left</span>
          )}
          {phase === 'reviewing' && (
            <span className="interview-phase-label">review your files</span>
          )}
        </div>
      </header>

      <div className="interview-body">
        {phase === 'interviewing' && sessionId && (
          <aside className="interview-sidebar">
            <SectionFill
              sessionId={sessionId}
              density={sectionDensity}
              skipped={skippedSections}
              approved={approvedFiles}
              onUpdate={setSkippedSections}
            />
          </aside>
        )}

        <main className="interview-main">
          {phase === 'interviewing' && (
            <InterviewBox
              ref={boxRef}
              onSessionCreated={setSessionId}
              onPhaseChange={handlePhaseChange}
              onQuestionsUpdate={setQuestionsRemaining}
              onSectionsTouched={handleSectionsTouched}
              onSkippedUpdate={setSkippedSections}
            />
          )}

          {phase === 'reviewing' && sessionId && (
            <div className="interview-review">

              <div className="interview-publish-box interview-publish-box--top">
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
              </div>

              <div className="interview-review-toolbar">
                <h2 className="interview-review-title">Your files</h2>
                <button
                  className="btn-ghost"
                  onClick={() => handleMoreQuestions()}
                >
                  + more questions
                </button>
              </div>

              <FileReview
                sessionId={sessionId}
                draftFiles={draftFiles}
                approvedFiles={approvedFiles}
                onApprove={file => setApprovedFiles(prev => [...prev, file])}
                onDraftUpdate={(file, draft) => setDraftFiles(prev => ({ ...prev, [file]: draft }))}
              />

            </div>
          )}
        </main>
      </div>
    </div>
  )
}
