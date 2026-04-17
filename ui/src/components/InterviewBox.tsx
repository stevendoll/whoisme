import { useState, useEffect, useRef, useCallback, forwardRef, useImperativeHandle } from 'react'
import { createInterview, respondToInterview, skipQuestion } from '../lib/api'
import type { InterviewPhase, RespondResponse } from '../lib/types'
import MicButton from './MicButton'
import SpeakButton from './SpeakButton'
import Visualizer, { type VisualizerHandle } from './Visualizer'
import ChatBubble from './ChatBubble'
import type { ChatRole } from './ChatBubble'
import { postError } from '../lib/api'

const CARTESIA_API_KEY = import.meta.env.VITE_CARTESIA_API_KEY as string
const SAMPLE_RATE = 44100

// Interviewer voice — warm, professional
const INTERVIEWER_VOICES = [
  '26403c37-80c1-4a1a-8692-540551ca2ae5', // Marian
  'cc00e582-ed66-4004-8336-0175b85c85f6', // Dana
  '6ccbfb76-1fc6-48f7-b71d-91ac6298247b', // Tessa
  'cbaf8084-f009-4838-a096-07ee2e6612b1', // Maya
]

// Wise Guy voice — distinct character voice
const WISE_GUY_VOICE_ID: string = (import.meta.env.VITE_WISE_GUY_VOICE_ID as string)?.trim()
  || 'a0e99841-438c-4a64-b679-ae501e7d6091' // Barbershop Man

