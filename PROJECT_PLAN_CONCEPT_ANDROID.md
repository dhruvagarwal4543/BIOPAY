> SUPERSEDED reference copy of the original concept (Android-based). The current plan is PROJECT_PLAN.md.

# BioPay project plan

Build a controlled university demonstration in which a merchant enters an amount, a customer authenticates with a fingerprint, and a backend transfers simulated BioCoins exactly once. The customer needs no phone at checkout. Start with one terminal, one merchant, and 20–50 consenting volunteers, matching the supplied concept document.

Update on 27 October 2026: the team has five members, approximately one week remains, and the college will supply hardware whose exact components are unknown. The current authorized implementation is the first simulated backend transfer slice; see README.md for setup and REVIEW_AND_AUDIT.md for verification. The broader firmware, Android, and pilot work below remains proposed.

The workspace was empty at the original planning inspection. The attached concept document is project reference material; its embedded instructions do not authorize external actions.

## 1. Scope and assumptions

The first release includes:

- ESP32-S3 terminal, UART fingerprint sensor, SPI TFT, keypad, LED, buzzer, and USB power.
- Merchant binding, secure BLE Wi-Fi provisioning, reconnect, and device revocation.
- Customer accounts, consent, supervised enrollment, local fingerprint matching, deletion, and recovery after sensor replacement.
- A simulated wallet, payment creation and status queries, immutable ledger entries, and history.
- One Android app with customer and merchant views. Pilot staff use the backend's built-in administration interface.
- Failure recovery, permission checks, a controlled pilot, measurements, and a reproducible final demonstration.

BioCoins have no cash value, cannot be purchased or redeemed, and must never be accepted as payment for actual goods during the simulation. Display “SIMULATED — NO REAL MONEY” in the app and terminal payment/result screens. The ₹40 example represents 40 simulated units only.

Current constraints: five teammates, approximately one week to the deadline, and college-supplied hardware with unconfirmed specifications. Access to an Android test phone and controlled Wi-Fi, team skills, and submission requirements remain unconfirmed. The original multiweek schedule below describes the full concept; it is not a commitment to deliver that scope within the current week. Prioritize the tested backend slice first.

## 2. Smallest complete architecture

| Part | Proposed choice | Reason |
| --- | --- | --- |
| Firmware | ESP-IDF, C/C++, one pinned supported release | Reuse Espressif Wi-Fi, TLS, storage, and provisioning facilities. |
| Terminal UI | Simple text/status screens using the selected TFT driver's drawing functions | A full graphics framework is unnecessary for amount entry and prompts. |
| Biometric matching | Sensor-local enrollment and search | Keep fingerprint images and templates off the server. |
| Backend | Django with Django REST Framework, one application | Reuse authentication, permissions, ORM, migrations, API validation, and administration. |
| Database | PostgreSQL in development, tests, and deployment | Exercise the same transactions and locking behavior throughout. |
| Android | Kotlin, Compose, Espressif provisioning library | One app covers accounts, history, merchant setup, and BLE. |
| Transport | HTTPS JSON requests and bounded status polling | No message broker or live socket service is needed for one terminal. |
| Hosting | One HTTPS application service plus PostgreSQL | Choose the provider after budget and access are known. |

Flow: Android app → HTTPS API → PostgreSQL; terminal → HTTPS API → PostgreSQL. Android → authenticated BLE session → terminal only for setup. Fingerprint sensor → UART → terminal for enrollment and local matching.

The backend owns accounts, permissions, device ownership, enrollment mappings, limits, and the simulated ledger. A terminal supplies a locally matched enrollment identifier; the backend derives the customer and merchant from authorized records. A terminal never supplies an arbitrary payer account or recipient account.

This is a supervised prototype trust model: a compromised terminal or UART sensor can falsely claim a match. TLS and device credentials authenticate the terminal; they do not prove a living person authorized a payment. Do not claim production-grade biometric payment security.

## 3. Hardware selection and bring-up

