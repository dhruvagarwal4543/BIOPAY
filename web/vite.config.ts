import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The browser only ever talks to this origin; /api is proxied to Django, so no CORS is needed.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // changeOrigin must stay false: Django's CSRF check compares Origin with the Host the browser used.
  server: { proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false } } },
})
