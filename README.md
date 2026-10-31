# BioPay backend

**SIMULATED — NO REAL MONEY**

This first backend slice transfers integer BioCoins between one fixed demo customer and one fixed demo merchant. BioCoins have no cash value. Never exchange them for money or actual goods.

Fingerprint authentication is **simulated** (every payment and enrollment is marked `MOCK`) until the college hardware arrives. The mock APIs are disabled by default and also require Django debug mode. Keep the server on your private development machine. This is not the volunteer-ready or production backend.

Architecture and status: see `PROJECT_PLAN.md`. A React web app lives in `web/` (section "Web application" below).

## Prerequisites

- Python 3.12 or newer supported by the pinned dependencies.
- PostgreSQL 16 or newer, running locally, with `psql` available.
- A PostgreSQL role that owns the development database and has `CREATEDB` for Django's separate test database. Use a dedicated local role, not production credentials.

PostgreSQL is the only configured database. There is no SQLite fallback. Tests fail if PostgreSQL is missing or inaccessible.

## Install

From this directory:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

If using an existing environment created by `uv`, install with `uv pip install --python .venv/bin/python -r requirements.txt` instead. A uv-created environment may not contain pip.

## Configure PostgreSQL

Connect with your local PostgreSQL administrator account. For a local installation this may be `psql -d postgres`; on other installations use `psql -U postgres -d postgres` or your configured administrator name.

Run once in `psql`:

```sql
CREATE ROLE biopay LOGIN NOSUPERUSER NOCREATEROLE CREATEDB;
\password biopay
CREATE DATABASE biopay OWNER biopay;
\q
```

The `\password` prompt avoids putting the database password in shell history. `CREATEDB` is for this local test role only. Tests create and destroy `test_biopay`, not `biopay`. Do not point tests at shared or production servers.

## Set environment variables

Generate a Django secret and a separate demo token. Run this twice, and use a different result for each value:

```sh
python -c 'import secrets; print(secrets.token_urlsafe(50))'
```

Edit `.env`:

| Variable | Set to |
| --- | --- |
| `DJANGO_SECRET_KEY` | First generated secret. The example placeholder is rejected. |
| `DJANGO_DEBUG` | `true` for local development. |
| `DJANGO_ALLOWED_HOSTS` | `127.0.0.1,localhost`. |
| `PGDATABASE`, `PGUSER` | `biopay`, or your dedicated local names. |
| `PGPASSWORD` | Password entered at the PostgreSQL prompt. |
| `PGHOST`, `PGPORT` | Usually `127.0.0.1` and `5432`. A local Unix socket directory also works as `PGHOST`. |
| `BIOPAY_ENABLE_DEMO_API` | Change `false` to `true` to explicitly enable mock endpoints locally. |
| `BIOPAY_DEMO_TOKEN` | Second generated secret, at least 32 characters. |
| `BIOPAY_MAX_PAYMENT` | `100` BioCoins by default, a positive signed 64-bit integer. |

Keep shell values quoted as in the example. `.env` is ignored by Git; never share or commit it. Django reads exported environment variables, not `.env` automatically. Load your trusted local file in every new shell:

```sh
source .venv/bin/activate
set -a
source .env
set +a
```

## Migrate and run

```sh
python manage.py migrate
python manage.py seed_demo
python manage.py check
python manage.py runserver 127.0.0.1:8000
```

`seed_demo` creates `demo-customer` with 500 BioCoins and `demo-merchant` with 0. Repeating it keeps current balances, including after payments. There is no public funding or balance-edit endpoint and no generated login/password.

The customer wallet records `opening_balance=500`. Seed funds are opening data, not a payment or a transfer from a fictitious funding wallet. Reconcile each wallet as `opening_balance + sum(ledger deltas) = balance`. All later successful payments have one debit and one credit whose sum is zero. Do not delete demo records and expect seeding to restore their history.

## API examples

In another terminal, activate the environment and export `.env` as above. The token goes in a header, never in a URL. These examples use loopback HTTP only; do not transmit this shared token over an untrusted network.

Check initial balances:

```sh
curl -sS http://127.0.0.1:8000/api/dev/mock/wallets/ \
  -H "X-BioPay-Demo-Token: $BIOPAY_DEMO_TOKEN"
```