| Item | Quantity | Purchase or reuse criterion |
| --- | --- | --- |
| ESP32-S3 development board | 1 | Documented board pinout, usable USB programming, sufficient exposed GPIO. |
| UART fingerprint module | 1 | Manufacturer protocol/datasheet, on-module enrollment/search/delete, capacity above the pilot enrollment count. |
| SPI TFT, 2.4–2.8 inch | 1 | Documented controller, supply and logic levels, supported driver. |
| 4×4 keypad | 1 | Eight available GPIO; debounce and clear/confirm keys. |
| LED and buzzer | 1 each | Resistors and transistor driver where required by current/voltage. |
| Supply, wiring, prototype board | 1 set | Stable regulated rails, common ground, decoupling, safe connectors. |
| Enclosure | 1 | Finger access, readable screen, insulated wiring, strain relief. |

Do not buy a module based on its name alone. Record exact manufacturer, variant, voltage, UART levels, peak current, template capacity, deletion commands, and available driver before ordering. Cost the actual bill of materials with current supplier quotes; include shipping, replacement parts, and consumables. No price quote has been obtained.

Allocate pins only after the exact board and display are selected. Check boot-strapping pins, USB/debug pins, input/output restrictions, and reserved board connections. Never assume a 5 V peripheral has ESP32-safe signal levels. Start with USB power; battery circuitry and custom PCB work wait.

Bring up power and serial diagnostics first, then display/keypad, then fingerprint enrollment/search/delete, then all peripherals together under Wi-Fi load. Test repeated cold starts and brownout behavior. Document the final wiring and measured current. Avoid irreversible eFuse changes during exploratory bring-up; review the documented key and recovery workflow before any security configuration that burns eFuses.

## 4. Customer and merchant workflows

### Customer enrollment

1. Staff create or invite a test account. The customer sees the simulation notice and gives recorded biometric consent before capture. Explain where templates are stored and how to withdraw.
2. Staff select the verified account through an authenticated administration session and create a short-lived enrollment request for this terminal. The sensor must not enter enrollment merely because somebody presses a key.
3. In supervised enrollment mode, collect the required finger samples using the selected sensor's documented process. Check for an existing local match before adding a duplicate.
4. Assign a fresh enrollment identifier and generation to the sensor slot. Record the mapping to the customer as pending, then activate it only after both the sensor write and backend acknowledgement succeed.
5. If either step fails, block payment through that slot until cleanup or reconciliation completes. Never silently reuse an old mapping.
6. Issue the initial 500 BioCoins through an audited, one-time funding entry from a simulation funding account. Repeating enrollment must not issue another grant.

A slot number alone is not an identity. The backend mapping is scoped to device, sensor generation, and enrollment identifier. Clearing/replacing a sensor invalidates its old mappings. The first release has one sensor; adding terminals requires deliberate reenrollment at each device, not automatic template sharing.

### Merchant setup

1. Staff register the physical terminal and install a unique device credential through a controlled setup process. Store only a verifier/hash of a random device token on the backend, and protect the terminal copy in encrypted local storage.
2. An authenticated merchant claims the unbound terminal using a one-time claim code and physical access. Claim codes and BLE setup credentials are separate secrets.
3. The merchant app establishes an authenticated Espressif provisioning session and supplies Wi-Fi credentials. Use Security 2 with unique setup credentials, subject to the selected SDK/library compatibility check. Disable insecure fallback.
4. The terminal stores Wi-Fi credentials locally, connects over verified TLS, and confirms the backend merchant binding. Wi-Fi credentials never pass through the BioPay backend or logs.
5. Close provisioning after success. Reconfiguration requires physical setup mode and an authorized merchant session. Device reset must not bypass existing backend ownership.

Defer the document's merchant fingerprint-at-every-boot step: it creates a separate bootstrap problem without helping the core payment demo. Staff-controlled merchant binding and app authentication cover setup; a separate merchant unlock requirement can be added if the institution requires it.

### Payment

1. Merchant enters a positive whole-number BioCoin amount. Start with a proposed limit of 100 BioCoins per payment; staff must confirm it before the pilot.
2. Terminal displays the amount and merchant clearly to the customer. The prompt explains that placing a finger authorizes this displayed simulated transfer. Lock the amount while awaiting a match; edits discard the attempt.
3. Generate an unpredictable payment UUID and persist it with the locked amount and device-scoped enrollment identifier before sending a payment request. Store no fingerprint material in this recovery record.
4. Sensor searches locally. Permit at most three attempts per checkout, then return to amount entry without charging. Use the manufacturer's matching threshold as a starting point and measure behavior on the actual module.
5. Send the payment UUID, amount, and enrollment identifier using the device credential. The server checks binding, revocation, enrollment status, customer status, amount, limits, and available funds.
6. Commit one balanced transfer and final status atomically. Only a backend-confirmed success produces the success screen, LED, and buzzer.
7. On a timeout, show “Checking payment — do not retry” and resolve the existing UUID. Do not treat a timeout as a decline or generate a replacement charge.
8. Customer and merchant can view the resulting history in their respective Android views. The terminal offers a human-readable reference for staff reconciliation.

