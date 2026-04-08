/**
 * Minimal Cartesia WebSocket TTS — plays audio, resolves when done.
 * No UI state management; use VoiceBox's speakAs for the full experience.
 */

const SAMPLE_RATE = 44100

export interface GenerationConfig {
  emotion?: string
  speed?: number
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

export function playTts(
  apiKey: string,
  voiceId: string,
  text: string,
  audioCtx: AudioContext,
  generationConfig?: GenerationConfig,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const clean = stripSsml(text)

    if (!apiKey || !voiceId) {
      const ms = Math.max(800, clean.length * 45)
      setTimeout(resolve, ms)
      return
    }

    const wsUrl = `wss://api.cartesia.ai/tts/websocket?api_key=${apiKey}&cartesia_version=2025-04-16`
    const ws    = new WebSocket(wsUrl)
    ws.binaryType = 'arraybuffer'

    let nextPlayTime = 0
    let firstChunk   = true
    let settled      = false

    const finish = () => {
      if (settled) return
      settled = true
      ws.close()
      resolve()
    }

    const fail = (msg: string) => {
      if (settled) return
      settled = true
      ws.close()
      reject(new Error(msg))
    }

    const scheduleChunk = (pcm: Float32Array) => {
      if (firstChunk) {
        firstChunk   = false
        nextPlayTime = audioCtx.currentTime + 0.02
      }
      const buf = audioCtx.createBuffer(1, pcm.length, SAMPLE_RATE)
      buf.copyToChannel(pcm, 0)
      const src = audioCtx.createBufferSource()
      src.buffer = buf
      src.connect(audioCtx.destination)
      src.start(nextPlayTime)
      nextPlayTime += buf.duration
    }

    ws.onopen = () => {
      const payload: Record<string, unknown> = {
        context_id:    crypto.randomUUID(),
        model_id:      'sonic-3',
        transcript:    clean,
        voice:         { mode: 'id', id: voiceId },
        output_format: { container: 'raw', encoding: 'pcm_f32le', sample_rate: SAMPLE_RATE },
      }
      if (generationConfig && Object.keys(generationConfig).length > 0) {
        payload['generation_config'] = generationConfig
      }
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
            if (firstChunk) {
              fail(`TTS error: ${JSON.stringify(msg)}`)
            } else {
              const remaining = Math.max(50, (nextPlayTime - audioCtx.currentTime) * 1000 + 150)
              setTimeout(finish, remaining)
            }
            return
          }
          if (msg.data) {
            const bin   = atob(msg.data)
            const bytes = new Uint8Array(bin.length)
            for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
            scheduleChunk(new Float32Array(bytes.buffer))
          }
        } catch (err) { console.error('TTS WS error:', err) }
      }
    }

    ws.onerror = () => fail('Connection failed')

    ws.onclose = () => {
      if (firstChunk) { fail('No audio received'); return }
      const remaining = Math.max(50, (nextPlayTime - audioCtx.currentTime) * 1000 + 150)
      setTimeout(finish, remaining)
    }
  })
}
