// Copy to src/config.h (git-ignored). Never commit the real key.
#pragma once
#define WIFI_SSID "your-wifi"
#define WIFI_PASSWORD "your-wifi-password"
#define BIOPAY_HOST "https://your-server"          // HTTPS only outside a private LAN
#define BIOPAY_TERMINAL_KEY "from create_terminal"  // shown once by `manage.py create_terminal`
#define BIOPAY_MAX_AMOUNT 100                       // must match the server's BIOPAY_MAX_PAYMENT
