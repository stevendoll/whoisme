interface Props {
  currentStep: 'interview' | 'review' | 'profile' | 'publish'
  questionsLeft?: number
}

const STEPS: Array<{ key: string; label: string; href: string }> = [
  { key: 'interview', label: 'Interview', href: '#/interview' },
  { key: 'review',    label: 'Review',    href: '#/review' },
  { key: 'profile',   label: 'Profile',   href: '#/profile' },
  { key: 'publish',   label: 'Publish',   href: '#/profile' },
]

const ORDER = ['interview', 'review', 'profile', 'publish']

export default function ProgressSteps({ currentStep, questionsLeft }: Props) {
  const currentIdx = ORDER.indexOf(currentStep)

  return (
    <nav className="progress-steps" aria-label="Progress">
      {STEPS.map(({ key, label, href }, idx) => {
        const isDone   = idx < currentIdx
        const isActive = idx === currentIdx
        const state    = isDone ? 'done' : isActive ? 'active' : 'future'

        const inner = (
          <span className="progress-step-inner">
            <span className="progress-step-dot" />
            <span className="progress-step-label">
              {label}
              {isActive && key === 'interview' && questionsLeft !== undefined && (
                <span className="progress-step-sub">{questionsLeft} left</span>
              )}
            </span>
          </span>
        )

        return (
          <span key={key} className="progress-step-wrap">
            {idx > 0 && <span className="progress-connector" aria-hidden="true" />}
            <span className={`progress-step progress-step--${state}`}>
              {isDone ? (
                <a href={href} className="progress-step-link">{inner}</a>
              ) : (
                inner
              )}
            </span>
          </span>
        )
      })}
    </nav>
  )
}
