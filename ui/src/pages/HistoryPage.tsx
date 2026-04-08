import { useState, useEffect, useRef } from 'react'
import { getConversations, getConversationTurns } from '../lib/api'
import { playTts } from '../lib/tts'
import type { Conversation, Turn } from '../lib/types'
import Nav from '../components/Nav'

const CARTESIA_API_KEY = import.meta.env.VITE_CARTESIA_API_KEY as string

const SPEAKER_LABEL: Record<string, string> = {
  visitor:     'You',
  consultant1: 'Alex',
  consultant2: 'Jamie',
}

const SPEAKER_COLOR: Record<string, string> = {
  visitor:     'var(--accent)',
  consultant1: '#d2a050',
  consultant2: '#9b85c8',
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit',
    })
  } catch { return iso }
}

export default function HistoryPage() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selected,      setSelected]      = useState<string | null>(null)
  const [turns,         setTurns]         = useState<Turn[]>([])
  const [loading,       setLoading]       = useState(true)
  const [turnsLoading,  setTurnsLoading]  = useState(false)
  const [replaying,     setReplaying]     = useState(false)
  const [replayIdx,     setReplayIdx]     = useState<number>(-1)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const stopRef     = useRef(false)

  useEffect(() => {
    getConversations()
      .then(r => setConversations(r.conversations))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const loadConversation = async (id: string) => {
    setSelected(id)
    setTurns([])
    setReplayIdx(-1)
    setTurnsLoading(true)
    try {
      const r = await getConversationTurns(id)
      setTurns(r.turns)
    } catch (e) {
      console.error(e)
    } finally {
      setTurnsLoading(false)
    }
  }

  const startReplay = async () => {
    if (replaying || turns.length === 0) return
    setReplaying(true)
    stopRef.current = false

    if (!audioCtxRef.current) audioCtxRef.current = new AudioContext()
    const ctx = audioCtxRef.current
    void ctx.resume()

    for (let i = 0; i < turns.length; i++) {
      if (stopRef.current) break
      const turn = turns[i]
      setReplayIdx(i)
      const voiceId = turn.voiceId ?? ''
      try {
        await playTts(CARTESIA_API_KEY, voiceId, turn.text, ctx)
      } catch (e) {
        console.warn('Replay TTS error:', e)
      }
      if (i < turns.length - 1) await new Promise(r => setTimeout(r, 600))
    }

    setReplaying(false)
    setReplayIdx(-1)
  }

  const stopReplay = () => {
    stopRef.current = true
    setReplaying(false)
    setReplayIdx(-1)
  }

  return (
    <>
      <Nav />
      <div className="history-page">
        <div className="history-sidebar">
          <div className="history-sidebar-header">
            <h2>Conversations</h2>
            <a href="#" className="history-back">← Back</a>
          </div>

          {loading && <p className="history-empty">Loading...</p>}
          {!loading && conversations.length === 0 && (
            <p className="history-empty">No conversations yet.</p>
          )}

          {conversations.map(c => (
            <button
              key={c.conversationId}
              className={`history-conv-item${selected === c.conversationId ? ' active' : ''}`}
              onClick={() => void loadConversation(c.conversationId)}
            >
              <span className="history-conv-date">{formatDate(c.createdAt)}</span>
              <span className="history-conv-preview">{c.preview}</span>
            </button>
          ))}
        </div>

        <div className="history-main">
          {!selected && (
            <div className="history-empty-state">
              <p>Select a conversation to view it.</p>
            </div>
          )}

          {selected && (
            <>
              <div className="history-toolbar">
                <button
                  className={`history-replay-btn${replaying ? ' active' : ''}`}
                  onClick={replaying ? stopReplay : () => void startReplay()}
                >
                  {replaying ? '■ Stop' : '▶ Replay'}
                </button>
              </div>

              {turnsLoading && <p className="history-empty">Loading turns...</p>}

              <div className="history-turns">
                {turns.map((turn, idx) => (
                  <div
                    key={`${turn.conversationId}-${turn.order}`}
                    className={`history-turn${idx === replayIdx ? ' playing' : ''}`}
                    style={{ alignSelf: turn.speaker === 'visitor' ? 'flex-start' : 'flex-end' }}
                  >
                    <span
                      className="history-turn-speaker"
                      style={{ color: SPEAKER_COLOR[turn.speaker] ?? 'var(--accent)' }}
                    >
                      {SPEAKER_LABEL[turn.speaker] ?? turn.speaker}
                    </span>
                    <p>{turn.text}</p>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  )
}
