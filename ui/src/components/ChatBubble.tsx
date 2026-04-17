export type ChatRole = 'interviewer' | 'user' | 'heckle'

interface Props {
  role: ChatRole
  text: string
}

function stripTags(text: string): string {
  if (!text) return ''
  return text
    .replace(/<emotion[^>]*\/>/g, '')
    .replace(/\[laughter\]/gi, '')
    .replace(/\[clears throat\]/gi, '')
    .trim()
}

export default function ChatBubble({ role, text }: Props) {
  return (
    <div className={`chat-bubble chat-bubble--${role}`}>
      {role === 'heckle' && <span className="chat-bubble-heckle-label">wise guy</span>}
      <p>{stripTags(text)}</p>
    </div>
  )
}
