# Hardware handoff

**Status: BLOCKED — HARDWARE MODEL AND PINOUT REQUIRED.** Nothing physical has been built, wired, flashed or tested. No pins, voltages or sensor models are asserted anywhere in this repository.

## 1. What to decide and send before any wiring
| Item | Why it matters | Where to find it |
| --- | --- | --- |
| ESP32-S3 board exact name (and a pinout photo/diagram) | Pin numbers and which pins are safe differ per board | Board silkscreen, seller page |
| Fingerprint sensor exact model and interface (UART, SPI, ...) | Decides the driver, enrollment commands and how many slots exist | Datasheet |
| Sensor operating voltage and logic level | A wrong supply or 5 V logic into a 3.3 V pin can damage the board or the sensor | Datasheet; confirm with a multimeter |
| Display model | Needs a driver and a pin set | Datasheet |
| Keypad / buttons for the amount | Amount entry method | Parts list |
| Power source (USB, battery) and its current limit | Sensor current draw | Datasheets |
| Wi-Fi network for the demo and the server's address | Terminal must reach the Django server | Your router |

## 2. Software already ready (verified on a laptop)
- `firmware/lib/payflow`: payment state machine behind interfaces for HTTP, storage, sensor and random numbers. `make -C firmware test` checks: one payment ID per payment, saved before sending, reused on every retry and after a reboot, cleared only by a definite server answer; only the slot number and amount are sent.
- Server payment API, terminal key authentication, revocation, idempotency, reconciliation (104 backend tests).

## 3. Still to build once the parts are known
1. `Sensor` implementation: enroll (template stays in the module, return the slot) and match (return the slot).
2. `Http` over TLS with header `X-BioPay-Terminal-Key`; certificate or CA pinning.
3. `Store` on ESP32 non-volatile storage for the pending payment record.
4. `Rng` from the ESP32 hardware random generator for UUIDv4.
5. User interface: amount entry, "place finger", success / declined / network / revoked screens.
6. Server: a real-sensor mode for `/api/terminal/*` (it is gated to `DEBUG` plus the demo flag today) and HTTPS in front of Django.
7. Terminal registration: `python manage.py create_terminal <merchant-code> "<name>"` prints the device key once; store it on the device, never in git (`firmware/src/config.h` is git-ignored).

## 4. Physical test checklist (all UNCHECKED)
- [ ] Voltage and logic levels confirmed against datasheets before power-up.
- [ ] Enroll a consenting volunteer; the server shows only terminal + slot.
- [ ] Match succeeds for the enrolled finger and fails for another finger.
- [ ] A 60 BioCoin payment succeeds and both dashboards show it.
- [ ] Cut Wi-Fi mid-payment, restore it: exactly one debit.
- [ ] Reboot the device mid-payment: it resumes with the same payment ID.
- [ ] Admin revokes the terminal: the next payment is refused.
- [ ] Withdraw consent / revoke enrollment: the next payment is refused.
- [ ] Insufficient balance shows "declined" on the display.

See `diagrams/hardware-plan.svg` for the planned block diagram (every box there is unverified).
