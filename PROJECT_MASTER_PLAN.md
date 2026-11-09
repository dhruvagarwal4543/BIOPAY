# BioPay master plan (source of truth across sessions)

Plan + progress in one file. Evidence: TEST_REPORT.md. Blockers: BLOCKERS.md. Design: ARCHITECTURE.md.

| # | Phase | Status |
|---|-------|--------|
| 0 | Audit + baseline | DONE |
| 1 | Design system / routes | DONE (existing tokens reused; routes in ARCHITECTURE.md) |
| 2 | Cinematic 3D landing | DONE, verified in software-WebGL Chromium (desktop+mobile screenshots). Not checked: real GPU frame rate |
| 3 | Registration + consent | DONE (backend tests + real browser) |
| 4 | Customer app | DONE: wallet, history, tx detail, enroll/withdraw. No separate /wallet, /profile pages (merged into /customer) |
| 5 | Merchant app | DONE: dashboard, history, detail, terminals, simulator |
| 6 | Admin | DONE: overview, revoke, reconciliation, audit log. Customers/merchants are panels, not separate routes |
| 7 | Terminal simulator | DONE (dev-only, real payment service) |
| 8 | Firmware | PARTIAL: payflow logic tested natively; ESP32 glue BLOCKED on hardware |
| 9 | QA/security/perf | PARTIAL: see TEST_REPORT.md for what was and was not run |
| 10 | Delivery docs | DONE: README demo sequence, ARCHITECTURE.md |

## Resume point
Next: (a) before real hardware, replace the DEBUG gate on the terminal API with a real-sensor mode (BLOCKERS #2);
(b) axe accessibility run, keyboard walk, GPU frame-rate check; (c) HTTPS/production settings pass.
