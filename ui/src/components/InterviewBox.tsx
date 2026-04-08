import { useState, useEffect, useRef, useCallback, forwardRef, useImperativeHandle } from 'react'
import { createInterview, respondToInterview, skipQuestion, pauseInterview } from '../lib/api'
import type { InterviewPhase, RespondResponse } from '../lib/types'
import MicButton from './MicButton'
import SpeakButton from './SpeakButton'
import Visualizer, { type VisualizerHandle } from './Visualizer'
import ChatBubble from './ChatBubble'
import HeckleToast from './HeckleToast'
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
  role: 'interviewer' | 'user'
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
  const [heckle, setHeckle] = useState<string | null>(null)
  const [status, setStatus] = useState('')
  const [statusType, setStatusType] = useState<'' | 'error' | 'playing'>('')
  const [latencyMs, setLatencyMs] = useState<number | null>(null)

  type BoxState = 'loading' | 'interviewer-speaking' | 'waiting' | 'user-speaking' | 'submitting'
  const [boxState, setBoxState] = useState<BoxState>('loading')
  const [ttsState, setTtsState] = useState<'idle' | 'connecting' | 'playing'>('idle')

  const inputRef         = useRef<HTMLDivElement>(null)
  const audioCtxRef      = useRef<AudioContext | null>(null)
  const analyserRef      = useRef<AnalyserNode | null>(null)
  const vizRef           = useRef<VisualizerHandle>(null)
  const chatEndRef       = useRef<HTMLDivElement>(null)
  const chatAreaRef      = useRef<HTMLDivElement>(null)
  const ttsDisabled      = useRef(false)
  const ttsErrorReported = useRef(false)
  const voiceId          = useRef(pickInterviewerVoice())
  const sessionIdRef     = useRef<string | null>(null)

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

  const speakText = useCallback((text: string): Promise<void> => {
    return new Promise(resolve => {
      if (!CARTESIA_API_KEY || !voiceId.current || ttsDisabled.current) {
        setTtsState('playing'); setStatus('▶ Playing...'); setStatusType('playing')
        const ms = Math.max(800, text.length * 45)
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
            transcript: text,
            voice: { mode: 'id', id: voiceId.current },
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
    if (heckleText) {
      setHeckle(heckleText)
      onHeckle?.(heckleText)
    }
    if (res) {
      onSectionsTouched?.(res.sectionsTouched)
      onQuestionsUpdate?.(res.questionsRemaining)
      if (res.phase !== 'interviewing') {
        onPhaseChange?.(res.phase)
      }
    }
    setBoxState('interviewer-speaking')
    await speakText(message)
    setBoxState('waiting')
    requestAnimationFrame(() => inputRef.current?.focus())
  }, [addMessage, speakText, onHeckle, onSectionsTouched, onQuestionsUpdate, onPhaseChange])

  // Start interview on mount
  useEffect(() => {
    let cancelled = false
    createInterview().then(async result => {
      if (cancelled) return
      const id = result.sessionId
      setSessionId(id)
      onSessionCreated?.(id)
      onQuestionsUpdate?.(result.questionsRemaining)
      await handleInterviewerMessage(result.message, result.heckle)
    }).catch(err => {
      if (cancelled) return
      setStatus(`Error: ${err instanceof Error ? err.message : 'Failed to start interview'}`)
      setStatusType('error')
      setBoxState('waiting')
    })
    return () => { cancelled = true }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const getInputText = () => inputRef.current?.textContent?.trim() ?? ''

  const handleSubmit = useCallback(async (text: string) => {
    if (!text.trim() || !sessionIdRef.current) return
    const sid = sessionIdRef.current

    setBoxState('user-speaking')
    addMessage('user', text)
    if (inputRef.current) inputRef.current.innerHTML = ''

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
      setStatus(`Error: ${err instanceof Error ? err.message : 'Unknown error'}`)
      setStatusType('error')
      setBoxState('waiting')
    }
  }, [addMessage, handleInterviewerMessage])

  const handleSkipQuestion = useCallback(async () => {
    if (!sessionIdRef.current || boxState !== 'waiting') return
    const sid = sessionIdRef.current
    setBoxState('submitting')
    setStatus('Skipping...')
    try {
      const res = await skipQuestion(sid)
      setStatus('')
      onQuestionsUpdate?.(res.questionsRemaining)
      await handleInterviewerMessage(res.message, res.heckle)
    } catch (err) {
      setStatus(`Error: ${err instanceof Error ? err.message : 'Unknown error'}`)
      setStatusType('error')
      setBoxState('waiting')
    }
  }, [boxState, handleInterviewerMessage, onQuestionsUpdate])

  const handlePause = useCallback(async () => {
    if (!sessionIdRef.current) return
    setBoxState('submitting')
    setStatus('Generating drafts...')
    try {
      const res = await pauseInterview(sessionIdRef.current)
      setStatus('')
      setPhase('reviewing')
      onPhaseChange?.('reviewing', res.draftFiles, res.skippedSections)
    } catch (err) {
      setStatus(`Error: ${err instanceof Error ? err.message : 'Unknown error'}`)
      setStatusType('error')
      setBoxState('waiting')
    }
  }, [onPhaseChange])

  const handlePlay = useCallback(() => {
    if (boxState !== 'waiting') return
    const text = getInputText()
    if (text) void handleSubmit(text)
  }, [handleSubmit, boxState])

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
      void handleInterviewerMessageRef.current(message, heckle)
    },
  }))

  return (
    <div className="interview-box">
      <HeckleToast text={heckle} key={heckle} />

      {messages.length > 0 && (
        <div className="chat-area" ref={chatAreaRef}>
          {messages.map(msg => (
            <ChatBubble
              key={msg.id}
              speaker={msg.role === 'interviewer' ? 'consultant1' : 'visitor'}
              text={msg.text}
            />
          ))}
          <div ref={chatEndRef} />
        </div>
      )}

      {phase === 'interviewing' && (
        <div className="voicebox-box">
          <div className="voicebox-input-area">
            <div
              ref={inputRef}
              contentEditable={!isBusy}
              suppressContentEditableWarning
              onKeyDown={handleKeyDown}
              className="voicebox-input"
              aria-label="Your answer"
            />
          </div>
          <div className="voicebox-toolbar">
            <span className="voicebox-hint">
              ↵ send
              {latencyMs !== null && <span className="voicebox-latency">{latencyMs}ms</span>}
            </span>
            <div className="voicebox-toolbar-right">
              <button
                className="voicebox-reset"
                onClick={handleSkipQuestion}
                disabled={isBusy}
                title="Skip this question"
                aria-label="Skip question"
              >
                skip
              </button>
              <button
                className="voicebox-reset"
                onClick={handlePause}
                disabled={isBusy}
                title="Pause and review drafts"
                aria-label="Pause interview"
              >
                pause
              </button>
              <MicButton
                onTranscript={t => { if (inputRef.current) inputRef.current.textContent = t }}
                onEnd={handlePlay}
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
