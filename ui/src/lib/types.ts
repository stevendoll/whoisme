export interface IcebreakerResponse {
  id: string
  text: string
}

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

export interface AdminIcebreaker {
  id: string
  text: string
  isActive?: string
}