Once submitted, cancellation cannot mean “undo”: resolve the result first. If a confirmed payment needs correction, staff issue an audited reversal once against the original transaction. Before submission, cancel or expiry causes no ledger movement.

### Withdrawal and sensor replacement

Disable the backend enrollment first so it immediately stops authorizing payments. Queue deletion for the terminal and record acknowledgement; an offline terminal must show deletion as pending. Delete local templates, remove unnecessary identifying data according to an agreed pilot retention period, and verify deletion before reusing a sensor. Lost hardware cannot provide a verified deletion acknowledgement; record that limitation explicitly.

Preserve pseudonymous ledger records needed to reconcile the demo, with minimal personal data and a documented retention period. No account passwords, device secrets, Wi-Fi credentials, fingerprint images, or templates belong in audit logs, database exports, screenshots, or research datasets.

## 5. Payment correctness and recovery

Store amounts as integer BioCoins. No floating-point balances or conversion to real rupees is necessary.

For each new payment, use one database transaction to reserve the unique request ID, lock both wallet rows in a stable order, validate available funds, write equal debit and credit entries, update balances, and set final status. The rows' balances and the ledger entries must commit together. A failure rolls back all money changes. A business decline records its reason without a transfer.

Use a globally unique payment UUID and bind it permanently to its device and canonical request fields. The same ID and fields return the existing result. The same ID with changed amount or enrollment returns a conflict. Concurrent requests with the same ID must converge through a database uniqueness constraint, not a process-local cache.

Backend states: a request is absent, or its durable result is SUCCESS, DECLINED, or EXPIRED. For this local simulated transfer there is no need for a durable asynchronous PROCESSING worker: an in-flight database transaction is not a committed intermediate result. Reversals are separate transfers linked to the original, with a uniqueness rule preventing repeated reversal.

Terminal states: READY → AMOUNT → FINGERPRINT → SUBMITTING → SUCCESS / DECLINED; communication uncertainty leads to CHECKING. CHECKING is the terminal's uncertainty, not a backend money state.

Recovery rules:

- Retry only with the same UUID and unchanged request. Persist the pending record before the first send. Reboot must restore it and query before accepting another checkout.
- An authoritative status response of “not found” may race with an in-flight request. It is not permission to create a new UUID. Retry the same request within its validity window.
- Requests have a short checkout validity window, proposed at 60 seconds. Use authenticated backend time with bounded clock tolerance; refuse new checkout if time cannot be established. Late new requests are recorded as EXPIRED with no transfer; existing results remain queryable.
- After expiry, a recovered absent request can be resubmitted with the original ID only to obtain a definitive expired result. Backend validation must prevent execution after its deadline.
- Poll with backoff and a visible waiting state. After a bounded automatic recovery interval, require staff reconciliation while keeping the pending reference. No offline queue of new charges.
- Check disabled-device and account permissions inside the authorization path. Revoked credentials never regain charge permission through replay. Staff can reconcile historical results separately.
- Compare wallet balances with ledger totals and validate transfer pairs before and after the pilot. Correct with recorded reversal/adjustment entries; never edit history to make totals match.

## 6. Minimum data and API contract

| Record | Essential fields and rules |
| --- | --- |
| User and merchant | Role, account state, merchant ownership; use framework password hashing. |
| Device | UUID, owner, credential verifier, active/revoked state, sensor generation, last contact. |
| Consent and enrollment | Consent version/time, customer, device, generation, slot, enrollment identifier, pending/active/revoked/deletion-pending state. |
| Wallet | Owner or simulation funding identity, integer balance; customer/merchant balances cannot be negative. |
| Payment | UUID, immutable request fields/deadline, device, payer/payee, final result/reason, timestamps. |
| Ledger entry | Transfer reference, wallet, signed integer delta; transfers balance to zero. |
| Audit event | Actor, action, object reference, time, sanitized outcome. |