Create one payment ID and transfer 40 BioCoins:

```sh
PAYMENT_ID=$(python -c 'import uuid; print(uuid.uuid4())')
curl -sS -i http://127.0.0.1:8000/api/dev/mock/payments/ \
  -H "X-BioPay-Demo-Token: $BIOPAY_DEMO_TOKEN" \
  -H 'Content-Type: application/json' \
  --data "{\"payment_id\":\"$PAYMENT_ID\",\"amount\":40}"
```

Expected first response, with generated IDs and timestamp:

```json
{
  "warning": "SIMULATED — NO REAL MONEY",
  "authentication": "MOCK — NO BIOMETRIC VERIFICATION",
  "payment": {
    "payment_id": "<the UUID you supplied>",
    "payer_id": 1,
    "merchant_id": 1,
    "amount": 40,
    "status": "SUCCESS",
    "decline_reason": "",
    "created_at": "<UTC timestamp>"
  },
  "replayed": false
}
```

Balances become customer 460 and merchant 40. Repeat the same curl payment command with the same `PAYMENT_ID`: it returns the existing payment with `replayed=true` and does not transfer again. Use the same ID after a timeout; do not generate a replacement ID to retry an uncertain payment.

Query final status and paginated history:

```sh
curl -sS "http://127.0.0.1:8000/api/dev/mock/payments/$PAYMENT_ID/" \
  -H "X-BioPay-Demo-Token: $BIOPAY_DEMO_TOKEN"
curl -sS 'http://127.0.0.1:8000/api/dev/mock/history/?page=1' \
  -H "X-BioPay-Demo-Token: $BIOPAY_DEMO_TOKEN"
```

History contains up to 20 demo payments per page, newest first, including declines. No caller can select a different payer or merchant. Additional request fields are rejected. Only JSON integer amounts are accepted; strings, decimals (including `40.0`), booleans, zero, and negative values are rejected.

| HTTP status | Meaning and stable error code |
| --- | --- |
| `201` | New successful payment. |
| `200` | Successful payment replay or a successful GET. |
| `400` | Validation error: `invalid_request`; malformed JSON: `parse_error`. |
| `401` | Missing or incorrect mock token: `authentication_failed`. |
| `404` | Demo disabled or a payment not found: `not_found`. |
| `409` | UUID already used with different canonical payment fields: `payment_conflict`. |
| `422` | Final declined payment: `insufficient_funds`, including repeated requests. |
| `503` | Demo accounts/wallets are missing: `demo_not_ready`. |

Handled API errors use `{"error":{"code":"...","message":"..."}}`, with field details for validation errors. A decline also includes its saved payment and replay flag. The simulation and mock-auth labels accompany handled responses. Unmatched URLs and unexpected server errors use Django's error handling; a server error is never a successful payment confirmation. Query or retry the same UUID to resolve uncertainty. A missing status result may race with a still-running request.

## Transaction behavior

The payment UUID is also the unique duplicate-request reference. Its canonical request is the UUID, fixed customer, fixed merchant, and amount. UUID text is parsed to a UUID before comparison.

`payments/services.py` owns the transfer. One outermost durable database transaction reserves the UUID using its primary-key constraint, locks both wallets in ascending primary-key order, checks funds, writes ledger entries, updates balances, and saves the final result. Exceptions roll back all of it. The service returns to the API only after commit. Django's `get_or_create` resolves simultaneous UUID inserts through a database uniqueness constraint and a savepoint, rather than a memory lock.

Other requests cannot see the tentative row while that transaction is uncommitted. Only final `SUCCESS` and `DECLINED` results persist. A declined UUID stays declined; a changed amount requires a new checkout with a new ID. Development limits are checked on each submission, so do not change the configured limit while testing retries of outstanding requests.

Wallet ownership and nonnegative balances have database constraints. Balanced ledger pairs are written by the shared service and checked by tests; privileged direct SQL/ORM writes can bypass those cross-row rules. No API or admin interface exposes those writes.

## Automated checks

After loading your local environment, run:

