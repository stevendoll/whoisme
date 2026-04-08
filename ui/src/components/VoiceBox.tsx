import { useState, useEffect, useRef, useCallback } from 'react'
import { getIcebreaker, postTurn, postError } from '../lib/api'
import type { ChatMessage, Speaker } from '../lib/types'
import MicButton from './MicButton'
import SpeakButton from './SpeakButton'
import Visualizer, { type VisualizerHandle } from './Visualizer'
import ChatBubble from './ChatBubble'

const CARTESIA_API_KEY = import.meta.env.VITE_CARTESIA_API_KEY as string
const SAMPLE_RATE = 44100

// ── Voice assignment ──────────────────────────────────────────────────────────
// VITE_CARTESIA_VOICES: comma-separated list of voice IDs to pick from randomly.
// Falls back to legacy single-voice env vars when the list is absent or too short.

// Sonic 3 voices — all support [laughter] and emotion controls
const SONIC3_VOICES = [
  '0834f3df-e650-4766-a20c-5a93a43aa6e3', // Leo
  '6776173b-fd72-460d-89b3-d85812ee518d', // Jace
  'c961b81c-a935-4c17-bfb3-ba2239de8c2f', // Kyle
  'f4a3a8e4-694c-4c45-9ca0-27caf97901b5', // Gavin
  'cbaf8084-f009-4838-a096-07ee2e6612b1', // Maya
  '6ccbfb76-1fc6-48f7-b71d-91ac6298247b', // Tessa
  'cc00e582-ed66-4004-8336-0175b85c85f6', // Dana
  '26403c37-80c1-4a1a-8692-540551ca2ae5', // Marian
]


function assignVoices(): Record<Speaker, string> {
  const envPool = (import.meta.env.VITE_CARTESIA_VOICES as string ?? '')
    .split(',').map(v => v.trim()).filter(Boolean)
  const pool = envPool.length >= 3 ? envPool : SONIC3_VOICES
  const shuffled = [...pool].sort(() => Math.random() - 0.5)
  return { visitor: shuffled[0], consultant1: shuffled[1], consultant2: shuffled[2] }
}

function stripSsml(text: string): string {
  return text
    .replace(/<emotion[^>]*\/?>/gi, '')
    .replace(/<\/emotion>/gi, '')
    .replace(/\[clears throat\]/gi, '')
  // [laughter] intentionally kept — Sonic 3 (2025-01-13) generates it natively
    .replace(/\s{2,}/g, ' ')
    .trim()
}

const pause = (ms: number) => new Promise<void>(r => setTimeout(r, ms))

