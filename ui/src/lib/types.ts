export interface ContactRequest {
  name: string
  email: string
  message: string
}

// ── Interview ─────────────────────────────────────────────────────────────────

export type InterviewPhase = 'interviewing' | 'reviewing' | 'complete'

export interface CreateInterviewResponse {
  sessionId: string
  message: string
  heckle: string | null
  questionsRemaining: number
  questionsTotal: number
}

export interface RespondResponse {
  message: string
  sectionsTouched: string[]
  heckle: string | null
  questionsRemaining: number
  phase: InterviewPhase
}

export interface SkipQuestionResponse {
  message: string
  heckle: string | null
  questionsRemaining: number
}

export interface PauseResponse {
  phase: InterviewPhase
  draftFiles: Record<string, string>
  skippedSections: string[]
}

export interface MoreQuestionsResponse {
  message: string
  heckle: string | null
  questionsRemaining: number
  phase: InterviewPhase
}

export interface ReviewApproveResponse {
  approvedFiles: string[]
}

export interface ReviewFeedbackResponse {
  file: string
  draft: string
}

export interface SessionState {
  sessionId: string
  phase: InterviewPhase
  questionsAsked: number
  questionsTotal: number
  questionsRemaining: number
  sectionDensity: Record<string, number>
  skippedSections: string[]
  approvedFiles: string[]
  draftFiles: string[]
}

// ── Users ─────────────────────────────────────────────────────────────────────

export interface UserProfile {
  userId: string
  email: string
  username: string | null
  published: boolean
  visibility: Record<string, string>
  hasBearerToken: boolean
  lastPublishedAt: string | null
  approvedFilesAt: Record<string, string>
}
