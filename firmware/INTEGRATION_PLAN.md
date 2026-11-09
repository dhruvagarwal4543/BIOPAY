# Hardware integration plan (nothing here is verified on a device)

Parts not chosen yet: sensor model, display, keypad, pinout. Do not wire from this document.

| Step | Work | Status |
|---|---|---|
| 1 | Choose a sensor module with on-device matching and an Arduino/ESP-IDF driver; record datasheet voltage/UART pins in `firmware/WIRING.md` after the parts are in hand | BLOCKED (hardware) |
| 2 | `Sensor` implementation: enroll (store template in the module, return slot) and match (return slot) | BLOCKED |
| 3 | Wi-Fi + `Http` over TLS with header `X-BioPay-Terminal-Key`; pin the server certificate or CA | BLOCKED (needs board); server needs HTTPS |
| 4 | `Store` over NVS; keep the pending record `{uuid, slot, amount}` (already designed in `payflow`) | core DONE, glue BLOCKED |
| 5 | `Rng` from `esp_random` for UUIDv4 | BLOCKED |
| 6 | UI: amount entry, "place finger", success/decline/network/revoked messages | BLOCKED |
| 7 | Retry/timeout: resend the stored payment unchanged until a definite answer; show "unconfirmed" meanwhile | logic DONE (native tests) |
| 8 | Restart recovery: on boot, if a pending record exists, resend it first | logic DONE (`hasPending` + `retry`) |
| 9 | Server: add a real-sensor mode to the terminal API (it is gated behind DEBUG today) and serve over HTTPS | TODO, software |
| 10 | Real-device test checklist: enroll with consent, match, pay, cut Wi-Fi mid-payment (exactly one debit), revoke terminal (refused), reboot mid-payment | UNCHECKED |
Native core check: `make -C firmware test`.
