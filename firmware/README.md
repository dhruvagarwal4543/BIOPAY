# BioPay terminal firmware (ESP32 NodeMCU-32S)

Hardware: R307S fingerprint (UART), 4x4 keypad (GPIO 32,33,25,26 / 27,14,18,19), LED on GPIO4 (common cathode). No OLED, no buzzer.

## Status (be honest)
| Check | Level |
|---|---|
| `make test`: payment state machine + amount entry | software, native, fakes |
| `pio run -e nodemcu-32s` compiles | software build only |
| Backend real-sensor mode (`python manage.py test payments`) | software, real PostgreSQL |
| R307S match, keypad, LED, Wi-Fi, full payment on the board | **NOT YET RUN on hardware** |

## Configure and build
1. `cp include_config.example.h src/config.h` (git-ignored). Fill Wi-Fi, host, terminal key, enrol PIN, and **FP_RX_PIN / FP_TX_PIN from the working sensor test**. The build refuses to compile while they are `-1`.
2. TLS: set `BIOPAY_CA_CERT` for HTTPS. Plain HTTP only with `BIOPAY_USE_TLS 0` on a private LAN.
3. `pio run -e nodemcu-32s`, then `pio run -e nodemcu-32s -t upload` and `pio device monitor`.

## Backend
Run Django with `BIOPAY_TERMINAL_REAL_SENSOR=true` (works with `DJANGO_DEBUG=false`). Create the terminal with `manage.py create_terminal` and put its key in `config.h`. In this mode only enrollments with `source=R307S` can pay; mock enrollments and the merchant simulator never apply.

## Use
- Pay: any key, type amount, `#`, `#` again to confirm (`*` corrects), then place the finger.
- Enrol (needs the customer's consent first): customer clicks "Reserve slot" in the web app, which shows a slot number; at the device press `A`, enter the enrol PIN, enter that slot, scan twice.
- LED: blip every 2s idle | fast blink waiting/working | solid 2s paid | 3 slow blinks failure | 1Hz blink unconfirmed (same payment is resent, never doubled).
- Unconfirmed payments are stored in NVS and resent with the same UUID, also after a reboot.

## Hardware verification checklist (all UNCHECKED)
Sensor found at boot; enrol with consent; match pays and web history shows an `R307S` payment; wrong finger sends nothing; insufficient funds shows failure LED; Wi-Fi off mid-payment gives exactly one debit after reconnect; revoked terminal is refused; keypad key order matches the labels.
