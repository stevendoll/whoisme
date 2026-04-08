import { useState, useCallback, useRef } from 'react'
import InterviewBox, { type InterviewBoxHandle } from '../components/InterviewBox'
import SectionFill from '../components/SectionFill'
import FileReview from '../components/FileReview'
import { moreQuestions, startAuth, publishProfile } from '../lib/api'
import type { InterviewPhase } from '../lib/types'

export default function InterviewPage() {
  const boxRef = useRef<InterviewBoxHandle>(null)

  const [sessionId, setSessionId] = useState<string | null>(null)
  const [phase, setPhase] = useState<InterviewPhase>('interviewing')
  const [questionsRemaining, setQuestionsRemaining] = useState<number | null>(null)
  const [sectionDensity, setSectionDensity] = useState<Record<string, number>>({})
  const [skippedSections, setSkippedSections] = useState<string[]>([])
  const [draftFiles, setDraftFiles] = useState<Record<string, string>>({})
  const [approvedFiles, setApprovedFiles] = useState<string[]>([])

  // Auth / publish
  const [email, setEmail] = useState('')
  const [magicLinkSent, setMagicLinkSent] = useState(false)
  const [magicLinkError, setMagicLinkError] = useState('')
  const [username, setUsername] = useState('')
  const [publishing, setPublishing] = useState(false)
  const [publishError, setPublishError] = useState('')
  const [publishedUrl, setPublishedUrl] = useState('')

  const isLoggedIn = !!localStorage.getItem('whoisme_user_token')

  const totalDraftable = 10 - skippedSections.length
  const allApproved = totalDraftable > 0 && approvedFiles.length >= totalDraftable

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

  const handlePublish = async () => {
    const name = username.trim()
    if (!name) return
    setPublishing(true)
    setPublishError('')
    try {
      const res = await publishProfile(name)
      setPublishedUrl(res.url)
    } catch (err) {
      setPublishError(err instanceof Error ? err.message : 'Failed to publish')
    } finally {
      setPublishing(false)
    }
  }

  return (
    <div className="interview-page">
      <header className="interview-header">
        <a href="#/" className="interview-logo">WhoIsMe</a>
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

              {allApproved && !publishedUrl && (
                <div className="interview-publish-box">
                  <h3 className="interview-publish-heading">Publish your profile</h3>

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
                      <div className="interview-input-row">
                        <span className="interview-username-prefix">whoisme.io/u/</span>
                        <input
                          type="text"
                          value={username}
                          onChange={e => setUsername(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ''))}
                          placeholder="yourname"
                          className="interview-text-input"
                          onKeyDown={e => e.key === 'Enter' && handlePublish()}
                        />
                        <button
                          className="btn-primary"
                          onClick={handlePublish}
                          disabled={publishing || !username.trim()}
                        >
                          {publishing ? 'Publishing…' : 'Publish'}
                        </button>
                      </div>
                      {publishError && <p className="interview-error">{publishError}</p>}
                    </div>
                  )}
                </div>
              )}

              {publishedUrl && (
                <div className="interview-published">
                  Your profile is live at{' '}
                  <a href={publishedUrl} target="_blank" rel="noopener noreferrer">{publishedUrl}</a>
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
