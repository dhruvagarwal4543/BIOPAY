# Blockers
1. **BLOCKED — HARDWARE MODEL AND PINOUT REQUIRED.** Hardware (ESP32-S3 + fingerprint sensor): model/pins unknown. Wiring, flashing, real enrollment/match, real payment: all BLOCKED/UNCHECKED. What is needed: docs/HARDWARE_HANDOFF.md.
2. The terminal API (`/api/terminal/*`) only works when `DJANGO_DEBUG=true` and `BIOPAY_ENABLE_DEMO_API=true` (it is gated as a mock). A real device needs a non-debug "real sensor" mode and HTTPS first. Do this when hardware arrives.
3. `.env` cannot be read in this session (guard hook); tests used throwaway env values and a scratch DB `biopay_e2e`.
4. Not run: screen-reader session, GPU frame-rate on real hardware, load testing beyond the PostgreSQL race tests.
