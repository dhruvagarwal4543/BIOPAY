// Real-stack check: Django + PostgreSQL + Vite, NO mocks. Walks the whole college demo, then axe-scans
// each page and checks overflow at 4 widths. Run: scripts/demo.sh start; node web/e2e-real/demo.mjs
// Needs BASE (default http://127.0.0.1:5173) and the demo password in .demo-credentials (or $DEMO_PASSWORD).
import { chromium } from 'playwright-core'
import AxeBuilder from '@axe-core/playwright'
import { readFileSync, mkdirSync } from 'node:fs'
import assert from 'node:assert/strict'

const BASE = process.env.BASE ?? 'http://127.0.0.1:5173'
const PW = process.env.DEMO_PASSWORD ?? readFileSync(new URL('../../.demo-credentials', import.meta.url), 'utf8').trim()
const OUT = process.env.OUT ?? new URL('../test-results/real-stack/', import.meta.url).pathname
mkdirSync(OUT, { recursive: true })
const user = 'vol-' + Math.random().toString(36).slice(2, 8)
const volunteerPw = 'volunteer-' + Math.random().toString(36).slice(2, 12) + '-X9'

const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await ctx.newPage()
const problems = []
page.on('pageerror', (e) => problems.push('pageerror: ' + e.message))
page.on('console', (m) => m.type() === 'error' && !/status of (401|403|409|422)/.test(m.text()) && problems.push('console: ' + m.text()))
page.on('dialog', (d) => d.accept())
const log = (s) => console.log('PASS', s)
const text = () => page.locator('body').innerText()
const has = (re) => page.waitForFunction(([src, fl]) => new RegExp(src, fl).test(document.body.innerText), [re.source, re.flags], { timeout: 10000 })
const status = () => page.getByRole('status').filter({ hasText: /:|Waiting/ }).last().innerText()
const axe = async (name) => {
  const r = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
  assert.deepEqual(r.violations.map((v) => `${v.id} x${v.nodes.length}: ${v.help}`), [], `axe ${name}`)
  log(`axe clean: ${name}`)
}
const login = async (u, p) => {
  await page.goto(BASE + '/login'); await page.getByLabel('Username').fill(u); await page.getByLabel('Password').fill(p)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL((u) => !u.pathname.endsWith('/login'))
}
const logout = async () => { await page.getByRole('button', { name: 'Sign out' }).click(); await page.waitForURL('**/login') }

