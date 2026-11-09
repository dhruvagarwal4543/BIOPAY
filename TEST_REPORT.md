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

## Completion run (2026-11-09, second session)
- Backend `manage.py test`: **104 OK** (adds simulator-consent tests: unauthorized slot, revoked enrollment, withdrawn consent, terminal ownership, repeated UUID, changed payload 409, insufficient funds, owner-only toggle, audit, and a PostgreSQL race test where consent withdrawal queues behind an in-flight payment).
- Playwright (mocked API, system Chrome): **18 passed** — adds axe WCAG 2 A/AA scans of `/`, `/login`, `/register` (0 violations), no horizontal overflow at 390/768/1024/1440 on public pages, keyboard Tab order + visible focus on login.
- Real stack (`node web/e2e-real/demo.mjs`, real Django + PostgreSQL scratch DB + Vite, software-WebGL Chromium): **ALL PASSED** — landing 6 sections + WebGL canvas; register with consent; mock enroll; /wallet redirect; /profile; merchant simulator pay 60 (SUCCESS), resend same ID (replayed, charged once), second 60 (DECLINED insufficient), unknown slot refused; merchant sees opaque "Customer #n"; customer balance 40 with SUCCESS+DECLINED history; consent withdrawn -> payment refused; admin reconciliation SUCCESS, audit shows register/enroll/simulator_off; admin gets "Not authorised" on merchant page; axe 0 violations on landing, register, customer, profile, merchant, simulator, tx detail, admin, audit; no overflow at 4 widths on the app pages tested; no unexpected console errors.
- `tsc -b` OK; `oxlint` 0 errors, 3 warnings (pre-existing fast-refresh/set-state-in-effect); `vite build` OK, app bundle 289 kB.
- Firmware `make -C firmware test` OK (native fakes).
- Ponytail review of this session's code: fixed demo.sh killing unrelated servers (now pid files), hardcoded paths in the real-stack script, misleading simulator toggle when disabled, missing consent race test.
- NOT done: screen-reader session; axe on authenticated pages is only in the real-stack script (not in CI); real-GPU frame rate; mobile pages other than /merchant and /merchant/terminal checked for overflow only on the public pages + merchant pair; admin/customer pages at 390px not overflow-tested.
