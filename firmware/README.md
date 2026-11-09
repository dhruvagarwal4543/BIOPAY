# BioPay terminal firmware (ESP32-S3)

**Status: BLOCKED on hardware.** Sensor model, pinout and display are unknown, so no wiring is documented and nothing here has run on a board.

Verified (on a laptop): `make -C firmware test` runs `lib/payflow`, the payment state machine, against fakes.
It checks that a payment UUID is created once, saved before sending, reused on every retry and across a reboot, and cleared only by a definite server answer (success, 422, 403, 409, revoked). Only the sensor slot and amount are ever sent, never a fingerprint template.

Still to write once hardware is chosen (each implements an interface in `payflow.h`):
- `Http` over WiFiClientSecure with header `X-BioPay-Terminal-Key` to `POST /api/terminal/payments/`
- `Store` over NVS (Preferences)
- `Sensor` for the chosen module (match on the sensor, return its slot)
- `Rng` (`esp_random`) for UUIDv4, then `main.cpp` (Wi-Fi, keypad/amount entry, result display)

Real-device checklist (all UNCHECKED): flash; enroll with consent; match; pay; kill Wi-Fi mid-payment and confirm one debit after retry; revoke terminal and confirm refusal.
Enrollment slots are per-terminal sensor slots, never global identity; the server never accepts a payer id from the terminal.