function stripSsml(text: string): string {
  if (!text) return ''
  return text
    .replace(/<emotion[^>]*\/?>/gi, '')
    .replace(/<\/emotion>/gi, '')
    .replace(/\[clears throat\]/gi, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

function pickInterviewerVoice(): string {
  const envVoice = import.meta.env.VITE_INTERVIEWER_VOICE_ID as string
  if (envVoice?.trim()) return envVoice.trim()
  return INTERVIEWER_VOICES[Math.floor(Math.random() * INTERVIEWER_VOICES.length)]
}


export interface InterviewBoxHandle {
  sessionId: string | null
  resumeWithQuestion: (message: string, heckle: string | null, questionsRemaining: number) => void
}

interface ChatEntry {
  id: string
  role: ChatRole
  text: string
}

interface InterviewBoxProps {
  onSectionsTouched?: (sections: string[]) => void
  onPhaseChange?: (phase: InterviewPhase, draftFiles?: Record<string, string>, skippedSections?: string[]) => void
  onQuestionsUpdate?: (remaining: number) => void
  onHeckle?: (text: string) => void
  onSessionCreated?: (sessionId: string) => void
  onSkippedUpdate?: (skipped: string[]) => void
}

const InterviewBox = forwardRef<InterviewBoxHandle, InterviewBoxProps>(function InterviewBox({
  onSectionsTouched,
  onPhaseChange,
  onQuestionsUpdate,
  onHeckle,
  onSessionCreated,
  onSkippedUpdate: _onSkippedUpdate,
}, ref) {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [phase, setPhase] = useState<InterviewPhase>('interviewing')
  const [messages, setMessages] = useState<ChatEntry[]>([])
  const [status, setStatus] = useState('')
  const [statusType, setStatusType] = useState<'' | 'error' | 'playing'>('')
  const [latencyMs, setLatencyMs] = useState<number | null>(null)
  const [inputText, setInputText] = useState('')

  type BoxState = 'loading' | 'failed' | 'interviewer-speaking' | 'waiting' | 'user-speaking' | 'submitting'
  const [boxState, setBoxState] = useState<BoxState>('loading')
  const [ttsState, setTtsState] = useState<'idle' | 'connecting' | 'playing'>('idle')

  const [questionsRemaining, setQuestionsRemaining] = useState<number | null>(null)
  const [questionsTotal, setQuestionsTotal] = useState<number | null>(null)

  const inputRef         = useRef<HTMLTextAreaElement>(null)
  const audioCtxRef      = useRef<AudioContext | null>(null)
  const analyserRef      = useRef<AnalyserNode | null>(null)
  const vizRef           = useRef<VisualizerHandle>(null)
  const chatEndRef       = useRef<HTMLDivElement>(null)
  const chatAreaRef      = useRef<HTMLDivElement>(null)
  const ttsDisabled      = useRef(false)
  const ttsErrorReported = useRef(false)
  const voiceId          = useRef(pickInterviewerVoice())
  const sessionIdRef     = useRef<string | null>(null)
  const wiseGuyEnabledRef = useRef(true)
  const [wiseGuyEnabled, setWiseGuyEnabled] = useState(true)

  // Keep ref in sync so callbacks have stable access
  useEffect(() => { sessionIdRef.current = sessionId }, [sessionId])

  useEffect(() => {
    if (messages.length === 0) return
    requestAnimationFrame(() => chatAreaRef.current?.scrollTo({ top: chatAreaRef.current.scrollHeight, behavior: 'smooth' }))
  }, [messages])

  const addMessage = useCallback((role: ChatEntry['role'], text: string) => {
    setMessages(prev => [...prev, { id: crypto.randomUUID(), role, text }])
  }, [])

  const reportTtsError = useCallback((message: string) => {
    if (ttsErrorReported.current) return
    ttsErrorReported.current = true
    postError('tts_failure', message).catch(() => { /* best-effort */ })
  }, [])

  const speakText = useCallback((text: string, voiceOverride?: string): Promise<void> => {
    return new Promise(resolve => {
      const clean = stripSsml(text)
      const activeVoice = voiceOverride ?? voiceId.current
      if (!CARTESIA_API_KEY || !activeVoice || ttsDisabled.current) {
        setTtsState('playing'); setStatus('▶ Playing...'); setStatusType('playing')
        const ms = Math.max(800, clean.length * 45)
        setTimeout(() => { setTtsState('idle'); setStatus(''); setStatusType(''); resolve() }, ms)
        return
      }

      setTtsState('connecting'); setStatus('Connecting...'); setStatusType(''); setLatencyMs(null)
      const startMark = performance.now()

      try {
        if (!audioCtxRef.current) audioCtxRef.current = new AudioContext()
        void audioCtxRef.current.resume()
        const audioCtx = audioCtxRef.current

        analyserRef.current = audioCtx.createAnalyser()
        analyserRef.current.fftSize = 256
        analyserRef.current.connect(audioCtx.destination)

        const wsUrl = `wss://api.cartesia.ai/tts/websocket?api_key=${CARTESIA_API_KEY}&cartesia_version=2025-04-16`
        const ws = new WebSocket(wsUrl)
        ws.binaryType = 'arraybuffer'

        let nextPlayTime = 0, firstChunk = true, settled = false

        const finish = () => {
          if (settled) return; settled = true
          ws.close(); vizRef.current?.stop()
          setTtsState('idle'); setStatus(''); setStatusType(''); resolve()
        }
        const fail = (msg: string) => {
          if (settled) return; settled = true
          ws.close(); vizRef.current?.stop()
          ttsDisabled.current = true
          reportTtsError(msg)
          setTtsState('idle'); setStatus(''); setStatusType('')
          resolve()
        }
        const scheduleChunk = (pcm: Float32Array) => {
          if (firstChunk) {
            setLatencyMs(Math.round(performance.now() - startMark))
            firstChunk = false; nextPlayTime = audioCtx.currentTime + 0.02
            setTtsState('playing'); setStatus('▶ Playing...'); setStatusType('playing')
            vizRef.current?.start(analyserRef.current!)
          }
          const buf = audioCtx.createBuffer(1, pcm.length, SAMPLE_RATE)
          buf.copyToChannel(pcm, 0)
          const src = audioCtx.createBufferSource()
          src.buffer = buf; src.connect(analyserRef.current!); src.start(nextPlayTime)
          nextPlayTime += buf.duration
        }

        ws.onopen = () => {
          setStatus('Synthesizing...')
          ws.send(JSON.stringify({
            context_id: crypto.randomUUID(),
            model_id: 'sonic-3',
            transcript: clean,
            voice: { mode: 'id', id: activeVoice },
            output_format: { container: 'raw', encoding: 'pcm_f32le', sample_rate: SAMPLE_RATE },
            continue: false,
          }))
        }
        ws.onmessage = (e) => {
          if (e.data instanceof ArrayBuffer) {
            scheduleChunk(new Float32Array(e.data))
          } else {
            try {
              const msg = JSON.parse(e.data as string) as { type?: string; data?: string }
              if (msg.type === 'error' || msg.type === 'done') {
                if (firstChunk) fail(`TTS error: ${JSON.stringify(msg)}`)
                else { setTimeout(finish, Math.max(50, (nextPlayTime - audioCtx.currentTime) * 1000 + 150)) }
                return
              }
              if (msg.data) {
                const bin = atob(msg.data); const bytes = new Uint8Array(bin.length)
                for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
                scheduleChunk(new Float32Array(bytes.buffer))
              }
            } catch { /* ignore */ }
          }
        }
        ws.onerror = () => fail('Connection failed')
        ws.onclose = () => {
          if (firstChunk) { fail('No audio received'); return }
          setTimeout(finish, Math.max(50, (nextPlayTime - audioCtx.currentTime) * 1000 + 150))
        }
      } catch (err) {
        ttsDisabled.current = true
        reportTtsError(err instanceof Error ? err.message : 'AudioContext error')
        setTtsState('idle'); setStatus(''); setStatusType('')
        resolve()
      }
    })
  }, [reportTtsError])

  const handleInterviewerMessage = useCallback(async (message: string, heckleText: string | null, res?: RespondResponse) => {
    addMessage('interviewer', message)

    // Show wise guy on only 30% of questions, and only if enabled
    const effectiveHeckle = (heckleText && wiseGuyEnabledRef.current && Math.random() < 0.3)
      ? heckleText : null
    if (effectiveHeckle) {
      addMessage('heckle', effectiveHeckle)
      onHeckle?.(effectiveHeckle)
    }

    if (res) {
      onSectionsTouched?.(res.sectionsTouched)
      onQuestionsUpdate?.(res.questionsRemaining)
      setQuestionsRemaining(res.questionsRemaining)
      if (res.phase !== 'interviewing') {
        onPhaseChange?.(res.phase, res.draftFiles)
      }
    }
    setInputText('')
    setBoxState('interviewer-speaking')
    if (effectiveHeckle) {
      await speakText(effectiveHeckle, WISE_GUY_VOICE_ID)
    }
    await speakText(message)
    setBoxState('waiting')
    requestAnimationFrame(() => inputRef.current?.focus())
  }, [addMessage, speakText, onHeckle, onSectionsTouched, onQuestionsUpdate, onPhaseChange])

  const report = (errorType: string, err: unknown) => {
    const msg = err instanceof Error ? err.message : String(err ?? 'Unknown error')
    console.error(`[InterviewBox] ${errorType}:`, err)
    postError(errorType, msg).catch(() => { /* best-effort */ })
    return msg
  }

  // Catch any unhandled promise rejections and surface them
  useEffect(() => {
    const handler = (e: PromiseRejectionEvent) => {
      const msg = report('unhandled_rejection', e.reason)
      setStatus(`Unhandled error: ${msg}`)
      setStatusType('error')
    }
    window.addEventListener('unhandledrejection', handler)
    return () => window.removeEventListener('unhandledrejection', handler)
  }, [])

  // Start interview on mount
  useEffect(() => {
    let cancelled = false
    createInterview().then(result => {
      if (cancelled) return
      const id = result.sessionId
      setSessionId(id)
      onSessionCreated?.(id)
      onQuestionsUpdate?.(result.questionsRemaining)
      setQuestionsRemaining(result.questionsRemaining)
      setQuestionsTotal(result.questionsTotal)
      if (result.heckle) { onHeckle?.(result.heckle) }
      void handleInterviewerMessageRef.current(result.message, result.heckle ?? null)
    }).catch(err => {
      if (cancelled) return
      report('interview_start_failed', err)
      setBoxState('failed')
    })
    return () => { cancelled = true }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleRetry = () => {
    setBoxState('loading')
    setStatus('')
    let cancelled = false
    createInterview().then(result => {
      if (cancelled) return
      const id = result.sessionId
      setSessionId(id)
      onSessionCreated?.(id)
      onQuestionsUpdate?.(result.questionsRemaining)
      setQuestionsRemaining(result.questionsRemaining)
      setQuestionsTotal(result.questionsTotal)
      if (result.heckle) { onHeckle?.(result.heckle) }
      void handleInterviewerMessageRef.current(result.message, result.heckle ?? null)
    }).catch(err => {
      if (cancelled) return
      report('interview_start_failed', err)
      setBoxState('failed')
    })
    return () => { cancelled = true }
  }

  const showNoSession = () => {
    const msg = 'Action attempted with no session — interview may have failed to start'
    report('no_session', new Error(msg))
    setStatus('Interview not started — please refresh the page.')
    setStatusType('error')
  }

  const handleSubmit = useCallback(async (text: string) => {
    if (!text.trim()) return
    if (!sessionIdRef.current) { showNoSession(); return }
    const sid = sessionIdRef.current

    setBoxState('user-speaking')
    addMessage('user', text)
    setInputText('')

    setBoxState('submitting')
    setStatus('Thinking...')
    setStatusType('')

    try {
      const res = await respondToInterview(sid, text)
      setStatus('')
      if (res.phase !== 'interviewing') {
        setPhase(res.phase)
      }
      await handleInterviewerMessage(res.message, res.heckle, res)
    } catch (err) {
      const msg = report('submit_failed', err)
      setStatus(`Error: ${msg}`)
      setStatusType('error')
      setBoxState('waiting')
    }
  }, [addMessage, handleInterviewerMessage])

  const handleSkipQuestion = useCallback(async () => {
    if (boxState !== 'waiting') return
    if (!sessionIdRef.current) { showNoSession(); return }
    const sid = sessionIdRef.current
    setBoxState('submitting')
    setStatus('Skipping...')
    try {
      const res = await skipQuestion(sid)
      setStatus('')
      onQuestionsUpdate?.(res.questionsRemaining)
      setQuestionsRemaining(res.questionsRemaining)
      await handleInterviewerMessage(res.message, res.heckle)
    } catch (err) {
      const msg = report('skip_failed', err)
      setStatus(`Error: ${msg}`)
      setStatusType('error')
      setBoxState('waiting')
    }
  }, [boxState, handleInterviewerMessage, onQuestionsUpdate])

  const handlePause = useCallback(() => {
    if (!sessionIdRef.current) { showNoSession(); return }
    // Navigate immediately — ReviewPage will call the pause API and show a spinner
    onPhaseChange?.('reviewing')
  }, [onPhaseChange])

  const handlePlay = useCallback(() => {
    if (boxState !== 'waiting') return
    const text = inputText.trim()
    if (text) void handleSubmit(text)
  }, [handleSubmit, boxState, inputText])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handlePlay() }
  }

  const isBusy = boxState !== 'waiting'

  const handleInterviewerMessageRef = useRef(handleInterviewerMessage)
  useEffect(() => { handleInterviewerMessageRef.current = handleInterviewerMessage }, [handleInterviewerMessage])
  const onQuestionsUpdateRef = useRef(onQuestionsUpdate)
  useEffect(() => { onQuestionsUpdateRef.current = onQuestionsUpdate }, [onQuestionsUpdate])

  useImperativeHandle(ref, () => ({
    get sessionId() { return sessionIdRef.current },
    resumeWithQuestion(message, heckle, questionsRemaining) {
      setPhase('interviewing')
      onQuestionsUpdateRef.current?.(questionsRemaining)
      setQuestionsRemaining(questionsRemaining)
      void handleInterviewerMessageRef.current(message, heckle)
    },
  }))

  return (
    <div className="interview-box">
      {messages.length > 0 && (
        <div className="chat-area" ref={chatAreaRef}>
          {messages.map(msg => (
            <ChatBubble
              key={msg.id}
              role={msg.role}
              text={msg.text}
            />
          ))}
          <div ref={chatEndRef} />
        </div>
      )}

      {phase === 'interviewing' && boxState === 'failed' && (
        <div className="voicebox-box voicebox-failed">
          <p className="voicebox-failed-msg">Could not connect to the interview server.</p>
          <button className="btn-primary" onClick={handleRetry}>Try again</button>
        </div>
      )}

      {phase === 'interviewing' && boxState !== 'failed' && (
        <div className="voicebox-box">
          <div className="voicebox-input-area">
            <textarea
              ref={inputRef}
              value={inputText}
              onChange={e => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              className="voicebox-input"
              aria-label="Your answer"
              rows={3}
              disabled={isBusy}
            />
          </div>
          <div className="voicebox-toolbar">
            <span className="voicebox-hint">
              ↵ send
              {latencyMs !== null && <span className="voicebox-latency">{latencyMs}ms</span>}
            </span>
            <div className="voicebox-toolbar-right">
              <label className="wise-guy-toggle" title={wiseGuyEnabled ? 'Silence the wise guy' : 'Let the wise guy speak'}>
                <span className="wise-guy-label">wise guy</span>
                <span className={`wise-guy-switch${wiseGuyEnabled ? ' wise-guy-switch--on' : ''}`}
                  role="switch"
                  aria-checked={wiseGuyEnabled}
                  onClick={() => {
                    wiseGuyEnabledRef.current = !wiseGuyEnabledRef.current
                    setWiseGuyEnabled(v => !v)
                  }}
                />
              </label>
              <button
                className="voicebox-reset"
                onClick={handleSkipQuestion}
                disabled={isBusy}
                title="Skip this question and move to new topics"
                aria-label="Skip question"
              >
                skip
              </button>
              {questionsRemaining !== null && questionsTotal !== null && (questionsTotal - questionsRemaining) >= 2 && (
                <button
                  className="voicebox-reset"
                  onClick={handlePause}
                  disabled={isBusy}
                  title="End the interview and generate your profile"
                  aria-label="End interview"
                >
                  end interview
                </button>
              )}
              <MicButton
                getBaseText={() => inputText.trim()}
                onTranscript={t => setInputText(t)}
                onEnd={() => { /* user submits manually */ }}
                onError={msg => { setStatus(msg); setStatusType('error') }}
                disabled={isBusy}
              />
              <SpeakButton state={ttsState} onClick={handlePlay} disabled={isBusy} />
            </div>
          </div>
        </div>
      )}

      <Visualizer ref={vizRef} />

      {status && (
        <div className="voicebox-status" style={{
          color: statusType === 'error'   ? '#ff6b6b'
               : statusType === 'playing' ? 'var(--accent)'
               : 'rgba(245,240,232,0.4)',
        }}>
          {status}
        </div>
      )}
    </div>
  )
})

export default InterviewBox