function formatText(text: string): string {
  return text
    .replace(/\[laughter\]/gi, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
    .replace(/\bknowing\b/gi, '<em>knowing</em>')
}

function newConversationId() {
  const id = crypto.randomUUID()
  sessionStorage.setItem('t12n_conversation_id', id)
  sessionStorage.removeItem('t12n_order')
  return id
}

function newVoiceIds() {
  const voices = assignVoices()
  sessionStorage.setItem('t12n_voices', JSON.stringify(voices))
  return voices
}

function getStoredOrder(): number {
  return parseInt(sessionStorage.getItem('t12n_order') ?? '0', 10) || 0
}

function saveOrder(n: number) {
  sessionStorage.setItem('t12n_order', String(n))
}

export default function VoiceBox() {
  const [conversationId, setConversationId] = useState(() => {
    const stored = sessionStorage.getItem('t12n_conversation_id')
    if (stored) return stored
    return newConversationId()
  })

  // Randomly assigned once per session, persisted across page reloads
  const [voiceIds, setVoiceIds] = useState<Record<Speaker, string>>(() => {
    const stored = sessionStorage.getItem('t12n_voices')
    if (stored) { try { return JSON.parse(stored) as Record<Speaker, string> } catch { /* fall through */ } }
    return newVoiceIds()
  })

  const orderRef = useRef(getStoredOrder())

  type ConvState = 'idle' | 'visitor-speaking' | 'loading' | 'consultant-speaking' | 'waiting'
  const [convState,  setConvState]  = useState<ConvState>('idle')
  const [ttsState,   setTtsState]   = useState<'idle' | 'connecting' | 'playing'>('idle')
  const [messages,   setMessages]   = useState<ChatMessage[]>([])
  const [status,     setStatus]     = useState('')
  const [statusType, setStatusType] = useState<'' | 'error' | 'playing'>('')
  const [latencyMs,  setLatencyMs]  = useState<number | null>(null)

  const inputRef          = useRef<HTMLDivElement>(null)
  const audioCtxRef       = useRef<AudioContext | null>(null)
  const analyserRef       = useRef<AnalyserNode | null>(null)
  const vizRef            = useRef<VisualizerHandle>(null)
  const messagesEndRef    = useRef<HTMLDivElement>(null)
  const voiceboxBoxRef    = useRef<HTMLDivElement>(null)
  const ttsDisabled       = useRef(false)
  const ttsErrorReported  = useRef(false)

  useEffect(() => {
    getIcebreaker()
      .then(ib => { if (inputRef.current) inputRef.current.innerHTML = formatText(ib.text) })
      .catch(() => {
        if (inputRef.current && !inputRef.current.textContent?.trim())
          inputRef.current.innerHTML = formatText('The gap between knowing and doing is costing us.')
      })
  }, [])

  useEffect(() => {
    if (messages.length === 0) return
    requestAnimationFrame(() => {
      voiceboxBoxRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    })
  }, [messages])

  const getInputText = () => inputRef.current?.textContent?.trim() ?? ''

  const playPopSound = useCallback(() => {
    try {
      if (!audioCtxRef.current) audioCtxRef.current = new AudioContext()
      const ctx = audioCtxRef.current
      void ctx.resume()
      const osc  = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'sine'
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.frequency.setValueAtTime(920, ctx.currentTime)
      osc.frequency.exponentialRampToValueAtTime(520, ctx.currentTime + 0.09)
      gain.gain.setValueAtTime(0.07, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.14)
      osc.start(ctx.currentTime)
      osc.stop(ctx.currentTime + 0.14)
    } catch { /* ignore */ }
  }, [])

  const reportTtsError = useCallback((message: string) => {
    if (ttsErrorReported.current) return
    ttsErrorReported.current = true
    postError('tts_failure', message).catch(() => { /* best-effort */ })
  }, [])

  const speakAs = useCallback((speaker: Speaker, text: string, overrideVoiceId?: string, emotion?: string): Promise<void> => {
    return new Promise((resolve, _reject) => {
      const voiceId = overrideVoiceId ?? voiceIds[speaker]
      const clean   = stripSsml(text)

      const silentPlayback = () => {
        setTtsState('playing'); setStatus('▶ Playing...'); setStatusType('playing')
        const ms = Math.max(800, clean.length * 45)
        setTimeout(() => { setTtsState('idle'); setStatus(''); setStatusType(''); resolve() }, ms)
      }

      if (!CARTESIA_API_KEY || !voiceId || ttsDisabled.current) {
        silentPlayback()
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
          const payload: Record<string, unknown> = {
            context_id: crypto.randomUUID(), model_id: 'sonic-3', transcript: clean,
            voice: { mode: 'id', id: voiceId },
            output_format: { container: 'raw', encoding: 'pcm_f32le', sample_rate: SAMPLE_RATE },
          }
          if (emotion) payload['generation_config'] = { emotion }
          payload['continue'] = false
          ws.send(JSON.stringify(payload))
        }
        ws.onmessage = (e) => {
          if (e.data instanceof ArrayBuffer) {
            scheduleChunk(new Float32Array(e.data))
          } else {
            try {
              const msg = JSON.parse(e.data as string) as { type?: string; data?: string }
              if (msg.type === 'error' || msg.type === 'done') {
                if (firstChunk) fail(`TTS error: ${(msg as Record<string,unknown>).error ?? JSON.stringify(msg)}`)
                else { const rem = Math.max(50, (nextPlayTime - audioCtx.currentTime) * 1000 + 150); setTimeout(finish, rem) }
                return
              }
              if (msg.data) {
                const bin = atob(msg.data); const bytes = new Uint8Array(bin.length)
                for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
                scheduleChunk(new Float32Array(bytes.buffer))
              }
            } catch (err) { console.error('WS msg error:', err) }
          }
        }
        ws.onerror = () => fail('Connection failed')
        ws.onclose = () => {
          if (firstChunk) { fail('No audio received'); return }
          const rem = Math.max(50, (nextPlayTime - audioCtx.currentTime) * 1000 + 150)
          setTimeout(finish, rem)
        }
      } catch (err) {
        ttsDisabled.current = true
        reportTtsError(err instanceof Error ? err.message : 'AudioContext error')
        setTtsState('idle'); setStatus(''); setStatusType('')
        resolve()
      }
    })
  }, [voiceIds, reportTtsError])

  const addBubble = useCallback((speaker: Speaker, text: string) => {
    setMessages(prev => [...prev, { id: crypto.randomUUID(), speaker, text }])
  }, [])

  const handleSubmit = useCallback(async (text: string) => {
    if (!text.trim()) return
    const visitorOrder = orderRef.current

    try {
      setConvState('visitor-speaking')
      await speakAs('visitor', text)

      playPopSound()
      addBubble('visitor', text)
      if (inputRef.current) inputRef.current.innerHTML = ''

      setConvState('loading')
      setStatus('Alex and Jamie are thinking...')
      setStatusType('')

      const [response] = await Promise.all([
        postTurn(conversationId, { order: visitorOrder, text, speaker: 'visitor', voices: voiceIds }),
        pause(2000),
      ])

      const replies = response.consultantReplies ?? []
      orderRef.current = visitorOrder + 1 + replies.length
      saveOrder(orderRef.current)

      setStatus('')
      setConvState('consultant-speaking')

      for (let i = 0; i < replies.length; i++) {
        const reply = replies[i]
        if (i > 0) await pause(2000)
        playPopSound()
        addBubble(reply.speaker, reply.text)
        await speakAs(reply.speaker, reply.text, reply.voiceId, reply.emotion)
      }

      setConvState('waiting')
      requestAnimationFrame(() => inputRef.current?.focus())

    } catch (err) {
      setStatus(`Error: ${err instanceof Error ? err.message : 'Unknown error'}`)
      setStatusType('error')
      setConvState('waiting')
    }
  }, [conversationId, voiceIds, speakAs, playPopSound, addBubble])

  const isBusy = convState !== 'idle' && convState !== 'waiting'

  const handlePlay = useCallback(() => {
    if (convState !== 'idle' && convState !== 'waiting') return
    const text = getInputText()
    if (text) void handleSubmit(text)
  }, [handleSubmit, convState])

  const handleReset = useCallback(() => {
    if (isBusy) return
    setMessages([])
    orderRef.current = 0
    ttsDisabled.current = false
    ttsErrorReported.current = false
    setStatus('')
    setStatusType('')
    setConvState('idle')
    setConversationId(newConversationId())
    setVoiceIds(newVoiceIds())
    if (inputRef.current) inputRef.current.innerHTML = ''
    getIcebreaker()
      .then(ib => { if (inputRef.current) inputRef.current.innerHTML = formatText(ib.text) })
      .catch(() => { if (inputRef.current) inputRef.current.innerHTML = formatText('The gap between knowing and doing is costing us.') })
  }, [isBusy])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handlePlay() }
  }

  return (
    <div className="voicebox">
      {messages.length > 0 && (
        <div className="chat-area">
          {messages.map(msg => (
            <ChatBubble key={msg.id} speaker={msg.speaker} text={msg.text} />
          ))}
          <div ref={messagesEndRef} />
        </div>
      )}

      <div ref={voiceboxBoxRef} className="voicebox-box">
        <div className="voicebox-input-area">
          <div
            ref={inputRef}
            contentEditable
            suppressContentEditableWarning
            onKeyDown={handleKeyDown}
            className="voicebox-input"
          />
        </div>
        <div className="voicebox-toolbar">
          <span className="voicebox-hint">
            ↵ enter and let's talk
            {latencyMs !== null && <span className="voicebox-latency">{latencyMs}ms</span>}
          </span>
          <div className="voicebox-toolbar-right">
            <button
              className="voicebox-reset"
              onClick={handleReset}
              disabled={isBusy}
              title="New conversation"
              aria-label="New conversation"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
                <path d="M17.65 6.35A7.958 7.958 0 0 0 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
              </svg>
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
}
