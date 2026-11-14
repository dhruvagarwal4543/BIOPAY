# BioPay backend review and audit

> Historical review of the first backend slice (27 October 2026). Current results are in `TEST_REPORT.md`.

Verified on 27 October 2026. **SIMULATED — NO REAL MONEY**

What this change does: creates a Django REST Framework backend for a transfer between two fixed demo accounts. It records final payments and balanced ledger entries, handles repeated UUIDs, and exposes token-gated development APIs for payment submission, status, balances, and history.

What this repository does: it contains this initial backend slice and the broader project plan. Assumed load is one demo terminal and merchant; two simultaneous requests are tested to cover retries and overspending. It is not a multi-user biometric or payment-provider integration.

## Scope read

Read settings, URL dispatch, all five models, the initial migration, shared transfer service, serializers, authentication, error handling, API views, demo setup, the test suite, dependency pins, environment template, ignore rules, README, and updated project-plan constraints. Traced the full request through validation, account selection, UUID reservation, row locks, ledger writes, balance updates, commit, and response.

There was no existing code or Git repository to compare against. The code review covers the newly created implementation and its connected callers rather than a historical diff.

## Findings fixed during implementation

1. **Unknown request fields initially returned a server error.** A serializer-level error used a list where DRF expected a dictionary. The API now returns a structured validation error and HTTP 400. The regression checks attempts to supply payer, merchant, balance, or fingerprint fields. Leaving this unfixed would turn ordinary invalid requests into server failures.
2. **DRF accepted numeric and boolean payment IDs.** Its standard UUID field converts integer inputs, including booleans, into UUIDs. The input field now requires a UUID string before parsing. A regression test was run and failed against the old behavior, then passed after the fix. Leaving it unfixed would accept request identities outside the documented contract.
3. **Pagination configuration produced a framework warning.** The page size lacked a default paginator setting. Configuring the existing framework paginator removed the warning without a new pagination implementation.

No unresolved must-fix findings were found within this local-development scope. This review is not an independent penetration test or production-readiness certification.

## Integrity and permission checks

- Payment UUID primary-key uniqueness arbitrates simultaneous requests in PostgreSQL. The existing result is compared against the fixed payer, fixed merchant, and integer amount.
- Both wallet rows are locked in primary-key order before balance checks. Ledger entries, debit, credit, and final status share one outermost durable transaction.
- The API does not receive a payment result from the service until commit succeeds. Injected credit failure and injected commit failure both propagate without returning success or retaining partial writes.
- Database constraints reject ownerless/double-owned wallets, negative balances, nonpositive payment amounts, invalid final results, zero ledger deltas, and duplicate entries for one wallet/payment.
- No public funding, account selection, balance editing, admin interface, or customer credential endpoint exists. Demo-token checks apply to submission and read endpoints.
- Mock APIs return 404 unless explicitly enabled with debug mode. Invalid/missing tokens return 401; an empty token fails closed. Unknown input fields are rejected.
- Demo history and status are restricted to the fixed demo account pair; history is paginated. Wallet reads use one SQL statement for a consistent committed snapshot of both balances.
- Example configuration contains placeholders only. Temporary verification secrets were generated outside the repository; no `.env` containing real secrets was added. PostgreSQL tests used a separate local cluster with TCP listening disabled.

## Executed environment and commands

Environment: Python 3.12.13, Django 5.2.18, Django REST Framework 3.17.2, psycopg 3.3.6, PostgreSQL 16.15 on macOS ARM64. Runtime dependencies are pinned in `requirements.txt`.

