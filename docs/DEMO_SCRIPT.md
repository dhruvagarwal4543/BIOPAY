# Live demo script (about 8 minutes)

Prerequisites: macOS or Linux, PostgreSQL 16+ running locally, Python 3.12, Node 20+. The script checks these and prints what is missing.

Setup (once): PostgreSQL running; `python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`; `cd web && npm install`.
Start: `scripts/demo.sh start` (isolated database `biopay_demo`, never your real data). Password: `scripts/demo.sh creds`. Reset to a clean state: `scripts/demo.sh reset && scripts/demo.sh start`. Stop: `scripts/demo.sh stop`.

1. Open http://127.0.0.1:5173/ . Scroll through the six scenes (identity, scan, transaction, wallet, ecosystem, call to action). Note "SIMULATED PAYMENT — NO REAL MONEY".
2. Click Sign in -> Create an account. Fill the form, tick consent, register. You land on your wallet with 100 BioCoins.
3. Under enrollment tick the consent boxes (including the simulator opt-in) and press Enroll (MOCK). Note your "Mock fingerprint slot" number.
4. Sign out. Sign in as `demo-merchant` (password from `scripts/demo.sh creds`). Open Simulator.
5. Enter your slot and amount 60, Pay: SUCCESS, confirmed by the server.
6. Press "Resend the same payment": the server says replayed, charged once (idempotency).
7. Pay 60 again: DECLINED, insufficient BioCoins (balance is 40). Try slot 9999: refused.
8. Merchant dashboard: payments listed with an anonymous "Customer #n"; open one for details.
9. Sign in as your customer: balance 40, history shows SUCCESS and DECLINED. Switch "Merchant simulator" OFF; as merchant, a new payment is refused (consent withdrawn).
10. Sign in as `demo-admin`: Ledger reconciliation = SUCCESS; Audit log shows register, enroll, simulator off. Revoke an enrollment and show payments stop.
Automated version of this flow: `node web/e2e-real/demo.mjs`.

## Troubleshooting
- `PostgreSQL is not running`: start it (for Homebrew: `brew services start postgresql@16`).
- `Port 8000/5173 is used by another program`: stop that program; the script only ever stops its own processes (pids in `.demo-pids`).
- Login fails after a reset: the password changes on every reset; run `scripts/demo.sh creds`.
- Blank 3D area: the browser has no WebGL or reduced-motion is on; the page still works as plain sections.
- Logs: `/tmp/biopay-django.log`, `/tmp/biopay-vite.log`.
- Something stuck: `scripts/demo.sh stop` then `scripts/demo.sh start`; for a clean slate `scripts/demo.sh reset` (drops only the `biopay_demo` database).

## Known limitations
Simulated BioCoins only; mock fingerprint (no real sensor); the simulator and mock enrollment exist only when `DEBUG` and the demo flag are on and must never be enabled on a shared host; physical hardware not yet integrated.
