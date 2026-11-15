# Blockers
1. **BLOCKED — HARDWARE MODEL AND PINOUT REQUIRED.** Hardware (ESP32-S3 + fingerprint sensor): model/pins unknown. Wiring, flashing, real enrollment/match, real payment: all BLOCKED/UNCHECKED. What is needed: docs/HARDWARE_HANDOFF.md.
2. DONE (software): `BIOPAY_TERMINAL_REAL_SENSOR=true` enables the terminal API without DEBUG for R307S enrollments only. Still needed: HTTPS in front of Django and the server CA in `config.h`.
2b. BLOCKED: R307S UART pins are not in the repo (the bench sketch was not provided); firmware refuses to build until `FP_RX_PIN/FP_TX_PIN` are set. Sensor is not wired, so nothing is flashed or hardware-verified. Keypad row/column order is an assumption.
3. `.env` cannot be read in this session (guard hook); tests used throwaway env values and a scratch DB `biopay_e2e`.
4. Not run: screen-reader session, GPU frame-rate on real hardware, load testing beyond the PostgreSQL race tests.