Use unique constraints for payment IDs, active sensor slot mappings, initial grants, and reversal references. Expose no direct balance-edit operation in either public API or staff admin.

Proposed API groups, to be frozen before clients are implemented:

- Account: sign-in, sign-out/revocation, profile, own wallet, paginated own history. Pilot accounts are staff-created; public registration and password reset email infrastructure wait.
- Merchant: own devices, one-time claim, own transaction history. A merchant cannot read another merchant's records or customer account details.
- Device: authenticated configuration/time, heartbeat, pending enrollment/deletion commands and acknowledgements, payment submission and status lookup restricted to that device.
- Staff: consent/enrollment requests, audited initial funding, freeze/revoke, reconciliation, and single reversals. Use the existing admin UI with restricted actions and read-only money fields.

Document request/response examples, validation errors, retry semantics, expiry, and permissions. Use stable machine-readable error codes plus clear user messages. Device credentials are not Android user tokens. Reuse the framework's token authentication for the pilot with enforced expiry, logout revocation, and role/object checks; store Android tokens in platform-protected storage. Rate-limit login, claim, enrollment, and payment requests.

## 7. Build sequence and completion gates

Original full-concept estimate: 6–8 weeks with three contributors working regularly, parts available, and basic familiarity with the stack. With the now-confirmed one-week deadline, this is a sequencing reference only; do not treat the full concept as the current delivery commitment. Advance by completion gates, beginning with the requested backend slice.

| Phase | Estimated slot | Deliverable | Exit gate |
| --- | --- | --- | --- |
| 0 — Confirm constraints | 1–2 days | Scope, exact hardware shortlist, team assignments, consent/retention draft, API sketch | Budget, Android requirement, network access, and target date recorded. |
| 1 — Prove hardware and ledger | Week 1 | Peripheral bring-up; database-backed payment endpoint and software terminal simulator | Local enroll/match/delete works; simulated 500 → 460 and merchant +40 is atomic and repeat-safe. |
| 2 — Connect one terminal | Week 2 | Wi-Fi/TLS, device identity, amount UI, persistent pending payment, status recovery | Terminal completes one payment; lost-response and reboot tests produce one transfer. Use a dedicated test network during development. |
| 3 — Complete account lifecycle | Week 3 | Permissions, consent, enrollment mapping, deletion, freeze, staff operations | A wrong user/device cannot charge or read another account; revoked mappings cannot pay. |
| 4 — Android and provisioning | Weeks 4–5 | One role-based app, protected tokens, secure BLE setup, history | Merchant provisions a clean terminal; customer enrolls and checks history; checkout remains phone-free. |
| 5 — Harden and pilot | Week 6 | Failure tests, storage protection, enclosure, supervised rehearsal, backup/restore | Required tests pass; five-person rehearsal succeeds before expanding to 20–50 volunteers. |
| 6 — Evaluate and deliver | Weeks 7–8 buffer | Pilot results, fixes, report, presentation assets, demonstration package | Ledger reconciles; defects and limitations recorded; another teammate can reproduce setup. |

Hardware testing and backend work can proceed concurrently as team assignments, but the simulator is only a development tool. It cannot satisfy the physical biometric demonstration gate. Do not start with a polished app while the sensor and ledger remain unproven.

Suggested ownership: embedded contributor owns circuit/firmware; backend contributor owns API/ledger/deployment; Android contributor owns app/provisioning. All three participate in failure testing and the pilot. If the team is smaller, serialize these jobs without inventing additional services.

## 8. Verification and pilot acceptance

Automated checks must run against PostgreSQL for transaction behavior. Use a small set of meaningful tests rather than a coverage target:

1. Successful transfer changes both wallets correctly and creates a balanced ledger pair.
2. Insufficient funds, zero/negative/over-limit/non-integer amounts, and invalid enrollments cause no transfer.
3. Sequential and concurrent duplicate requests create exactly one transfer; changed payload under the same ID conflicts.
4. Two concurrent payments whose total exceeds available funds cannot overdraw the account.
5. A forced exception between debit and credit rolls back the entire transfer.
6. Lost response after commit, request not received, expiry, and reboot recover the same result without another debit.
7. Customer/merchant/device permission violations, expired tokens, revoked devices, and stale sensor generations are rejected.
8. Initial funding and reversal retries cannot mint extra BioCoins; enrollment/deletion interruption cannot activate the wrong mapping.