// 1. landing
await page.goto(BASE + '/'); await page.waitForSelector('canvas'); await page.waitForTimeout(1500)
assert.equal(await page.locator('main section').count(), 6); log('landing: 6 sections + WebGL canvas')
await page.screenshot({ path: `${OUT}/01-landing.png` }); await axe('landing')
// 2-4. register + consent + balance
await page.goto(BASE + '/register'); await axe('register')
await page.getByLabel('Full name').fill('Demo Volunteer'); await page.getByLabel(/Username/).fill(user)
await page.getByLabel(/Password/).fill(volunteerPw); await page.getByRole('checkbox').check()
await page.getByRole('button', { name: 'Register' }).click(); await page.waitForURL('**/customer')
await has(/100\s*BioCoins/); log('registered with consent; 100 simulated BioCoins')
// 5. enroll mock fingerprint (with simulator opt-in)
await page.getByLabel(/consent to enrolling/).check(); await page.getByLabel(/allow the merchant simulator/i).check()
await page.getByRole('button', { name: 'Enroll (MOCK)' }).click()
await page.getByText(/Mock fingerprint slot/).waitFor()
const slot = Number((await text()).match(/Mock fingerprint slot (\d+)/)[1]); log(`mock fingerprint enrolled, slot ${slot}, simulator ON`)
await has(/Merchant simulator: ON/); await page.screenshot({ path: `${OUT}/02-customer.png` }); await axe('customer dashboard')
await page.goto(BASE + '/wallet'); await page.waitForURL('**/customer'); log('/wallet redirects to /customer')
await page.goto(BASE + '/profile'); await has(/Demo Volunteer/); await axe('profile'); log('/profile works')
await page.goto(BASE + '/customer'); await logout()
// 6-9. merchant pays
await login('demo-merchant', PW); await page.waitForURL('**/merchant'); await axe('merchant dashboard')
await page.getByRole('link', { name: 'Simulator' }).first().click(); await page.waitForURL('**/merchant/terminal'); await axe('simulator')
await has(/NOT A PHYSICAL FINGERPRINT MATCH/)
const pay = async (s, a) => { await page.getByLabel('Mock fingerprint slot').fill(String(s)); await page.getByLabel(/Amount/).fill(String(a)); await page.getByRole('button', { name: /^(Pay|Retry payment)$/ }).click(); await page.waitForTimeout(900); return status() }
assert.match(await pay(slot, 60), /SUCCESS: Payment confirmed by the server/); log('payment of 60 confirmed by backend')
// 13. idempotent retry
await page.getByRole('button', { name: /Resend the same payment/ }).click(); await page.waitForTimeout(900)
assert.match(await status(), /SUCCESS: Confirmed \(replayed, charged once\)/); log('idempotent resend: replayed, charged once')
// 12. insufficient funds (40 left)
assert.match(await pay(slot, 60), /DECLINED: Insufficient BioCoins/); log('second payment of 60 declined (insufficient balance)')
assert.match(await pay(9999, 5), /UNAUTHORIZED/); log('unknown slot refused')
await page.screenshot({ path: `${OUT}/03-simulator.png` })
await page.goto(BASE + '/merchant'); await has(/Customer #\d+/); assert.doesNotMatch(await text(), /Demo Volunteer/); log('merchant history shows opaque customer label')
await page.getByRole('link', { name: /\w{3} \d+, \d{4}/ }).first().click(); await page.getByText('Transaction details').waitFor(); await axe('merchant tx detail'); log('merchant transaction detail')
await page.goto(BASE + '/merchant'); await logout()
// 11. customer sees balance + history
await login(user, volunteerPw); await page.waitForURL('**/customer')
await has(/40\s*BioCoins/); await has(/SUCCESS/); await has(/DECLINED/); log('customer balance 40; history shows SUCCESS and DECLINED')
await page.getByRole('link', { name: /\w{3} \d+, \d{4}/ }).first().click(); await page.getByText('Transaction details').waitFor(); log('customer transaction detail')
await page.goto(BASE + '/customer')
// consent withdrawal: switch simulator off -> merchant refused
await page.getByRole('button', { name: /Merchant simulator: ON/ }).click(); await page.getByText('Merchant simulator: OFF').waitFor(); await logout()
await login('demo-merchant', PW); await page.goto(BASE + '/merchant/terminal')
assert.match(await pay(slot, 5), /UNAUTHORIZED/); log('simulator consent withdrawn -> payment refused'); await logout()
// 14. admin
await login('demo-admin', PW); await page.waitForURL('**/admin'); await page.getByText('Ledger reconciliation').waitFor()
await has(/Every wallet equals opening balance/); log('admin reconciliation SUCCESS')
await axe('admin'); await page.screenshot({ path: `${OUT}/04-admin.png` })
const t = await text(); for (const a of ['customer.registered', 'enrollment.created', 'enrollment.simulator_off']) assert.ok(t.includes(a), a)
log('admin audit shows register / enroll / simulator_off'); await page.goto(BASE + '/admin/audit'); await axe('admin audit')
// role isolation
await page.goto(BASE + '/merchant'); await has(/Not authorised/); log('admin cannot open merchant page (role isolation)'); await logout()
// responsive overflow on every page of every role, 320..1920
const WIDTHS = [320, 390, 768, 1024, 1440, 1920]
const overflowAt = async (pages) => {
  for (const w of WIDTHS) {
    await page.setViewportSize({ width: w, height: 850 })
    for (const p of pages) {
      await page.goto(BASE + p); await page.waitForTimeout(350)
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `${p}@${w}`)
    }
  }
}
await overflowAt(['/', '/login', '/register'])
await login('demo-merchant', PW); await overflowAt(['/merchant', '/merchant/terminal']); await logout()
await login(user, volunteerPw); await overflowAt(['/customer', '/profile']); await logout()
await login('demo-admin', PW); await overflowAt(['/admin', '/admin/audit']); await page.setViewportSize({ width: 390, height: 844 }); await page.goto(BASE + '/admin'); await page.waitForTimeout(500); await page.screenshot({ path: `${OUT}/06-admin-mobile.png`, fullPage: true }); await logout()
await login('demo-merchant', PW)
await page.setViewportSize({ width: 390, height: 844 }); await page.goto(BASE + '/merchant/terminal'); await page.screenshot({ path: `${OUT}/05-simulator-mobile.png` })
log('no horizontal overflow at 320/390/768/1024/1440/1920 on all role pages')
assert.deepEqual(problems, [], 'console/page errors'); log('no unexpected console errors')
await browser.close(); console.log('REAL-STACK DEMO: ALL PASSED')
