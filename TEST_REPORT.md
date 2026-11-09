# Test report
## 2026-11-09 baseline
- `manage.py test`: 80 tests, OK (throwaway env, local PostgreSQL).
- `tsc -b`: clean. `vite build`: OK (JS 274 kB).
- Playwright e2e: not yet run.
## Phase 2 (landing) — headless gstack browser
- `/` renders all 6 sections, 0 console errors on fresh load, `tsc -b` clean.
- Headless Chromium has no WebGL (webgl/webgl2 = false) -> only the 2D FALLBACK was exercised. 3D scenes, camera waypoints, scroll-scrub: UNVERIFIED.
- Found+fixed: app gated every route (incl. `/`) on `/auth/me`; landing now renders without the API.
