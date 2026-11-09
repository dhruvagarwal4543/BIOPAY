# Presentation outline (about 12 slides)
1. Title: BioPay, phone-free biometric checkout (simulated BioCoins, no real money).
2. Problem: phones fail; biometric payment raises safety and consent questions.
3. Idea and objectives (5 bullets).
4. User journey: register -> consent -> enroll -> pay -> receipt.
5. Architecture diagram (sensor, ESP32, API, database, three web roles).
6. The payment engine: atomic transfer, ledger, idempotency UUID (one diagram of retry after a lost reply).
7. Privacy by design: template never leaves the sensor; slot number only.
8. Security: roles, CSRF, key hashing, revocation under locks, audit log, simulator consent.
9. Live demo (use docs/DEMO_SCRIPT.md).
10. Testing: 104 backend, 18 browser, real-stack run, accessibility checks (numbers from TEST_REPORT.md).
11. Hardware plan and honest status: firmware core tested; wiring and sensor testing pending (firmware/INTEGRATION_PLAN.md).
12. Limitations, future scope, Q&A (see viva list in the report).
