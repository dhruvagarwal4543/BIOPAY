# Test report
## 2026-11-09 baseline
- `manage.py test`: 80 tests, OK (throwaway env, local PostgreSQL).
- `tsc -b`: clean. `vite build`: OK (JS 274 kB).
- Playwright e2e: not yet run.
## Phase 2 (landing) — headless gstack browser
- `/` renders all 6 sections, 0 console errors on fresh load, `tsc -b` clean.
- Headless Chromium has no WebGL (webgl/webgl2 = false) -> only the 2D FALLBACK was exercised. 3D scenes, camera waypoints, scroll-scrub: UNVERIFIED.
- Found+fixed: app gated every route (incl. `/`) on `/auth/me`; landing now renders without the API.

## Final run (2026-11-09)
- Backend `manage.py test`: 94 tests OK (80 baseline + 14 new: register/consent/password, mock enroll, simulator, detail, audit).
- Browser (Playwright, mocked API): 10 passed (incl. landing without API, reduced motion, register validation).
- Real stack (Django + scratch Postgres + Vite, headless browser): register -> consent -> enroll -> simulator pay 30 (success), unknown slot (unauthorized), 100 (declined), admin sees audit + reconciliation SUCCESS.
- 3D: Playwright Chromium with SwiftShader WebGL, desktop 1440x900 and mobile 390x844, 7 scroll points each: scenes render, no console errors, no horizontal scroll. Fixed: scene timing vs sections, edge-on fingerprint, dark materials, mobile clipping.
- Firmware: `make -C firmware test` OK (native fakes only; nothing run on a board).
- `tsc -b`, `vite build` OK. App bundle 285 kB; landing + three load lazily (Scene 943 kB, 250 kB gzip).
- Ponytail review + audit run; findings fixed: audit pager, stable `terminal_revoked` code, empty-terminal state, lazy landing bundle, stray script removed, password validators enabled, SIM string aligned to spec.
