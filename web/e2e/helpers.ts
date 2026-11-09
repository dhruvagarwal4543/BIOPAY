import type { Page, Route } from '@playwright/test'

export const SIM = 'SIMULATED PAYMENT — NO REAL MONEY'
export const MOCK_FP = 'DEVELOPMENT SIMULATION — NOT A PHYSICAL FINGERPRINT MATCH'

type Role = 'customer' | 'merchant'
const USERS = {
  alice: { username: 'alice', role: 'customer' as Role, name: 'Alice' },
  shop: { username: 'shop', role: 'merchant' as Role, name: 'Shop A' },
}

const payments = [
  { payment_id: '11111111-1111-4111-8111-111111111111', payer: 'Customer #1', merchant: 'Shop A', amount: 40, status: 'SUCCESS', decline_reason: '', auth_method: 'MOCK', created_at: '2026-10-30T04:00:00Z' },
  { payment_id: '22222222-2222-4222-8222-222222222222', payer: 'Customer #1', merchant: 'Shop A', amount: 900, status: 'DECLINED', decline_reason: 'insufficient_funds', auth_method: 'MOCK', created_at: '2026-10-30T04:05:00Z' },
]

export interface Mock {
  user: (typeof USERS)[keyof typeof USERS] | null
  expireOnNextData: boolean
  deletionStatus: number
  paymentsStatus: number
  paymentRows: typeof payments
  calls: Record<string, number>
}

const json = (route: Route, status: number, body: unknown) =>
  route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

/** Controlled mock server for /api. Cookies and sessions are simulated by `state.user`. */
export async function mockApi(page: Page, initial: Partial<Mock> = {}) {
  const state: Mock = {
    user: null, expireOnNextData: false, deletionStatus: 200, paymentsStatus: 200,
    paymentRows: payments, calls: {}, ...initial,
  }
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '')
    state.calls[path] = (state.calls[path] ?? 0) + 1
    // A data call after the server "forgot" the session: 401 like the real backend, and clear it.
    const expired = () => {
      if (!state.expireOnNextData) return false
      state.expireOnNextData = false
      state.user = null
      return true
    }
    if (path === '/auth/csrf/') return json(route, 200, { csrf_token: 't' })
    if (path === '/auth/me/') return json(route, 200, { user: state.user })
    if (path === '/auth/login/') {
      const body = route.request().postDataJSON()
      if (body.password !== 'correct-password') {
        return json(route, 401, { error: { code: 'authentication_failed', message: 'Incorrect username or password.' } })
      }
      state.user = body.username === 'shop' ? USERS.shop : USERS.alice
      return json(route, 200, { user: state.user })
    }
    if (path === '/auth/logout/') { state.user = null; return json(route, 200, { ok: true }) }
    if (expired() || !state.user) return json(route, 401, { error: { code: 'not_authenticated', message: 'Sign in.' } })
    if (path === '/customer/overview/') {
      return json(route, 200, {
        balance: 460,
        enrollments: [{ id: 1, customer: 'Alice', terminal: 'Counter 1', merchant: 'Shop A', status: 'ACTIVE', source: 'MOCK', consented_at: '2026-10-30T03:00:00Z', deletion_requested_at: null }],
      })
    }
    if (path === '/customer/enrollments/1/deletion-request/') {
      return state.deletionStatus === 200
        ? json(route, 200, {})
        : json(route, state.deletionStatus, { error: { code: 'permission_denied', message: 'You are not allowed to do that.' } })
    }
    if (path === '/merchant/overview/') {
      return json(route, 200, { balance: 40, terminals: [{ id: 1, name: 'Counter 1', merchant: 'Shop A', status: 'ACTIVE', last_seen: '2026-10-30T04:10:00Z' }] })
    }
    if (path === '/customer/payments/' || path === '/merchant/payments/') {
      if (state.paymentsStatus !== 200) return json(route, state.paymentsStatus, { error: { code: 'server_error', message: 'Server error.' } })
      return json(route, 200, { count: state.paymentRows.length, next: null, previous: null, results: state.paymentRows })
    }
    return json(route, 404, { error: { code: 'not_found', message: 'Not found.' } })
  })
  return state
}