```sh
python manage.py check --fail-level WARNING
python manage.py makemigrations --check --dry-run
python manage.py test payments --verbosity 2 --noinput
cd web && npx tsc -b && npm run lint && npm run build
cd web && npm run test:e2e     # real Chrome, API mocked; see below
```

To run only the concurrent request tests:

```sh
python manage.py test payments.tests.test_payments.PaymentConcurrencyTests --verbosity 2 --noinput
```

The concurrency tests use two separate PostgreSQL connections and synchronize requests inside their transactions before the UUID inserts. They assert that the engine is PostgreSQL; they do not silently skip or use SQLite. Other tests cover integer validation, replay/conflict, atomic rollback after a debit, commit failure, insufficient funds, seed repetition after spending, account constraints, history scope/pagination, and mock-token/enablement boundaries.

If database creation is denied, grant `CREATEDB` to the dedicated local test role or use a different dedicated local role that has it. If PostgreSQL or dependencies are unavailable, the backend is not verified: fix the setup and rerun the complete suite.

## Web application and accounts

### Run it (two terminals)

```sh
# 1. backend (from this directory, env loaded as above)
python manage.py migrate
python manage.py runserver 127.0.0.1:8000

# 2. web app
cd web && npm install && npm run dev      # http://127.0.0.1:5173
```

Open the Vite URL, not port 8000. Vite proxies `/api` to Django, so the browser sees one origin (session cookie + CSRF, no CORS). Use `127.0.0.1` or `localhost` consistently. `cd web && npm run build` type-checks and builds to `web/dist`.

### Create demo accounts without exposing credentials

```sh
export BIOPAY_DEMO_PASSWORD='choose-12+-chars'     # not stored in code; never printed
python manage.py seed_demo_users
```

Creates logins `demo-customer`, `demo-merchant`, `demo-admin` (staff), the two wallets (customer 500, merchant 0), one terminal and one MOCK enrollment on sensor slot 1. It prints the terminal key **once**; only its hash is stored. Re-running never overwrites a password or balance. Other accounts: `BIOPAY_NEW_PASSWORD=... python manage.py create_account customer|merchant <code> "<Name>"` (zero balance; there is no funding path). More terminals: `python manage.py create_terminal <merchant-code> "<name>"`. Supervised enrollment and consent records: Django admin at `/admin/` (Enrollments), logged in as `demo-admin`. Once an enrollment exists only its `status` is editable; its customer, terminal, sensor slot, consent time and source are read-only. To change who a slot belongs to, revoke the enrollment and create a new one so the consent trail stays intact.

### Web API (session login; unsafe methods need the `X-CSRFToken` header)

Status codes the browser relies on: **401** = no valid session (never signed in, expired, logged out, or account disabled), so the web app redirects to `/login`; **403** = signed in but not allowed (wrong role, or a failed CSRF check), shown as a message with no redirect. A wrong password on login is a 401 with an error message and does not redirect.

| Endpoint | Who |
| --- | --- |
| `GET /api/auth/csrf/`, `POST /api/auth/login/`, `POST /api/auth/logout/`, `GET /api/auth/me/` | anyone / signed in |
| `GET /api/customer/overview/`, `GET /api/customer/payments/`, `POST /api/customer/enrollments/<id>/deletion-request/` | customer (own data only) |
| `GET /api/merchant/overview/`, `GET /api/merchant/payments/` | merchant (own data only; customer names are hidden) |
| `GET /api/admin/overview/`, `GET /api/admin/payments/`, `POST /api/admin/terminals/<id>/revoke/`, `POST /api/admin/enrollments/<id>/revoke/` | staff only |

No endpoint takes a customer, merchant or wallet id from the browser as an authorization input. Another customer's enrollment id returns 404.

### Simulated terminal contract

`POST /api/terminal/payments/` with header `X-BioPay-Terminal-Key: <key>` and JSON `{"payment_id": "<uuid string>", "amount": 40, "sensor_slot": 1}`. Extra fields (e.g. a payer or merchant) are rejected with 400. `GET /api/terminal/payments/<uuid>/` returns that terminal's own payment.

