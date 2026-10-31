# BioPay project plan

**SIMULATED — NO REAL MONEY.** BioCoins have no cash value and are never exchanged for money or goods.

A controlled university demonstration: a merchant enters an amount on a physical terminal, a customer authenticates with a fingerprint sensor, and the backend transfers simulated BioCoins exactly once. The customer needs no phone. Team of five, about one week. The college supplies hardware; its exact components are not yet known.

The original Android-based concept is kept as `PROJECT_PLAN_CONCEPT_ANDROID.md` (hardware selection notes there are still useful). **Decision: the customer/merchant/admin client is a responsive web app, not Android.**

## Architecture (one of each, no microservices)

| Part | Choice |
| --- | --- |
| Web app | React + TypeScript + Vite + Tailwind CSS in `web/` |
| Backend | Django 5.2 + Django REST Framework, one app `payments/` |
| Database | PostgreSQL only (row locking is part of the design) |
| Human auth | Django sessions + CSRF, same origin (Vite proxies `/api`; no CORS) |
| Terminal auth | Per-terminal key in `X-BioPay-Terminal-Key` (hash stored); separate from web login |
| Dev-only auth | Shared `X-BioPay-Demo-Token` for the fixed-pair `/api/dev/mock/` routes |
| Terminal firmware | ESP32-S3 + UART fingerprint sensor — **not started, awaiting hardware** |

```
Browser ──/api (session+CSRF)──► Django ──► PostgreSQL
Terminal ─/api/terminal (key)──►   │  one atomic transfer service
```

Roles come from server-side records (`Customer.user`, `Merchant.user`, `is_staff`), never from anything the browser sends.

## Payment flow

1. Merchant enters a whole-number amount on the terminal; it shows the amount.
2. Customer touches the sensor. The sensor matches locally and yields a **sensor slot**. (Today this is simulated and every record is marked `MOCK`.)
3. Terminal posts `{payment_id (UUID), amount, sensor_slot}` with its key. The server derives the payer from the terminal's ACTIVE enrollment for that slot and the merchant from the terminal. The terminal can name neither.
4. One durable PostgreSQL transaction: reserve the UUID, lock the enrollment and both wallets (primary-key order), check funds, write two ledger entries, update balances, store the final result.
5. The terminal shows success only after a 201/200 `SUCCESS`. Retrying the same UUID returns the original result and never transfers twice. The same UUID with different fields returns 409.

## Accounting invariant (checked by `manage.py reconcile` and the admin dashboard)

- Wallet: `opening_balance + sum(ledger deltas) = balance`.
- Payment: `SUCCESS` has exactly two entries summing to 0; `DECLINED` has none.

No endpoint edits a balance. Django admin shows wallets, payments and ledger read-only.

## Status

| Area | State |
| --- | --- |
| Atomic, idempotent transfer service | Done (verified by tests, see README) |
| Login, roles, per-role permissions, CSRF | Done |
| Terminal/enrollment models, revoke, deletion request | Done |
| Customer / merchant / admin dashboards | Done (built and type-checked; not yet reviewed on a real phone) |
| Reconciliation command + admin panel | Done |
| Real fingerprint sensor, firmware, display, keypad | **Blocked on hardware** |
| Enrollment UI at the terminal | Blocked on hardware; today enrollment is created in Django admin (`Enrollments`) with consent recorded |
| BLE / Wi-Fi provisioning | Out of scope for the first demo |
| TLS, hosting, production settings | Not started; needs approval and a hosting choice |
| Real money, UPI/PPI | Out of scope, permanently for this project |

## Suggested split for five people (one week)

1. Hardware bring-up: power, display, keypad, then sensor enroll/search/delete once parts arrive.
2. Firmware: amount entry, call `POST /api/terminal/payments/`, show result only on backend confirmation.
3. Web UI: review on phone/tablet, polish, accessibility pass.
4. Backend: admin workflows, volunteer onboarding with `create_account`, consent paperwork.
5. Demo and test lead: rehearse failure cases (offline, retry, revoked terminal), write the demo script.

## Limits to state in the demonstration

A compromised terminal or sensor can claim a match; TLS and a terminal key prove which device spoke, not that a living person consented. Do not call this production-grade biometric security. Collect no real biometric data on the server (templates stay in the sensor) and obtain consent from volunteers before enrolling.
