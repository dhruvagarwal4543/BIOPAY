// Copy to src/config.h (git-ignored). Never commit real values.
#pragma once
#define WIFI_SSID "your-wifi"
#define WIFI_PASSWORD "your-wifi-password"
#define BIOPAY_HOST "https://your-server"           // no trailing slash; HTTPS outside a private LAN
#define BIOPAY_TERMINAL_KEY "from create_terminal"   // shown once by `manage.py create_terminal`
#define BIOPAY_MAX_AMOUNT 100                        // must match the server's BIOPAY_MAX_PAYMENT
#define BIOPAY_USE_TLS 1                             // 1 = HTTPS (needs BIOPAY_CA_CERT), 0 = plain HTTP on a private LAN only
// #define BIOPAY_CA_CERT "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----\n"
#define BIOPAY_ENROLL_PIN "000000"                   // keypad PIN that unlocks on-device finger enrollment
// R307S UART: copy these from the test that worked. No default is provided on purpose.
#define FP_RX_PIN -1  // ESP32 pin wired to R307S TX
#define FP_TX_PIN -1  // ESP32 pin wired to R307S RX
#define FP_BAUD 57600
