# BioPay: Phone-Free Biometric Checkout (IoT college project)

**SIMULATED PAYMENT — NO REAL MONEY.** BioCoins are demo credits with no monetary value. Fingerprint matching in the software demo is a labelled simulation, not real biometric verification. The physical terminal has not been built or tested yet.

## 1. Abstract
BioPay explores paying at a shop by placing a finger on a terminal instead of using a phone. A customer registers, consents, and enrolls a fingerprint on a terminal. At checkout the terminal identifies the enrolled finger, asks the server to move simulated BioCoins from the customer to the merchant, and shows the result. This project delivers the complete web platform and payment engine, verified with a software simulator, plus a tested firmware core ready to connect to an ESP32-S3 and a fingerprint sensor.

## 2. Problem statement
Phone-based payment needs a charged phone, a network and an app, and fails for people who forget or lose the device. Biometric checkout removes the device, but it brings two hard problems: moving money safely (no double charge, no lost update) and protecting biometric data and consent.

## 3. Objectives
1. Build a payment engine where a transfer is atomic and each payment is applied at most once.
2. Keep fingerprint templates off the server: the sensor matches, the server only sees a slot number.
3. Give customers, merchants and admins separate, access-controlled views with an audit trail.
4. Make consent, withdrawal and revocation immediate and enforceable.
5. Prove it with automated tests and a repeatable demo.

## 4. Proposed solution
A Django REST backend on PostgreSQL, a React web app with a Three.js landing page, a terminal API authenticated by a per-device key, and an ESP32-S3 firmware (core logic done, device glue pending).

## 5. System architecture
```
 Finger -> [Sensor] -> [ESP32-S3 terminal] --HTTPS, terminal key--> [Django API] -> [PostgreSQL]
                              (slot + amount + payment UUID)            ^
 Customer / Merchant / Admin browsers -------- session login, CSRF -----+
```
Layers: sensor (matches on-device) → terminal firmware (UUID, retries, display) → API (authentication, validation) → payment service (locks, ledger) → database (constraints).

## 6. Requirements
- Software: Python 3.12, Django, DRF, PostgreSQL 16, Node 20+, React 19, TypeScript, Vite, Three.js (React Three Fiber), GSAP, Playwright.
- Hardware (planned, not verified): ESP32-S3 board, fingerprint sensor module with on-device matching, display and input for the amount. Exact models are not chosen yet.

## 7. Workflow
1. Customer registers and ticks consent; receives starting BioCoins.
2. Enrollment: the sensor stores the template; the server stores only (terminal, slot, consent time).
3. Checkout: merchant enters amount; customer places finger; the terminal sends `{payment_id, amount, sensor_slot}` with its key.
4. Server finds the active enrollment for (terminal, slot), locks wallets in a fixed order, writes a debit and a credit, returns the result.
5. If the reply is lost, the terminal resends the same payment ID; the server answers with the stored result and charges once.

## 8. Database overview
Customer, Merchant, Wallet (balance, opening balance), Terminal (hashed key, revoked time), Enrollment (terminal, slot, status, consent, simulator consent), Payment (UUID primary key, status), LedgerEntry (one debit and one credit per successful payment), AuditEvent. Database constraints: positive amounts, non-negative balances, one live enrollment per slot, one ledger entry per wallet per payment. Reconciliation: opening balance + ledger = balance for every wallet; every payment balances to zero.

## 9. Security and privacy
- No fingerprint template or image reaches the server; a slot number is only meaningful with its terminal.
- Terminal keys are stored as SHA-256 hashes; passwords use Django hashing and a 12-character minimum with common-password checks.
- Roles come from server records, never from the browser. Merchants see customers only as "Customer #n". Customers cannot read others' data (404).
- CSRF protection on state-changing requests; login and registration are rate limited.
- Revoking a terminal or enrollment blocks new payments immediately, even for a payment in flight (row locks). A completed payment retried after revocation returns its original result and never charges twice.
- The merchant simulator needs the customer's explicit per-enrollment opt-in, enforced under the same database lock as the payment. It exists only when DEBUG and the demo flag are on, and must never be enabled on a shared host.
- Every sensitive action is recorded in an audit log (append-only by convention).

## 10. Test results (what actually ran)
See `TEST_REPORT.md` for the latest numbers: 104 backend tests (PostgreSQL, includes concurrency), 18 browser tests (mocked API, includes axe accessibility and overflow at 390/768/1024/1440), one real-stack end-to-end run (real Django + PostgreSQL + Vite) covering the full demo, firmware core tests (native).

## 11. Limitations
- No physical terminal yet: fingerprint matching, wiring and flashing are untested.
- The terminal API only runs in development mode; a real-sensor mode and HTTPS are needed before use on hardware.
- Audit log immutability is by convention, not database enforcement.
- Tested for tens of users on one server, not for scale.
- Accessibility checked with automated tools only (axe) plus a keyboard test; no screen-reader session.
- 3D checked with software rendering; real GPU frame rate unmeasured.

## 12. Future scope
Real sensor integration and liveness checks, HTTPS with device certificates, hardware-backed key storage on the ESP32, refunds, receipts, per-merchant settings, DB-level audit immutability, load testing.

## 13. Demo walkthrough
Follow `docs/DEMO_SCRIPT.md`.

## 14. Viva questions and answers
**Why not store the fingerprint on the server?** A leaked template cannot be changed like a password. Matching on the sensor means the server only gets a slot number.
**What stops a customer being charged twice if Wi-Fi drops?** Every payment has a UUID created and saved on the terminal before sending. A retry reuses it; the server uses the UUID as a unique key and returns the stored result.
**What if two payments hit the same wallet at once?** Wallets are locked in a fixed order inside one transaction, so they queue; balances cannot go negative (database constraint).
**What if a terminal is stolen?** An admin revokes it; the terminal row is locked during payments, so a payment either finished before revocation or is refused after.
**Can a merchant pick whom to charge?** The terminal sends only a slot; the server resolves the person. The software simulator needs the customer's opt-in for that enrollment.
**What if a sensor slot is deleted and reused?** Software enrollments never reuse a slot number, and records are scoped to a terminal and have a status, so an old record cannot silently point to a new person.
**How do you know balances are correct?** Reconciliation recomputes opening balance + ledger for every wallet and checks every payment nets to zero; admins can run it any time.
**Is this real money?** No. BioCoins are simulated, every payment screen says so.
**What is not proven yet?** Everything physical: real sensor matching, device wiring, and the terminal-to-server link on real hardware.
**Why a simulator?** To test the whole software chain before hardware exists. It is clearly labelled and can only run in development mode.
