import type {
  IcebreakerResponse,
  TurnRequest,
  TurnResponse,
  Conversation,
  ContactRequest,
  Turn,
  AdminIcebreaker,
} from './types'

const BASE = import.meta.env.VITE_API_URL ?? ''

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  })
  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const body = (await res.json()) as { error?: string; message?: string }
      message = body.error ?? body.message ?? message
    } catch { /* ignore */ }
    throw new Error(message)
  }
  return res.json() as Promise<T>
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
