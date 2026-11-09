import { expect, test, type Page } from '@playwright/test'
import { MOCK_FP, mockApi, SIM } from './helpers'

// These tests drive a real browser against mocked API responses. They check the web app's
// behaviour only. They say nothing about the backend, the database or any fingerprint sensor.

// Dev mode runs React StrictMode, which doubles the first fetches, so assert "stops growing", not exact counts.
async function expectNoMoreCalls(page: Page, state: { calls: Record<string, number> }) {
  await page.waitForTimeout(300)
  const snapshot = JSON.stringify(state.calls)
  await page.waitForTimeout(700)
  expect(JSON.stringify(state.calls)).toBe(snapshot)
}

async function signIn(page: Page, username: string, password = 'correct-password') {
  await page.getByLabel('Username').fill(username)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
}

test('login page renders with the simulation label', async ({ page }) => {
  await mockApi(page)
  await page.goto('/login')
  await expect(page.getByText(SIM).first()).toBeVisible()
  await expect(page.getByRole('heading', { name: 'BioPay' })).toBeVisible()
  await expect(page.getByLabel('Username')).toBeVisible()
  await expect(page.getByLabel('Password')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeEnabled()
})

test('failed login shows the error, stays on /login and does not loop', async ({ page }) => {
  const state = await mockApi(page)
  await page.goto('/login')
  await signIn(page, 'alice', 'wrong')
  await expect(page.getByRole('alert')).toHaveText('Incorrect username or password.')
  await expect(page).toHaveURL(/\/login$/)
  expect(state.calls['/auth/login/']).toBe(1)
  await expectNoMoreCalls(page, state) // a redirect loop would keep calling the API
})

test('expired session (401) redirects to /login once', async ({ page }) => {
  const state = await mockApi(page, { user: { username: 'alice', role: 'customer', name: 'Alice' }, expireOnNextData: true })
  await page.goto('/customer')
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()
  await expectNoMoreCalls(page, state)
  expect(state.user).toBeNull()
})

test('403 on a forbidden action keeps the user signed in', async ({ page }) => {
  const state = await mockApi(page, { user: { username: 'alice', role: 'customer', name: 'Alice' }, deletionStatus: 403 })
  page.on('dialog', (d) => d.accept())
  await page.goto('/customer')
  await expect(page.getByRole('button', { name: 'Request deletion' })).toBeVisible()
  const meBefore = state.calls['/auth/me/']
  await page.getByRole('button', { name: 'Request deletion' }).click()
  await expect(page.getByRole('alert')).toContainText('You are not allowed to do that.')
  await expect(page).toHaveURL(/\/customer$/)
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible()
  expect(state.calls['/auth/me/']).toBe(meBefore) // never re-checked, never logged out
  expect(state.calls['/auth/logout/']).toBeUndefined()
})

test('customer and merchant navigation', async ({ page }) => {
  await mockApi(page)
  await page.goto('/login')
  await signIn(page, 'alice')
  await expect(page).toHaveURL(/\/customer$/)
  await expect(page.getByText('Wallet balance')).toBeVisible()
  await expect(page.getByText('460').first()).toBeVisible()
  await expect(page.getByText(MOCK_FP)).toBeVisible()
  await page.goto('/merchant') // wrong role: a message, not a logout
  await expect(page.getByRole('heading', { name: 'Not authorised' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible() // never a dead end
  await expect(page.getByRole('link', { name: 'Go to your dashboard' })).toBeVisible()
  await page.goto('/customer')
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page).toHaveURL(/\/login$/)
  await signIn(page, 'shop')
  await expect(page).toHaveURL(/\/merchant$/)
  await expect(page.getByText('Merchant balance')).toBeVisible()
  await expect(page.getByText('Counter 1').first()).toBeVisible()
  await expect(page.getByText(MOCK_FP)).toBeVisible()
  await expect(page.getByText(SIM).first()).toBeVisible()
})

test('payment history shows success and declined states, plus MOCK verification', async ({ page }) => {
  await mockApi(page, { user: { username: 'alice', role: 'customer', name: 'Alice' } })
  await page.goto('/customer')
  const rows = page.getByRole('row')
  await expect(rows.filter({ hasText: 'SUCCESS' })).toContainText('40')
  await expect(rows.filter({ hasText: 'DECLINED' })).toContainText('900')
  await expect(page.getByText('MOCK').first()).toBeVisible()
})

test('payment history empty and error states', async ({ page }) => {
  await mockApi(page, { user: { username: 'alice', role: 'customer', name: 'Alice' }, paymentRows: [] })
  await page.goto('/customer')
  await expect(page.getByText('No transactions yet.')).toBeVisible()

  const state = await mockApi(page, { user: { username: 'alice', role: 'customer', name: 'Alice' }, paymentsStatus: 500 })
  await page.goto('/customer')
  await expect(page.getByRole('alert').filter({ hasText: 'Server error.' })).toBeVisible()
  state.paymentsStatus = 200
  await page.getByRole('button', { name: 'Retry' }).click()
  await expect(page.getByRole('row').filter({ hasText: 'SUCCESS' })).toBeVisible()
})

test('landing renders without the API, shows all six scenes and the simulation label', async ({ page }) => {
  // No mockApi: the public page must not depend on the backend being reachable.
  await page.goto('/')
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('heading', { level: 1, name: 'Your Identity. Your Payment.' })).toBeVisible()
  await expect(page.getByText(SIM)).toBeVisible()
  await expect(page.locator('main section')).toHaveCount(6)
  await page.getByRole('link', { name: 'Launch Demo' }).first().click()
  await expect(page).toHaveURL(/\/login$/)
})

test('landing with reduced motion still shows every scene copy (no scroll hijack, no horizontal scroll)', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'The Digital Wallet' })).toBeAttached()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
  expect(overflow).toBe(false)
})

test('register requires consent and a strong password before the server is asked', async ({ page }) => {
  const state = await mockApi(page)
  await page.goto('/register')
  await page.getByLabel('Full name').fill('Vol One')
  await page.getByLabel(/Username/).fill('vol-one')
  await page.getByLabel(/Password/).fill('short')
  await page.getByRole('button', { name: 'Register' }).click()
  expect(state.calls['/auth/register/'] ?? 0).toBe(0) // browser validation blocked the submit
  await expect(page.getByRole('checkbox')).not.toBeChecked()
})
