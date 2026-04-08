import { reactivateSection, skipSection } from '../lib/api'

const SECTIONS = [
  { id: 'identity',                   label: 'Identity' },
  { id: 'role-and-responsibilities',  label: 'Role & Responsibilities' },
  { id: 'current-projects',           label: 'Current Projects' },
  { id: 'team-and-relationships',     label: 'Team & Relationships' },
  { id: 'tools-and-systems',          label: 'Tools & Systems' },
  { id: 'communication-style',        label: 'Communication Style' },
  { id: 'goals-and-priorities',       label: 'Goals & Priorities' },
  { id: 'preferences-and-constraints', label: 'Preferences & Constraints' },
  { id: 'domain-knowledge',           label: 'Domain Knowledge' },
  { id: 'decision-log',               label: 'Decision Log' },
]

// Density → fill percentage. 5+ questions = 100%.
function toFillPct(density: number): number {
  return Math.min(100, Math.round((density / 5) * 100))
}

interface SectionFillProps {
  sessionId: string
  density: Record<string, number>
  skipped: string[]
  approved: string[]
  onUpdate: (skipped: string[]) => void
  disabled?: boolean
}

export default function SectionFill({ sessionId, density, skipped, approved, onUpdate, disabled }: SectionFillProps) {
  const skippedSet = new Set(skipped)
  const approvedSet = new Set(approved)

  const handleSkip = async (sectionId: string) => {
    if (disabled) return
    const result = await skipSection(sessionId, sectionId)
    onUpdate(result.skippedSections)
  }

  const handleReactivate = async (sectionId: string) => {
    if (disabled) return
    const result = await reactivateSection(sessionId, sectionId)
    onUpdate(result.skippedSections)
  }

  return (
    <div className="section-fill">
      {SECTIONS.map(({ id, label }) => {
        const isSkipped  = skippedSet.has(id)
        const isApproved = approvedSet.has(id)
        const fill = isApproved ? 100 : toFillPct(density[id] ?? 0)

        return (
          <div
            key={id}
            className={`section-fill-item ${isSkipped ? 'is-skipped' : ''} ${isApproved ? 'is-approved' : ''}`}
          >
            <div className="section-fill-bar-wrap">
              <div
                className="section-fill-bar"
                style={{ width: `${isSkipped ? 0 : fill}%` }}
              />
            </div>
            <span className="section-fill-label">{label}</span>
            {!isApproved && (
              <button
                className="section-fill-toggle"
                onClick={() => isSkipped ? handleReactivate(id) : handleSkip(id)}
                disabled={disabled}
                title={isSkipped ? 'Resume this section' : 'Skip this section'}
                aria-label={isSkipped ? `Resume ${label}` : `Skip ${label}`}
              >
                {isSkipped ? '↩' : '×'}
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}
