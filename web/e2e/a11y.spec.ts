import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { mockApi } from './helpers'

// axe scans (WCAG 2 A/AA rules) and responsive overflow checks. API is mocked, so these say
// nothing about the backend.
const WIDTHS = [390, 768, 1024, 1440]

async function scan(page: import('@playwright/test').Page) {
  const r = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
  return r.violations.map((v) => `${v.id}: ${v.nodes.length}x ${v.help}`)
}

for (const path of ['/', '/login', '/register']) {
  test(`axe: ${path} has no WCAG A/AA violations`, async ({ page }) => {
    await mockApi(page)
    await page.goto(path)
    await page.waitForTimeout(500)
    expect(await scan(page)).toEqual([])
  })
}

for (const w of WIDTHS) {
  test(`no horizontal overflow at ${w}px on public pages`, async ({ page }) => {
    await mockApi(page)
    await page.setViewportSize({ width: w, height: 800 })
    for (const path of ['/', '/login', '/register']) {
      await page.goto(path)
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), `${path} @${w}`).toBe(false)
    }
  })
}

test('login is keyboard-operable with visible focus', async ({ page }) => {
  await mockApi(page)
  await page.goto('/login')
  await expect(page.getByLabel('Username')).toBeVisible() // wait for the form before tabbing
  await page.keyboard.press('Tab')
  await expect(page.getByLabel('Username')).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByLabel('Password')).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeFocused()
  const outline = await page.getByRole('button', { name: 'Sign in' }).evaluate((e) => getComputedStyle(e).outlineStyle)
  expect(outline).not.toBe('none')
})
