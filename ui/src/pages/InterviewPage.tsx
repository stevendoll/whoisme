import { useState, useCallback, useEffect, useRef } from 'react'
import InterviewBox, { type InterviewBoxHandle } from '../components/InterviewBox'
import SectionFill from '../components/SectionFill'
import ProgressSteps from '../components/ProgressSteps'
import AccountMenu from '../components/AccountMenu'
import type { InterviewPhase } from '../lib/types'

const SESSION_STORAGE_KEY = 'whoisme_session'

function saveSession(data: {
  sessionId: string
  phase: InterviewPhase
  draftFiles: Record<string, string>
  approvedFiles: string[]
  generating?: boolean
}) {
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(data))
}

function loadSession(): {
  sessionId: string
  phase: InterviewPhase
  draftFiles: Record<string, string>
  approvedFiles: string[]
  generating?: boolean
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
  const [resumePrompt, setResumePrompt] = useState(saved?.phase === 'reviewing')

  const [sessionId, setSessionId] = useState<string | null>(saved?.sessionId ?? null)
  const sessionIdRef = useRef<string | null>(saved?.sessionId ?? null)
  useEffect(() => { sessionIdRef.current = sessionId }, [sessionId])
  const [phase, setPhase] = useState<InterviewPhase>(saved?.phase === 'reviewing' ? 'interviewing' : (saved?.phase ?? 'interviewing'))
  const [questionsRemaining, setQuestionsRemaining] = useState<number | null>(null)
  const [sectionDensity, setSectionDensity] = useState<Record<string, number>>({})
  const [skippedSections, setSkippedSections] = useState<string[]>([])
  const [draftFiles, setDraftFiles] = useState<Record<string, string>>(saved?.draftFiles ?? {})
  const [approvedFiles] = useState<string[]>(saved?.approvedFiles ?? [])

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

    if (newPhase === 'reviewing') {
      // Save synchronously before navigating so ReviewPage reads fresh data
      const sid = sessionIdRef.current
      if (sid) {
        const mergedDrafts = drafts ? { ...draftFiles, ...drafts } : draftFiles
        const generating = !drafts  // no drafts = triggered by pause button, ReviewPage will call the API
        saveSession({ sessionId: sid, phase: 'reviewing', draftFiles: mergedDrafts, approvedFiles, generating })
      }
      history.replaceState(null, '', '#/review')
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    }
  }, [draftFiles, approvedFiles])

  const handleSectionsTouched = useCallback((sections: string[]) => {
    setSectionDensity(prev => {
      const next = { ...prev }
      sections.forEach(s => { next[s] = (next[s] ?? 0) + 1 })
      return next
    })
  }, [])

  const handleStartOver = () => {
    if (!confirm('Start a new interview? Your current session will be lost.')) return
    localStorage.removeItem(SESSION_STORAGE_KEY)
    history.replaceState(null, '', '#/')
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  }

  const handleStartFresh = () => {
    localStorage.removeItem(SESSION_STORAGE_KEY)
    setResumePrompt(false)
  }

  if (resumePrompt) {
    return (
      <div className="interview-page">
        <header className="interview-header">
          <a href="#/" className="interview-logo"><img src="/assets/whoisme-logo.png" alt="WhoIsMe" /></a>
          <ProgressSteps currentStep="interview" />
          <AccountMenu />
        </header>
        <div className="interview-body">
          <main className="interview-main">
            <div className="resume-prompt">
              <p className="resume-prompt-text">You have a profile draft in progress.</p>
              <div className="resume-prompt-actions">
                <a href="#/review" className="btn-primary">Continue reviewing</a>
                <button className="btn-ghost" onClick={handleStartFresh}>Start a new interview</button>
              </div>
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
        <ProgressSteps currentStep="interview" questionsLeft={questionsRemaining ?? undefined} />
        <div className="interview-header-actions">
          {sessionId && (
            <button className="btn-ghost interview-start-over" onClick={handleStartOver}>start over</button>
          )}
          <AccountMenu />
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
          <InterviewBox
            ref={boxRef}
            onSessionCreated={setSessionId}
            onPhaseChange={handlePhaseChange}
            onQuestionsUpdate={setQuestionsRemaining}
            onSectionsTouched={handleSectionsTouched}
            onSkippedUpdate={setSkippedSections}
          />
        </main>
      </div>
    </div>
  )
}
