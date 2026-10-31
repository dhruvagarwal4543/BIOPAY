import { chromium } from '@playwright/test'
const browser = await chromium.launch({ channel: 'chrome' })
for (const base of ['http://127.0.0.1:5173', 'http://localhost:5173']) {
  const page = await browser.newPage()
  await page.goto(base + '/login')
  await page.getByLabel('Username').fill('demo-customer')
  await page.getByLabel('Password').fill(process.env.BIOPAY_DEMO_PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForTimeout(2000)
  const alert = await page.getByRole('alert').allTextContents()
  console.log(base, '->', page.url().replace(base, ''), alert.length ? 'ALERT: ' + alert : '', (await page.getByText('Wallet balance').count()) ? 'dashboard shown' : '')
}
await browser.close()