| Status | Meaning |
| --- | --- |
| 201 | New SUCCESS payment. Show success. |
| 200 | Replay of the same request; same stored result. |
| 401 | Missing, wrong or revoked terminal key, including a revoke that commits while the request is in flight (`terminal_revoked`). |
| 403 `enrollment_inactive` | No ACTIVE enrollment for that slot (unknown, deletion requested or revoked). |
| 409 | UUID already used with a different amount or payer. |
| 422 `insufficient_funds` | Final decline. |

Every response carries `authentication: "MOCK — DEVELOPMENT SIMULATION — NOT A PHYSICAL FINGERPRINT MATCH"`. The endpoint returns 404 unless `DJANGO_DEBUG=true` and `BIOPAY_ENABLE_DEMO_API=true`, so the mock cannot be deployed as if it were a sensor. The older shared-token routes under `/api/dev/mock/` still exist for the fixed demo pair and use a separate credential.

### Terminal lifecycle (revocation is one way)

A revoked terminal is never reactivated. Its `revoked_at` is read-only in Django Admin, and `Terminal.save()` refuses to clear it. If a terminal must come back, issue a replacement: `python manage.py replace_terminal <terminal_id>` revokes the old one (and any earlier replacement), creates a new terminal with a **new** key (printed once) and records `replaces` for the audit trail. Enrollments are not copied; enroll customers again on the new terminal under supervision. Revoke from the admin dashboard or the same command.

### Replaying a payment after its enrollment is revoked

If the terminal lost the reply and retries after the customer's enrollment was revoked (or deletion was requested), the same request returns the **original stored result** (`200`, `replayed: true`; a stored decline stays `422`). Nothing is written, so no second debit or credit is possible. This works only for the same terminal with the same payment UUID, amount and sensor slot; any other combination is `409`, a brand-new UUID is `403 enrollment_inactive`, and a revoked terminal always gets `401` and never sees payment details.

### Lock order (payment path)

`terminal → enrollment → payment row → wallets (ascending pk)`. `pay_at_terminal` locks the terminal row and checks `revoked_at` inside the payment transaction; revoking a terminal updates that same row, so a revoke either commits first (payment refused, nothing written) or waits until the in-flight payment commits. Revocation and deletion requests lock only a single row each, so no cycle exists.

### Reconciliation

```sh
python manage.py reconcile    # exits non-zero on any mismatch; the admin dashboard shows the same result
```

### Browser tests (`web/e2e`)

`cd web && npm run test:e2e` runs 7 Playwright tests in the locally installed **Google Chrome** (`channel: 'chrome'`; on a machine without Chrome run `npx playwright install chromium` and remove that line). The API is mocked at the network layer, so they check the web app's behaviour (login, 401 redirect without loops, 403 not logging out, navigation, SUCCESS/DECLINED/empty/error states) and prove nothing about the backend, the database or any fingerprint sensor.

### Not implemented (hardware or approval needed)

Physical fingerprint sensor, ESP32 firmware, terminal screen/keypad, BLE provisioning, TLS/hosting, production settings, any real-money integration.

## Files and limits

```text
biopay_backend/       Settings, root URLs, WSGI entry point
payments/models.py    Five models and database constraints
payments/services.py Atomic simulated transfer
payments/views.py    Four development API views
payments/tests/      PostgreSQL integration and concurrency tests
payments/migrations/ Initial schema migration
payments/management/commands/seed_demo.py
.env.example         Environment template without real credentials
requirements.txt     Pinned runtime dependencies
REVIEW_AND_AUDIT.md   Review scope, commands, and recorded verification
PROJECT_PLAN.md      Broader project plan and updated constraints
```

The full project has five teammates, roughly one week remaining, and college hardware whose exact components are unknown. This backend slice is deliberately separate from Android, ESP32, BLE, and real-money work. There is no biometric verification (it is simulated), no refunds, no funding API, and no production deployment configuration here. It is a local backend demonstration; do not invite volunteers to supply biometric data to it.

For framework behavior used here, see the official [Django transaction guide](https://docs.djangoproject.com/en/5.2/topics/db/transactions/), [Django row-locking API](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update), and [DRF serializer field documentation](https://www.django-rest-framework.org/api-guide/fields/). Runtime versions are pinned in `requirements.txt`.