Preparation and checks actually executed:

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python 'Django>=5.2,<5.3' 'djangorestframework>=3.16,<3.18' 'psycopg[binary]>=3.2,<3.4'
.venv/bin/python manage.py makemigrations payments
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py check --fail-level WARNING
.venv/bin/python manage.py makemigrations --check --dry-run
uv pip check --python .venv/bin/python
.venv/bin/python -m compileall -q biopay_backend payments manage.py
.venv/bin/python manage.py test payments --verbosity 2 --noinput
```

Commands used exported temporary test configuration. An isolated cluster was initialized with `initdb --auth-local=trust --auth-host=reject --username=biopay --encoding=UTF8 --locale=C`, started with `pg_ctl` using a private Unix socket and no TCP listener, and given a `biopay` database with `createdb`. Its filesystem permissions restricted access to the current user. Django created/destroyed `test_biopay` for each test run. Existing user databases were not touched.

A loopback Django development server was also started with `manage.py runserver 127.0.0.1:<temporary-port> --noreload`. A Python HTTP client exercised the running API with assertions and then terminated that server. The temporary database and verification secrets were removed after verification; no server is left running. Follow README to configure your own local database and environment.

## Results

| Check | Actual result |
| --- | --- |
| Initial PostgreSQL migration | Passed. |
| System checks | Passed, zero issues after pagination fix. |
| Pending migration check | Passed, no changes detected. |
| Dependency compatibility | Passed for all seven installed packages. |
| Python compilation | Passed. |
| Full final test run | **25 tests passed against PostgreSQL; zero failures or skips.** |
| Simultaneous same-UUID requests | Passed: one 201, one 200; one transfer and two ledger entries. |
| Simultaneous conflicting amounts | Passed: one 201, one 409; one transfer. |
| Simultaneous overspending | Passed: one 201, one 422; balance remained nonnegative. |
| Failure after ledger writes and debit | Passed: payment, entries, and debit rolled back; retry then succeeded. |
| Commit failure | Passed: no successful API result and no retained transfer. |
| Live HTTP flow | Passed: 201 new payment, 200 replay, 409 conflict, status/history correct, unauthenticated read 401. |
| Live balances and repeated seed | Passed: customer 460, merchant 40, unchanged by another seed run. |

Earlier checks did fail before fixes: the initial suite reported five unknown-field subtest errors, and the added strict-UUID regression exposed accepted integer/boolean IDs. Both were fixed; the final complete run passed. The concurrency tests used two independently verified PostgreSQL backend process IDs, synchronized inside the transaction before UUID insertion. No SQLite concurrency result is claimed.

## Limits retained deliberately

- One shared mock token and one fixed account pair. The code labels this shortcut. It does not authenticate a customer, merchant, device, or fingerprint.
- No public deployment, TLS termination setup, enrollment, consent lifecycle, device revocation, hardware, app, provider integration, or real money.
- Opening funds are stored separately from transfer entries; they are not claimed as a funded real-money deposit. All API transfers reconcile against these opening balances.
- Ledger balancing is enforced by the transfer service and tests, not a cross-row database trigger. Privileged direct database writes can violate it; no public write path bypasses the service.
- Unexpected server failures use Django's error handling. Resolve an uncertain result by querying/retrying the same UUID. This slice does not implement terminal persistence or checkout expiry.
- Do not change the development limit while retrying outstanding requests, delete ledger/seed data, or reuse this configuration for a volunteer pilot.

Verdict: ship this backend slice for local simulated testing. Add real identity and device authorization before a user/device pilot.

Not checked: physical hardware, biometric correctness, production load/deployment, or real-money/regulatory suitability. No dependencies or PostgreSQL access blocked verification.


---

# Hardening pass (30 October 2026) — web, terminal and revocation

**SIMULATED — NO REAL MONEY.** This section covers the web/terminal work added after the backend slice above. Results below were produced by running the commands on this machine (Python 3.12.13, Django 5.2.18, PostgreSQL 16, Node 22). The earlier "25 tests" claim was independently reproduced first (25 of 25 passed on PostgreSQL) before any change.

## Fixed

1. **Enrollment identity is immutable in Django Admin.** After creation only `status` is editable (`EnrollmentAdmin.get_readonly_fields`). Tested at the method level and by POSTing changed customer/terminal/slot/consent/source to the real admin form: nothing changed.
2. **Expired sessions redirect to login.** The API now answers 401 when there is no valid session and 403 only for a signed-in user who lacks permission or fails CSRF (`WebSessionAuthentication`). The web client redirects on 401 only, never for the login call and never when already on `/login`. Backend semantics are tested; the redirect itself is three lines in `web/src/api.ts` and was **not** exercised in a browser.
3. **Terminal revocation race closed.** `pay_at_terminal` now locks the terminal row and checks `revoked_at` inside the payment transaction. Revoking a terminal updates the same row, so a revoke either commits first (payment refused, nothing written) or waits for the in-flight payment. Lock order: terminal → enrollment → payment → wallets by pk. No cycle exists.
4. **Race tests added** (`TerminalRevocationRaceTests`, PostgreSQL asserted, never SQLite). Two deterministic tests were confirmed to **fail with the fix removed** and pass with it restored. A third randomized test accepts only "payment won, balanced" or "revoke won, no ledger rows" over 5 rounds, with `reconcile` clean each time. That randomized test is not by itself proof of the lock; the two deterministic ones are.
5. Cleanup: removed unused `recent_payments`; a missing wallet now returns 503 `demo_not_ready` instead of a server error.

## Results

| Check | Result |
| --- | --- |
| `manage.py check --fail-level WARNING` | 0 issues |
| `makemigrations --check` | no changes |
| Full backend suite | **65 tests, OK** (25 original, 40 new) |
| Original payment/idempotency/concurrency module | 25 tests, OK |
| New race tests, 3 consecutive runs | 3 of 3 passed each time |
| `manage.py reconcile` on the dev database | OK |
| `tsc -b` / `npm run build` | passed |
| `npm run lint` | 0 errors, 3 warnings (two fast-refresh export warnings, one set-state-in-effect in `useApi`; left as is) |

## Still open

- No frontend automated tests; the UI has not been viewed in a browser or on a phone.
- Staff can set a terminal's `revoked_at` back to empty in Django Admin (un-revoke). Treat admin accounts as trusted.
- A replay after an enrollment is revoked returns 403 even if the original payment succeeded.
- Not checked: hardware, TLS/production settings, real biometric behavior, load beyond the demo.

---

# Lifecycle, replay and browser-test pass (30 October 2026)

**SIMULATED — NO REAL MONEY.** Results from commands run on this machine.

- **Terminal revocation is one way.** `revoked_at` is read-only in Django Admin and `Terminal.save()` refuses to clear it. `replace_terminal` issues a new key and records `replaces`; re-running it revokes the earlier replacement. Queryset `.update()` and raw SQL can still bypass the model guard (privileged access only).
- **Replay after enrollment revocation now returns the stored result** (same terminal, UUID, amount and sensor slot), writes nothing, and never works for a revoked terminal or another terminal. The old 403 was a contract gap: a terminal that lost the reply could not learn that the customer had been charged. `Payment.sensor_slot` was added (migration 0003).
- **Browser tests:** 7 Playwright tests in real Chrome with a mocked API. They test web behaviour only, not the backend or a fingerprint sensor.
- Both new protections were checked by temporarily removing them: the lifecycle/replay tests then failed (7 failures) and the browser redirect tests failed as intended.
- The Ponytail audit found the dev database had not yet applied migration 0003 (tests use their own database, so they could not show it). It was applied with `migrate` (additive, no data removed).

| Check | Result |
| --- | --- |
| `check --fail-level WARNING` / `makemigrations --check` | clean / no changes |
| Full backend suite on PostgreSQL | **80 tests, OK** |
| Original payment module / race tests x3 | 25 OK / 3 OK each run |
| `reconcile` on the dev database | OK |
| `tsc -b`, `npm run build` | passed |
| `npm run lint` | 3 warnings (pre-existing), no errors |
| `npm run test:e2e` | **7 passed** (Chrome) |

Not checked: real hardware, a real fingerprint sensor, TLS/production settings, load, other browsers or phones.
