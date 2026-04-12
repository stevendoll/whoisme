export type Speaker = 'visitor' | 'consultant1' | 'consultant2'

export interface TurnRequest {
  order: number
  text: string
  speaker: Speaker
  voices?: Record<string, string>  // {speaker: cartesia_voice_id}
}

export interface Turn {
  conversationId: string
  order: number
  text: string
  speaker: Speaker
  voiceId?: string
  ideaId?: string
  createdAt: string
}

export interface ConsultantReply {
  order: number
  text: string
  speaker: 'consultant1' | 'consultant2'
  voiceId?: string
  emotion?: string
}

export interface TurnResponse {
  turn: Turn
  consultantReplies?: ConsultantReply[]
}

export interface Conversation {
  conversationId: string
  createdAt: string
  preview: string
  voices?: Record<string, string>
  usedIdeas?: string[]
}

export interface ContactRequest {
  name: string
  email: string
  message: string
}

// UI-only chat message
export interface ChatMessage {
  id: string
  speaker: Speaker
  text: string
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
}
