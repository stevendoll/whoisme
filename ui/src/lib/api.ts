import type {
  IcebreakerResponse,
  TurnRequest,
  TurnResponse,
  Conversation,
  ContactRequest,
  Turn,
  AdminIcebreaker,
  CreateInterviewResponse,
  RespondResponse,
  SkipQuestionResponse,
  PauseResponse,
  MoreQuestionsResponse,
  ReviewApproveResponse,
  ReviewFeedbackResponse,
  SessionState,
  UserProfile,
} from './types'

const BASE = import.meta.env.VITE_API_URL ?? ''

function getUserToken(): string | null {
  return localStorage.getItem('whoisme_user_token')
}

function snakeToCamel(s: string): string {
  return s.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase())
}

function camelizeKeys(val: unknown): unknown {
  if (Array.isArray(val)) return val.map(camelizeKeys)
  if (val !== null && typeof val === 'object') {
    return Object.fromEntries(
      Object.entries(val).map(([k, v]) => [snakeToCamel(k), camelizeKeys(v)])
    )
  }
  return val
}

async function apiFetch<T>(path: string, options: RequestInit = {}, auth = false): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(options.headers as Record<string, string>) }
  if (auth) {
    const token = getUserToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }
  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const body = camelizeKeys(await res.json()) as { error?: string; message?: string }
      message = body.error ?? body.message ?? message
    } catch { /* ignore */ }
    throw new Error(message)
  }
  return camelizeKeys(await res.json()) as T
}

export function getIcebreaker(): Promise<IcebreakerResponse> {
  return apiFetch('/conversations/icebreakers')
}

export function postTurn(conversationId: string, body: TurnRequest): Promise<TurnResponse> {
  return apiFetch(`/conversations/${conversationId}/turns`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function getConversations(): Promise<{ conversations: Conversation[] }> {
  return apiFetch('/conversations')
}

export function getConversationTurns(conversationId: string): Promise<{ turns: Turn[] }> {
  return apiFetch(`/conversations/${conversationId}/turns`)
}

export function postContact(body: ContactRequest): Promise<{ contactId: string }> {
  return apiFetch('/contacts', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function postError(error_type: string, message: string): Promise<{ ok: boolean }> {
  return apiFetch('/errors', {
    method: 'POST',
    body: JSON.stringify({ error_type, message }),
  })
}

// ── Admin auth ────────────────────────────────────────────────────────────────

export function postAdminLogin(email: string): Promise<{ ok: boolean }> {
  return apiFetch('/admin/login', { method: 'POST', body: JSON.stringify({ email }) })
}

export function postAdminVerify(token: string): Promise<{ ok: boolean; email?: string }> {
  return apiFetch('/admin/verify', { method: 'POST', body: JSON.stringify({ token }) })
}

// ── Admin ─────────────────────────────────────────────────────────────────────

export function getAdminIcebreakers(): Promise<{ items: AdminIcebreaker[]; count: number }> {
  return apiFetch('/admin/icebreakers')
}

export function createIcebreaker(text: string): Promise<AdminIcebreaker> {
  return apiFetch('/admin/icebreakers', {
    method: 'POST',
    body: JSON.stringify({ text, is_active: 'true' }),
  })
}

export function updateIcebreaker(id: string, patch: { text?: string; is_active?: string }): Promise<{ updated: string }> {
  return apiFetch(`/admin/icebreakers/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export function deleteIcebreaker(id: string): Promise<{ deleted: string }> {
  return apiFetch(`/admin/icebreakers/${id}`, { method: 'DELETE' })
}

// ── Interview ─────────────────────────────────────────────────────────────────

export function createInterview(): Promise<CreateInterviewResponse> {
  return apiFetch('/interview', { method: 'POST' })
}

export function respondToInterview(sessionId: string, text: string): Promise<RespondResponse> {
  return apiFetch(`/interview/${sessionId}/respond`, { method: 'POST', body: JSON.stringify({ text }) })
}

export function skipQuestion(sessionId: string): Promise<SkipQuestionResponse> {
  return apiFetch(`/interview/${sessionId}/skip-question`, { method: 'POST' })
}

export function skipSection(sessionId: string, section: string): Promise<{ message: string; heckle: string | null; skippedSections: string[] }> {
  return apiFetch(`/interview/${sessionId}/skip-section`, { method: 'POST', body: JSON.stringify({ section }) })
}

export function reactivateSection(sessionId: string, section: string): Promise<{ skippedSections: string[] }> {
  return apiFetch(`/interview/${sessionId}/reactivate-section`, { method: 'POST', body: JSON.stringify({ section }) })
}

export function pauseInterview(sessionId: string): Promise<PauseResponse> {
  return apiFetch(`/interview/${sessionId}/pause`, { method: 'POST' })
}

export function moreQuestions(sessionId: string, count = 10): Promise<MoreQuestionsResponse> {
  return apiFetch(`/interview/${sessionId}/more`, { method: 'POST', body: JSON.stringify({ count }) })
}

export function approveFile(sessionId: string, file: string): Promise<ReviewApproveResponse> {
  return apiFetch(`/interview/${sessionId}/review/approve`, { method: 'POST', body: JSON.stringify({ file }) })
}

export function submitFeedback(sessionId: string, file: string, text: string): Promise<ReviewFeedbackResponse> {
  return apiFetch(`/interview/${sessionId}/review/feedback`, { method: 'POST', body: JSON.stringify({ file, text }) })
}

export function getInterviewSession(sessionId: string): Promise<SessionState> {
  return apiFetch(`/interview/${sessionId}`)
}

// ── Users ─────────────────────────────────────────────────────────────────────

export function startAuth(email: string, sessionId?: string): Promise<{ ok: boolean }> {
  return apiFetch('/users/start', { method: 'POST', body: JSON.stringify({ email, session_id: sessionId }) })
}

export function verifyAuth(token: string): Promise<{ token: string; userId: string; email: string }> {
  return apiFetch('/users/verify', { method: 'POST', body: JSON.stringify({ token }) })
}

export function getMe(): Promise<UserProfile> {
  return apiFetch('/users/me', {}, true)
}

export function updateVisibility(visibility: Record<string, string>): Promise<{ visibility: Record<string, string> }> {
  return apiFetch('/users/me/visibility', { method: 'PATCH', body: JSON.stringify({ visibility }) }, true)
}

export function publishProfile(username: string): Promise<{ username: string; url: string }> {
  return apiFetch('/users/me/publish', { method: 'POST', body: JSON.stringify({ username }) }, true)
}

export function createBearerToken(): Promise<{ token: string }> {
  return apiFetch('/users/me/token', { method: 'POST' }, true)
}

export function revokeBearerToken(): Promise<{ ok: boolean }> {
  return apiFetch('/users/me/token', { method: 'DELETE' }, true)
}

export function importSession(sessionId: string): Promise<{ ok: boolean }> {
  return apiFetch('/users/me/import', { method: 'POST', body: JSON.stringify({ session_id: sessionId }) }, true)
}
