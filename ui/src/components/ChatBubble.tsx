import type { Speaker } from '../lib/types'

interface Props {
  speaker: Speaker
  text: string
}

const SPEAKER_META: Record<Speaker, { className: string }> = {
  visitor:     { className: 'chat-bubble--visitor' },
  consultant1: { className: 'chat-bubble--alex' },
  consultant2: { className: 'chat-bubble--jamie' },
}

// Strip Cartesia emotion/expression tags — they're for TTS only, not display
function stripTags(text: string): string {
  return text
    .replace(/<emotion[^>]*\/>/g, '')
    .replace(/\[laughter\]/gi, '')
    .replace(/\[clears throat\]/gi, '')
    .trim()
}

export default function ChatBubble({ speaker, text }: Props) {
  const { className } = SPEAKER_META[speaker]
  return (
    <div className={`chat-bubble ${className}`}>
      <p>{stripTags(text)}</p>
    </div>
  )
}