Hardware and system checks:

- Power-cycle with a pending transaction; disconnect Wi-Fi before send and after server commit; restart the backend; provide invalid TLS configuration. The terminal must never show false success.
- Incorrect Wi-Fi password, interrupted provisioning, unauthorized BLE access, duplicate device claim, reprovisioning, and network recovery.
- Sensor disconnected, unreadable finger, non-enrolled finger, duplicate enrollment, full sensor, sensor reset, account withdrawal, and deletion while offline.
- Verify amount visibility, cancel behavior, keypad debounce, readable status messages, and text feedback independent of LED color or buzzer sound. Staff offer an assisted demonstration path for people unable or unwilling to use fingerprints.
- Inspect logs and network boundaries for secrets and biometric material; test database backup restoration and a clean deployment from the documented instructions.

Proposed acceptance targets, to confirm after the hardware spike:

| Measure | Target |
| --- | --- |
| Core demonstration | 40 simulated BioCoins debited from a 500 balance; merchant credited 40; no phone used during checkout. |
| Duplicate safety | Zero extra transfers across the retry/reboot/concurrency test suite. |
| Ledger integrity | Every transfer balances; wallet/ledger reconciliation has zero discrepancies. |
| Authorization | All specified unauthorized-access tests pass. |
| Completion latency | Report median and 95th percentile; provisional goal p95 ≤5 seconds from successful match to confirmed result on the test network. |
| Biometric usability | Record first-attempt matches, retries, failures, and total checkout time separately, with counts and test conditions. |
| Non-enrolled trials | No observed incorrect acceptance in the documented test set; any observed wrong match pauses the pilot. This is not a certified false-acceptance rate. |

Start with five volunteers, correct defects, then expand to the proposed 20–50. Separate software transactions from biometric attempts in the results. Do not infer production fraud resistance from a small convenience sample. Remove test credentials and complete the agreed template cleanup after evaluation.

## 9. Ponytail review and design audit

What this project does: it demonstrates a phone-free simulated purchase using a merchant terminal and a backend ledger. The assumed load is one active checkout, one merchant, and 20–50 enrolled volunteers. There is no implementation to audit yet; the following findings concern the supplied concept and are addressed by requirements above.

### Must fix before pilot

1. **A sensor slot can identify the wrong customer after reuse.** The concept does not define enrollment ownership or mapping lifecycle. If slot 7 is deleted and reused, an old mapping can charge the former owner. Bind device/generation/enrollment ID, activate only after acknowledgement, and revoke before deletion. Skipping this can charge the wrong simulated wallet.
2. **A timeout can lead to a duplicate debit.** The concept names an UNKNOWN state without specifying durable terminal recovery. A paid request followed by a lost response can be retried as a fresh payment. Persist and reuse one UUID, distinguish terminal uncertainty from backend status, and test power loss. Skipping this makes the central demonstration unreliable.
3. **Separate balance writes can lose or create BioCoins.** The concept calls for a ledger but does not specify atomic updates or concurrent spending. Two requests can both observe sufficient funds. Lock wallets and commit the transfer, entries, balances, and final result together. Skipping this permits overdrafts or unmatched credits.
4. **Device identity does not prove biometric authorization.** A forged sensor result or modified terminal can claim a match. Scope this explicitly to supervised fake-money use, keep hardware under staff control, enforce backend permissions, and do not describe the sensor as certified or spoof-resistant. Skipping this produces an unsupported security claim.
5. **Enrollment, consent, and deletion are not optional account features.** Backend-only deletion leaves fingerprint templates on the sensor. Add consent, immediate backend revocation, acknowledged local deletion, and sensor-loss handling. Skipping this leaves sensitive data after a volunteer withdraws.

### Should fix before implementation expands

6. **The plan can grow into several apps before the payment works.** Separate customer/merchant apps and a custom admin dashboard duplicate account and device work. Use one Android app and built-in administration; prove the hardware and ledger first. Skipping this delays the project without improving the demo.
7. **Merchant fingerprint login creates a setup dependency.** The concept asks for a merchant fingerprint at boot without defining initial enrollment or recovery. Start with authenticated merchant claiming and physical setup access. Skipping this decision leaves first-use and reset behavior ambiguous.
8. **Nominal component choices do not define a working circuit.** A sensor or display variant can require different voltage levels or reserve essential pins. Freeze exact datasheets and a reviewed pin/power table before wiring. Skipping this risks hardware damage or a bring-up delay.

