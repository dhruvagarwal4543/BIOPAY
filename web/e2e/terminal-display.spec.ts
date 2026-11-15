import { expect, test } from '@playwright/test'
import { mockApi } from './helpers'

// Browser behaviour against a mocked API. This proves the widget renders what the API says; it does
// NOT prove a real ESP32 publishes anything (see firmware/README.md for hardware checks).
const T = { id: 1, name: 'Counter 1', merchant: 'Shop A' }

async function open(page: import('@playwright/test').Page, live: unknown, extra = {}) {
  const state = await mockApi(page, { user: { username: 'shop', role: 'merchant', name: 'Shop A' }, live: live as never, ...extra })
  await page.addInitScript(() => localStorage.setItem('biopay.terminal.open', '1'))
  await page.goto('/merchant')
  return state
}

test('shows the device screen live, and its state changes follow the API', async ({ page }) => {
  const state = await open(page, [{ ...T, online: true, screen: 'amount', data: { entry: '25', mock: false } }])
  const box = page.getByRole('status').filter({ hasText: 'ENTER AMOUNT' })
  await expect(box).toContainText('25')
  await expect(page.getByText('Terminal · Live')).toBeVisible()
  state.live = [{ ...T, online: true, screen: 'success', data: { amount: 25, ref: 'ab12cd34', mock: false } }]
  await expect(page.getByRole('status').filter({ hasText: 'PAID' })).toContainText('Ref ab12cd34')
  await expect(page.getByText('MOCK terminal')).toHaveCount(0)
})

test('offline device shows no screen; mock device is labelled', async ({ page }) => {
  const state = await open(page, [{ ...T, online: false, screen: null, data: {} }])
  await expect(page.getByText('Terminal · Offline')).toBeVisible()
  await expect(page.getByText('Terminal offline. Nothing is shown')).toBeVisible()
  state.live = [{ ...T, online: true, screen: 'idle', data: { mock: true } }]
  await expect(page.getByText('MOCK terminal · simulated')).toBeVisible()
})

test('server failure shows Connecting and recovers by itself', async ({ page }) => {
  const state = await open(page, [{ ...T, online: true, screen: 'idle', data: {} }])
  await expect(page.getByText('Terminal · Live')).toBeVisible()
  state.liveStatus = 500
  await expect(page.getByText('Terminal · Connecting')).toBeVisible()
  state.liveStatus = 200
  await expect(page.getByText('Terminal · Live')).toBeVisible()
})

test('collapses and expands; hidden for customers', async ({ page }) => {
  await open(page, [{ ...T, online: true, screen: 'idle', data: {} }])
  await page.getByRole('button', { name: 'Collapse terminal display' }).click()
  await expect(page.getByText('READY')).toHaveCount(0)
  await page.getByRole('button', { name: 'Expand terminal display' }).click()
  await expect(page.getByText('READY')).toBeVisible()
})

test('customer never sees the widget or calls the live API', async ({ page }) => {
  const state = await mockApi(page, { user: { username: 'alice', role: 'customer', name: 'Alice' } })
  await page.goto('/customer')
  await page.waitForTimeout(1500)
  await expect(page.getByText(/Terminal ·/)).toHaveCount(0)
  expect(state.calls['/merchant/terminals/live/'] ?? 0).toBe(0)
})

test('fits a 320px phone and stays on screen after dragging', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 })
  await open(page, [{ ...T, online: true, screen: 'finger', data: { amount: 40 } }])
  const panel = page.getByText('Terminal · Live').locator('xpath=ancestor::div[contains(@class,"fixed")]')
  let b = (await panel.boundingBox())!
  expect(b.x).toBeGreaterThanOrEqual(0); expect(b.x + b.width).toBeLessThanOrEqual(320)
  await page.mouse.move(b.x + 40, b.y + 15); await page.mouse.down()
  await page.mouse.move(-500, -500, { steps: 5 }); await page.mouse.up()
  b = (await panel.boundingBox())!
  expect(b.x).toBeGreaterThanOrEqual(-0.5); expect(b.y).toBeGreaterThanOrEqual(-0.5)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320)
})
