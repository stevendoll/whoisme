import { useState, useEffect, useRef, useCallback } from 'react'
import InterviewBox from '../components/InterviewBox'
import type { InterviewBoxHandle } from '../components/InterviewBox'
import { getContextSections, contextEnd, contextPublish, contextImport } from '../lib/api'
import type { ContextSectionMeta } from '../lib/api'
import type { InterviewPhase } from '../lib/types'

type Step = 'loading' | 'choose' | 'interviewing' | 'import' | 'publishing' | 'success' | 'error'
type MergeStrategy = 'replace' | 'prepend' | 'append'

export default function QuickContextPage() {
  const [step, setStep] = useState<Step>('loading')
  const [sections, setSections] = useState<ContextSectionMeta[]>([])
  const [selectedSection, setSelectedSection] = useState<ContextSectionMeta | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [successUrl, setSuccessUrl] = useState('')
  const [error, setError] = useState('')
  const [importSection, setImportSection] = useState('')
  const [importContent, setImportContent] = useState('')
  const [importMerge, setImportMerge] = useState<MergeStrategy>('prepend')
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
    setImportContent('')
    setImportSection('')
    setImportMerge('prepend')
    setStep('choose')
  }

  const handleImportSubmit = async () => {
    if (!importSection || !importContent.trim()) return
    setStep('publishing')
    try {
      const result = await contextImport(importSection, importContent.trim(), importMerge)
      setSuccessUrl(result.url)
      setStep('success')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
      setStep('error')
    }
  }

  const handleFileLoad = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => setImportContent(ev.target?.result as string ?? '')
    reader.readAsText(file)
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
    const label = selectedSection?.label
      ?? sections.find(s => s.key === importSection)?.label
      ?? 'context'
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
            <button
              className="btn-ghost"
              style={{ textAlign: 'left', padding: '14px 20px' }}
              onClick={() => { setImportSection(sections[0]?.key ?? ''); setStep('import') }}
            >
              Import markdown
            </button>
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

  if (step === 'import') {
    const mergeOptions: { value: MergeStrategy; label: string; description: string }[] = [
      { value: 'prepend', label: 'Prepend', description: 'Add before existing content' },
      { value: 'append',  label: 'Append',  description: 'Add after existing content' },
      { value: 'replace', label: 'Replace', description: 'Overwrite existing content' },
    ]
    return (
      <div className="landing-page">
        <div className="landing-content" style={{ maxWidth: 560, width: '100%' }}>
          <p className="landing-subheading" style={{ marginBottom: 24 }}>Import markdown</p>

          <div style={{ marginBottom: 16, textAlign: 'left' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'rgba(245,240,232,0.5)', marginBottom: 6 }}>
              Section
            </label>
            <select
              value={importSection}
              onChange={e => setImportSection(e.target.value)}
              style={{
                width: '100%', padding: '10px 12px', background: 'var(--surface)',
                border: '1px solid var(--border)', borderRadius: 6,
                color: 'var(--text)', fontSize: '0.9rem',
              }}
            >
              {sections.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>
          </div>

          <div style={{ marginBottom: 16, textAlign: 'left' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'rgba(245,240,232,0.5)', marginBottom: 6 }}>
              Merge strategy
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              {mergeOptions.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setImportMerge(opt.value)}
                  title={opt.description}
                  style={{
                    flex: 1, padding: '8px 0', fontSize: '0.85rem', cursor: 'pointer',
                    background: importMerge === opt.value ? 'var(--accent, rgba(245,240,232,0.12))' : 'var(--surface)',
                    border: `1px solid ${importMerge === opt.value ? 'rgba(245,240,232,0.4)' : 'var(--border)'}`,
                    borderRadius: 6, color: 'var(--text)',
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div style={{ marginBottom: 16, textAlign: 'left' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <label style={{ fontSize: '0.8rem', color: 'rgba(245,240,232,0.5)' }}>Content</label>
              <label style={{ fontSize: '0.8rem', color: 'rgba(245,240,232,0.4)', cursor: 'pointer' }}>
                Load file
                <input type="file" accept=".md,.txt" onChange={handleFileLoad} style={{ display: 'none' }} />
              </label>
            </div>
            <textarea
              value={importContent}
              onChange={e => setImportContent(e.target.value)}
              placeholder="Paste markdown here or load a file…"
              rows={12}
              style={{
                width: '100%', padding: '10px 12px', background: 'var(--surface)',
                border: '1px solid var(--border)', borderRadius: 6,
                color: 'var(--text)', fontSize: '0.85rem', resize: 'vertical',
                fontFamily: 'monospace', boxSizing: 'border-box',
              }}
            />
          </div>

          <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
            <button className="btn-ghost" onClick={handleReset}>Cancel</button>
            <button
              className="btn-ghost"
              onClick={handleImportSubmit}
              disabled={!importSection || !importContent.trim()}
            >
              Import
            </button>
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
