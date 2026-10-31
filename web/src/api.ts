export type Role = 'customer' | 'merchant' | 'admin'
export interface User { username: string; role: Role; name: string }
export interface Payment {
  payment_id: string; payer: string; merchant: string; amount: number
  status: 'SUCCESS' | 'DECLINED'; decline_reason: string; auth_method: string; created_at: string
}
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
export interface Enrollment {
  id: number; customer: string; terminal: string; merchant: string
  status: 'ACTIVE' | 'DELETION_REQUESTED' | 'REVOKED'; source: string
  consented_at: string; deletion_requested_at: string | null
}
export interface Terminal { id: number; name: string; merchant: string; status: 'ACTIVE' | 'REVOKED'; last_seen: string | null }

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const cookie = (name: string) =>
  document.cookie.split('; ').find((c) => c.startsWith(name + '='))?.split('=')[1] ?? ''

export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const method = init.method ?? 'GET'
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (method !== 'GET') {
    if (!cookie('csrftoken')) await fetch('/api/auth/csrf/', { credentials: 'same-origin' })
    headers['X-CSRFToken'] = cookie('csrftoken')
  }
  if (init.body !== undefined) headers['Content-Type'] = 'application/json'
  let res: Response
  try {
    res = await fetch(`/api${path}`, {
      method, headers, credentials: 'same-origin',
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Check that the backend is running.')
  }
  const data = await res.json().catch(() => null)
  // 401 = no valid session (expired). 403 = signed in but not allowed, so it is NOT redirected.
  // The login call itself returns 401 for a wrong password and must show its message instead.
  if (res.status === 401 && path !== '/auth/login/' && window.location.pathname !== '/login') {
    window.location.assign('/login')
  }
  if (!res.ok) {
    const message =
      data?.error?.message ??
      (res.status === 403 ? 'You are not allowed to view this.' : `Request failed (${res.status}).`)
    throw new ApiError(res.status, message)
  }
  return data as T
}

export const money = (n: number) => n.toLocaleString('en-IN')
export const when = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '—'
