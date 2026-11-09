# BioPay master plan (source of truth across sessions)

Kept as one file: plan + progress + acceptance. Test evidence: TEST_REPORT.md. Blockers: BLOCKERS.md.

## Verified baseline (2026-11-09)
- Django/DRF + PostgreSQL; models: Customer, Merchant, Wallet, Terminal, Enrollment, Payment, LedgerEntry.
- Backend: 80 tests pass. Web: React 19 + TS + Vite + Tailwind 4; `tsc -b` and `vite build` pass.
- Routes today: /login, /customer, /merchant, /admin. No landing page, no 3D, no registration, no firmware.

## Phases
| # | Phase | Status |
|---|-------|--------|
| 0 | Audit + baseline | DONE |
| 1 | Design system / route map | PENDING |
| 2 | Cinematic 3D landing (6 scenes) | PENDING |
| 3 | Registration + consent onboarding | PENDING |
| 4 | Customer app (wallet, tx detail, profile) | PENDING |
| 5 | Merchant app (terminal view) | PENDING |
| 6 | Admin (customers/merchants/audit) | PENDING |
| 7 | Terminal simulator UI | PENDING |
| 8 | Firmware (ESP32-S3) + HAL mock | PENDING (hardware BLOCKED) |
| 9 | Full QA/security/perf | PENDING |
| 10 | Delivery docs + demo | PENDING |

## Next step
Phase 2: add three/@react-three/fiber/drei/gsap, build `/` landing, keep existing app routes untouched.
