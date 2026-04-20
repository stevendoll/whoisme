import { useState, useEffect, useRef, useCallback } from 'react'
import InterviewBox from '../components/InterviewBox'
import type { InterviewBoxHandle } from '../components/InterviewBox'
import { getContextSections, contextEnd, contextPublish } from '../lib/api'
import type { ContextSectionMeta } from '../lib/api'
import type { InterviewPhase } from '../lib/types'

type Step = 'loading' | 'choose' | 'interviewing' | 'publishing' | 'success' | 'error'

export default function QuickContextPage() {
  const [step, setStep] = useState<Step>('loading')
  const [sections, setSections] = useState<ContextSectionMeta[]>([])
  const [selectedSection, setSelectedSection] = useState<ContextSectionMeta | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [successUrl, setSuccessUrl] = useState('')
  const [error, setError] = useState('')
  const boxRef = useRef<InterviewBoxHandle>(null)

  useEffect(() => {
    getContextSections()
      .then(r => { setSections(r.sections); setStep('choose') })
      .catch(() => { setError('Could not load context types.'); setStep('error') })
  }, [])

  const handleChoose = (section: ContextSectionMeta) => {
    setSelectedSection(section)
    setStep('interviewing')
  }

  const handlePublish = useCallback(async (sid: string) => {
    setStep('publishing')
    try {
      const result = await contextPublish(sid)
      setSuccessUrl(result.url)
      setStep('success')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to publish context')
      setStep('error')
    }
  }, [])

  const handlePhaseChange = useCallback((phase: InterviewPhase) => {
    if (phase === 'complete' && sessionId) {
      void handlePublish(sessionId)
    }
  }, [sessionId, handlePublish])

  const handleContextDone = useCallback(async () => {
    const sid = boxRef.current?.sessionId ?? sessionId
    if (!sid) return
    try {
      await contextEnd(sid)
      void handlePublish(sid)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to end session')
      setStep('error')
    }
  }, [sessionId, handlePublish])

  const handleReset = () => {
    setSelectedSection(null)
    setSessionId(null)
    setSuccessUrl('')
    setError('')
    setStep('choose')
  }

  if (step === 'loading') {
    return (
      <div className="landing-page">
        <div className="landing-content">
          <p style={{ color: 'rgba(245,240,232,0.4)', fontSize: '0.85rem' }}>Loading…</p>
        </div>
      </div>
    )
  }

  if (step === 'error') {
    return (
      <div className="landing-page">
        <div className="landing-content">
          <p style={{ color: '#ff6b6b', marginBottom: 16 }}>{error}</p>
          <a href="#/profile" className="btn-ghost">Back to profile</a>
        </div>
      </div>
    )
  }

  if (step === 'success') {
    const label = selectedSection?.label ?? 'context'
    return (
      <div className="landing-page">
        <div className="landing-content">
          <p style={{ fontSize: '1.1rem', marginBottom: 8 }}>Done.</p>
          <p style={{ color: 'rgba(245,240,232,0.6)', marginBottom: 24 }}>
            Your {label.toLowerCase()} is saved privately.
          </p>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
            <a href={successUrl} target="_blank" rel="noopener noreferrer" className="btn-ghost">
              View profile
            </a>
            <button className="btn-ghost" onClick={handleReset}>
              Add another
            </button>
            <a href="#/profile" className="btn-ghost">
              Back to profile
            </a>
          </div>
        </div>
      </div>
    )
  }

  if (step === 'publishing') {
    return (
      <div className="landing-page">
        <div className="landing-content">
          <p style={{ color: 'rgba(245,240,232,0.4)', fontSize: '0.85rem' }}>Saving your context…</p>
        </div>
      </div>
    )
  }

  if (step === 'choose') {
    return (
      <div className="landing-page">
        <div className="landing-content">
          <p className="landing-subheading" style={{ marginBottom: 32 }}>What would you like to add?</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, width: '100%', maxWidth: 360 }}>
            {sections.map(section => (
              <button
                key={section.key}
                className="btn-ghost"
                style={{ textAlign: 'left', padding: '14px 20px' }}
                onClick={() => handleChoose(section)}
              >
                {section.label}
              </button>
            ))}
            <div style={{ borderTop: '1px solid var(--border)', margin: '8px 0' }} />
            <a href="#/interview" className="btn-ghost" style={{ textAlign: 'left', padding: '14px 20px' }}>
              Full interview — start over
            </a>
          </div>
          <div style={{ marginTop: 24 }}>
            <a href="#/profile" style={{ color: 'rgba(245,240,232,0.4)', fontSize: '0.8rem' }}>
              ← Back to profile
            </a>
          </div>
        </div>
      </div>
    )
  }

  // step === 'interviewing'
  return (
    <div className="interview-page">
      <div className="interview-main">
        <InterviewBox
          ref={boxRef}
          contextType={selectedSection?.key}
          onPhaseChange={handlePhaseChange}
          onSessionCreated={setSessionId}
          onContextDone={selectedSection?.aiDriven ? handleContextDone : undefined}
        />
      </div>
    </div>
  )
}
