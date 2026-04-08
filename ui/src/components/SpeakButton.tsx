interface Props {
  state: 'idle' | 'connecting' | 'playing'
  disabled?: boolean
  onClick: () => void
}

export default function SpeakButton({ state, disabled, onClick }: Props) {
  const label = state === 'idle' ? 'Play' : state === 'connecting' ? '...' : 'Playing'

  return (
    <button
      onClick={onClick}
      disabled={disabled || state !== 'idle'}
      className="play-btn"
    >
      <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
        <path d="M8 5v14l11-7z" />
      </svg>
      {label}
    </button>
  )
}
