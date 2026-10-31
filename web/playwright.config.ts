import { defineConfig } from '@playwright/test'

// Real Chrome (already installed) drives the real built-in dev server. The API is mocked at the
// network layer inside each test, so no Django, database or terminal key is involved.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:5199', channel: 'chrome' },
  webServer: {
    command: 'npx vite --port 5199 --host 127.0.0.1',
    url: 'http://127.0.0.1:5199',
    reuseExistingServer: false,
  },
})
