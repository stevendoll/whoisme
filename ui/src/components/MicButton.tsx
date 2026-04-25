import { useState, useRef } from 'react'

interface Props {
  onTranscript: (text: string) => void
  onEnd: () => void
  onError: (msg: string) => void
  disabled?: boolean
  getBaseText?: () => string
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnySpeechRecognition = any

const SILENCE_TIMEOUT_MS = 5000

export default function MicButton({ onTranscript, onEnd, onError, disabled, getBaseText }: Props) {
  const [recording, setRecording] = useState(false)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null)
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const SR: AnySpeechRecognition = (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition
  if (!SR) return null

  const clearSilenceTimer = () => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current)
      silenceTimerRef.current = null
    }
  }

  const resetSilenceTimer = () => {
    clearSilenceTimer()
    silenceTimerRef.current = setTimeout(() => {
      recognitionRef.current?.stop()
    }, SILENCE_TIMEOUT_MS)
  }

  const toggle = () => {
    if (recording) {
      clearSilenceTimer()
      // eslint-disable-next-line @typescript-eslint/no-unsafe-call
      recognitionRef.current?.stop()
      return
    }
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    const rec = new SR()
    rec.continuous = true
    rec.interimResults = true
    rec.lang = 'en-US'
    recognitionRef.current = rec

    const baseText = getBaseText?.() ?? ''
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    rec.onresult = (e: any) => {
      resetSilenceTimer()
      // eslint-disable-next-line @typescript-eslint/no-unsafe-member-access, @typescript-eslint/no-unsafe-call
      const transcript = Array.from(e.results as ArrayLike<SpeechRecognitionResult>)
        .map(r => r[0].transcript).join('')
      onTranscript(baseText ? `${baseText} ${transcript}` : transcript)
    }
    rec.onend = () => {
      clearSilenceTimer()
      setRecording(false)
      // Do not call onTranscript here — onresult already fires the final transcript
      // and calling it again after submission clears the input causes stale text to reappear
      onEnd()
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    rec.onerror = (e: any) => {
      clearSilenceTimer()
      setRecording(false)
      // eslint-disable-next-line @typescript-eslint/no-unsafe-member-access
      onError(`Mic error: ${e.error}`)
    }
    setRecording(true)
    resetSilenceTimer()
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    rec.start()
  }

  return (
    <button
      onClick={toggle}
      disabled={disabled}
      title={recording ? 'Listening… click to stop' : 'Speak your answer'}
      className={`mic-btn${recording ? ' recording' : ''}`}
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 1a4 4 0 0 1 4 4v6a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4zm0 2a2 2 0 0 0-2 2v6a2 2 0 0 0 4 0V5a2 2 0 0 0-2-2zm7 8a1 1 0 0 1 1 1 8 8 0 0 1-7 7.938V21h2a1 1 0 0 1 0 2H9a1 1 0 0 1 0-2h2v-1.062A8 8 0 0 1 4 12a1 1 0 0 1 2 0 6 6 0 0 0 12 0 1 1 0 0 1 1-1z" />
      </svg>
    </button>
  )
}
