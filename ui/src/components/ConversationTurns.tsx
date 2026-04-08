import type { Turn } from '../lib/types'

interface Props {
  turns: Turn[]
}

export default function ConversationTurns({ turns }: Props) {
  if (turns.length <= 1) return null

  return (
    <div className="w-full max-w-[900px] mt-6 flex flex-col gap-2">
      {turns.slice(1).map((turn) => (
        <div
          key={`${turn.conversationId}-${turn.order}`}
          className={[
            'text-[0.8rem] leading-relaxed px-5 py-3 rounded-sm border border-[var(--border)]',
            turn.speaker === 'visitor'
              ? 'text-[rgba(245,240,232,0.6)] bg-[rgba(245,240,232,0.03)] self-end max-w-[80%]'
              : 'text-[var(--accent)] bg-[rgba(77,182,172,0.04)] self-start max-w-[80%]',
          ].join(' ')}
        >
          {turn.text}
        </div>
      ))}
    </div>
  )
}