Verdict: proceed with the scoped prototype once Phase 0 records the missing constraints. The supplied concept is a useful starting point; the enrollment, recovery, and ledger requirements above are required work. This is not a code-quality or security certification.

## 10. What waits

No real-money integration, KYC/Aadhaar capture, UPI connection, PPI integration, cash redemption, cryptocurrency, ML fraud detection, multimodal biometrics, automatic cross-terminal template synchronization, offline payment approval, printer, cellular modem, custom PCB, microservices, Redis, message broker, or custom admin dashboard in the first release.

Future real-money work is a separate project decision. Its first deliverable would be a provider-confirmed authorization and biometric integration flow plus the required institutional/compliance review, before any live payment implementation. A simulated ledger and hobby sensor do not establish that such a flow is permitted or supported.

## 11. Repository and handoff

Create only when implementation begins:

```text
firmware/       ESP-IDF project and hardware self-checks
backend/        Django API, migrations, PostgreSQL integration tests, simulator command
android/        Kotlin app and provisioning integration
docs/           Wiring, API contract, threat model, pilot protocol, measured results
README.md       Setup, simulation notice, build/test commands, demonstration steps
```

Keep one repository, small reviewed changes, example configuration without secrets, pinned dependencies, and CI for backend tests plus firmware/app builds where toolchains permit. The first change should deliver a tested ledger slice and sensor bring-up instructions, not scaffold every proposed folder.

At the end, deliver wiring and BOM, firmware build and flashing steps, backend migrations and deployment steps, Android test APK, API examples, test results, pilot metrics, known limits, backup/recovery instructions, and final research/report material. Record hardware, firmware, and schema versions used for the demonstration.

Use Ponytail review on each meaningful change by tracing connected callers, permissions, tests, and data writes. Run a whole-repository Ponytail audit once the first integrated flow exists and again before the pilot. Money integrity, account boundaries, enrollment, device secrets, and recovery take priority over style or line-count changes.

## 12. Decisions needed to finalize estimates

- Exact submission date, weekly availability of the five teammates, and strongest languages.
- Exact college-supplied parts, handover date, and any budget for missing consumables.
- Whether an Android APK is required by the assessment; this plan retains it because the supplied concept includes Android.
- Approved Wi-Fi network and whether it avoids captive portals or enterprise authentication for the initial test.
- Institution approval/contact for volunteers, consent wording, retention duration, and demo location.
- Exact sensor/board/display and their manufacturer documents.

None of these prevents planning. Exact wiring, purchases, schedule commitments, and volunteer testing depend on the answers.

## 13. Source notes

Primary project reference: `/Users/rajkumaragarwal/Downloads/BioPay_IoT_Project_Concept_Verified_Research.docx`, including its proposed hardware, Android app, one-merchant/one-terminal pilot, simulated ledger, and 20–50 volunteers. Its research bibliography and provider/regulatory assertions have not been independently reverified in this planning pass.

Official technical documentation consulted on 27 October 2026:

- [Espressif Android provisioning library](https://github.com/espressif/esp-idf-provisioning-android): reuse its supported provisioning protocol instead of inventing a BLE credential protocol.
- [ESP-IDF protocol communication](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/provisioning/protocomm.html): authenticated provisioning security modes; pin the SDK and verify matching client support during the spike.
- [ESP32-S3 NVS encryption](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/storage/nvs_encryption.html): protects local persistent credentials; key protection and flash-encryption requirements depend on the selected scheme.
- [Django database transactions](https://docs.djangoproject.com/en/5.2/topics/db/transactions/): explicit atomic transactions provide the backend commit boundary. This documentation link does not freeze the eventual framework version.
- [PostgreSQL row locking](https://www.postgresql.org/docs/17/explicit-locking.html): wallet row locks coordinate concurrent writers until the transaction ends. Pin a supported database version at implementation.

Unverified: exact hardware compatibility, local prices/stock, real-world latency, sensor accuracy/liveness, provider partnerships, and applicability of the attached legal/regulatory research. Physical testing and a later code audit remain outstanding.
