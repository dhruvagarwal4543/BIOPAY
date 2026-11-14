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
| 9 | QA/security/perf | DONE for software except items listed under NOT done in TEST_REPORT.md |
| 10 | Delivery docs | DONE: README, ARCHITECTURE.md, docs/ (college report, demo script, presentation outline), firmware/INTEGRATION_PLAN.md |

## Done since last checkpoint
Simulator needs per-enrollment customer consent; /wallet, /profile, nav; axe + responsive tests; real-stack demo script; scripts/demo.sh; college docs.

## SOFTWARE PHASE CLOSED (2026-11-15)
All software tasks done and verified (see TEST_REPORT.md, release verification). Deliverables: docs/FINAL_REPORT.pdf/.docx, docs/BioPay_Presentation.pptx, docs/diagrams, docs/HARDWARE_HANDOFF.md.

## Resume point
Next: (a) when hardware arrives: pick parts, follow firmware/INTEGRATION_PLAN.md; add a real-sensor mode to the terminal API (BLOCKERS #2) and HTTPS;
(b) screen-reader pass and GPU frame-rate check; (c) production settings pass.
