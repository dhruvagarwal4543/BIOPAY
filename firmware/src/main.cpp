// BioPay terminal. Flow: keypad amount -> finger match ON the R307S -> POST slot+amount -> LED/Serial result.
// No fingerprint image or template ever leaves the sensor; the server maps slot -> customer.
#include <Adafruit_Fingerprint.h>
#include <HTTPClient.h>
#include <Keypad.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include "../lib/amountentry/amountentry.h"
#include "../lib/payflow/payflow.h"
#include "config.h"

#if !defined(WIFI_SSID) || !defined(BIOPAY_HOST) || !defined(BIOPAY_TERMINAL_KEY) || !defined(BIOPAY_ENROLL_PIN)
#error "src/config.h is incomplete: see include_config.example.h"
#endif
#if FP_RX_PIN < 0 || FP_TX_PIN < 0
#error "Set FP_RX_PIN / FP_TX_PIN in src/config.h to the pins used by the working R307S test"
#endif
#if BIOPAY_USE_TLS && !defined(BIOPAY_CA_CERT)
#error "BIOPAY_USE_TLS=1 needs BIOPAY_CA_CERT (server CA). Certificates are never skipped."
#endif

using namespace biopay;

// Keypad wiring from the user's bench test. UNVERIFIED ASSUMPTION: first four are rows, last four are columns.
static const byte ROW_PINS[4] = {32, 33, 25, 26};
static const byte COL_PINS[4] = {27, 14, 18, 19};
static char KEYS[4][4] = {{'1', '2', '3', 'A'}, {'4', '5', '6', 'B'}, {'7', '8', '9', 'C'}, {'*', '0', '#', 'D'}};
static Keypad keypad(makeKeymap(KEYS), const_cast<byte*>(ROW_PINS), const_cast<byte*>(COL_PINS), 4, 4);
static const int LED_PIN = 4;  // common cathode, one verified channel

HardwareSerial fpSerial(2);
Adafruit_Fingerprint finger(&fpSerial);
Preferences prefs;

// ---- LED (one channel, so patterns carry the meaning) ----
// IDLE: short blip every 2s | WAIT: fast blink (finger/work) | OK: solid | FAIL: 3 slow blinks | UNSURE: 1Hz blink until settled
enum class Led { Idle, Wait, Ok, Fail, Unsure };
static Led led = Led::Idle;
static uint32_t ledSince = 0;
static void setLed(Led l) { led = l; ledSince = millis(); }
static void ledTick() {
  uint32_t t = millis() - ledSince; bool on = false;
  switch (led) {
    case Led::Idle: on = (t % 2000) < 80; break;
    case Led::Wait: on = (t % 200) < 100; break;
    case Led::Ok: on = t < 2000; break;
    case Led::Fail: on = t < 1800 && (t % 600) < 300; break;
    case Led::Unsure: on = (t % 1000) < 500; break;
  }
  digitalWrite(LED_PIN, on);
}
// Block (while animating) for ms; keeps the LED honest during waits.
static void hold(uint32_t ms) { uint32_t s = millis(); while (millis() - s < ms) { ledTick(); delay(5); } }

// ---- Interfaces behind PayFlow ----
struct EspHttp : Http {
  int post(const std::string& json, std::string& body) override {
    if (WiFi.status() != WL_CONNECTED) return 0;
    HTTPClient http; http.setTimeout(10000);
    #if BIOPAY_USE_TLS
    WiFiClientSecure client; client.setCACert(BIOPAY_CA_CERT);
    #else
    WiFiClient client;
    #endif
    if (!http.begin(client, String(BIOPAY_HOST) + "/api/terminal/payments/")) return 0;
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-BioPay-Terminal-Key", BIOPAY_TERMINAL_KEY);
    int status = http.POST(String(json.c_str()));
    if (status > 0) body = http.getString().c_str();
    http.end();
    return status > 0 ? status : 0;
  }
};
struct NvsStore : Store {  // survives reboot so a retry reuses the same UUID
  bool load(std::string& k, std::string& v) override {
    if (!prefs.isKey(k.c_str())) return false;
    v = prefs.getString(k.c_str(), "").c_str(); return true;
  }
  void save(const std::string& k, const std::string& v) override { prefs.putString(k.c_str(), v.c_str()); }
  void erase(const std::string& k) override { prefs.remove(k.c_str()); }
};
struct EspRng : Rng {
  std::string uuid4() override {
    uint8_t b[16]; for (int i = 0; i < 16; i += 4) { uint32_t r = esp_random(); memcpy(b + i, &r, 4); }
    b[6] = (b[6] & 0x0F) | 0x40; b[8] = (b[8] & 0x3F) | 0x80;
    char s[37]; snprintf(s, sizeof s, "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
      b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7], b[8], b[9], b[10], b[11], b[12], b[13], b[14], b[15]);
    return s;
  }
};
struct R307Sensor : Sensor {  // 1:N search on the module; only the matched slot number is returned
  bool match(uint32_t& slot) override {
    Serial.println("Place finger on the sensor...");
    setLed(Led::Wait);
    uint32_t start = millis(); uint8_t p = FINGERPRINT_NOFINGER;
    while (millis() - start < 15000) {
      ledTick(); p = finger.getImage();
      if (p == FINGERPRINT_OK) break;
      delay(30);
    }
    if (p != FINGERPRINT_OK) { Serial.println("No finger detected (timeout)."); return false; }
    if (finger.image2Tz() != FINGERPRINT_OK) { Serial.println("Could not read the finger; try again."); return false; }
    if (finger.fingerSearch() != FINGERPRINT_OK) { Serial.println("Fingerprint not recognised."); return false; }
    slot = finger.fingerID;
    Serial.printf("Matched sensor slot %u (confidence %u)\n", (unsigned)slot, (unsigned)finger.confidence);
    return true;
  }
};

static EspHttp http; static NvsStore store; static EspRng rng; static R307Sensor sensor;
static PayFlow flow(http, store, sensor, rng, BIOPAY_MAX_AMOUNT);

static bool wifiUp(uint32_t waitMs) {
  if (WiFi.status() == WL_CONNECTED) return true;
  WiFi.disconnect(); WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t s = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - s < waitMs) { ledTick(); delay(50); }
  return WiFi.status() == WL_CONNECTED;
}

static void show(Result r) {
  switch (r) {
    case Result::Success: Serial.println("PAYMENT OK"); setLed(Led::Ok); break;
    case Result::InsufficientFunds: Serial.println("DECLINED: insufficient BioCoins"); setLed(Led::Fail); break;
    case Result::NoEnrollment: Serial.println("REFUSED: finger not enrolled for this terminal (or terminal not permitted)"); setLed(Led::Fail); break;
    case Result::TerminalRevoked: Serial.println("REFUSED: this terminal has been revoked"); setLed(Led::Fail); break;
    case Result::Conflict: Serial.println("REFUSED: payment id conflict (server rejected a repeat with different details)"); setLed(Led::Fail); break;
    case Result::NoMatch: Serial.println("NO MATCH: payment not sent"); setLed(Led::Fail); break;
    case Result::BadAmount: Serial.println("Invalid amount"); setLed(Led::Fail); break;
    case Result::NetworkRetry: Serial.println("UNCONFIRMED: no answer from server. Retrying the SAME payment; do not pay again."); setLed(Led::Unsure); break;
    case Result::ServerError: Serial.println("ERROR: server rejected the request (check terminal key/config)"); setLed(Led::Fail); break;
  }
}

// Resend the stored payment (same UUID) until the server gives a definite answer.
static Result settlePending(Result r) {
  for (int tries = 0; r == Result::NetworkRetry && tries < 6; tries++) {
    show(r); hold(2000UL << (tries < 4 ? tries : 4));  // 2s,4s,8s,16s,32s,32s
    wifiUp(8000);
    r = flow.retry();
  }
  return r;
}

static char waitKey() { char k; while (!(k = keypad.getKey())) { ledTick(); delay(10); } return k; }

static std::string readDigits(const char* prompt, bool mask) {
  Serial.printf("%s ('#' ok, '*' delete)\n", prompt); std::string s;
  for (;;) {
    char k = waitKey();
    if (k == '#') return s;
    if (k == '*') { if (s.empty()) return ""; s.pop_back(); }
    else if (k >= '0' && k <= '9' && s.size() < 12) s += k;
    Serial.printf("> %s\n", mask ? std::string(s.size(), '*').c_str() : s.c_str());
  }
}

// Enroll a finger into R307S slot N (the slot the customer reserved in the web app after consenting).
static void enrollFinger() {
  if (readDigits("Enrol PIN", true) != BIOPAY_ENROLL_PIN) { Serial.println("Wrong PIN"); setLed(Led::Fail); return; }
  std::string t = readDigits("Slot number shown in the customer's web page", false);
  long slot = atol(t.c_str());
  if (slot < 1 || slot > finger.capacity) { Serial.println("Invalid slot"); setLed(Led::Fail); return; }
  setLed(Led::Wait);
  for (int pass = 1; pass <= 2; pass++) {
    Serial.printf("Place finger (scan %d of 2)\n", pass);
    uint32_t s = millis(); uint8_t p;
    while ((p = finger.getImage()) != FINGERPRINT_OK && millis() - s < 15000) { ledTick(); delay(30); }
    if (p != FINGERPRINT_OK || finger.image2Tz(pass) != FINGERPRINT_OK) { Serial.println("Enrol failed"); setLed(Led::Fail); return; }
    Serial.println("Remove finger"); while (finger.getImage() != FINGERPRINT_NOFINGER) { ledTick(); delay(30); }
  }
  if (finger.createModel() != FINGERPRINT_OK) { Serial.println("Scans did not match; enrol again"); setLed(Led::Fail); return; }
  if (finger.storeModel(slot) != FINGERPRINT_OK) { Serial.println("Store failed"); setLed(Led::Fail); return; }
  Serial.printf("Enrolled finger in slot %ld\n", slot); setLed(Led::Ok);
}

static void payOnce() {
  AmountEntry a(BIOPAY_MAX_AMOUNT);
  Serial.printf("Amount in BioCoins (max %d): digits, '*' delete, '#' confirm\n", BIOPAY_MAX_AMOUNT);
  while (a.state() != AmountEntry::State::Done && a.state() != AmountEntry::State::Cancelled) {
    auto before = a.state(); a.feed(waitKey());
    if (a.state() == AmountEntry::State::Confirming && before != a.state())
      Serial.printf("Pay %lld BioCoins? '#' = yes, '*' = correct\n", (long long)a.value());
    else Serial.printf("Amount: %lld\n", (long long)a.value());
  }
  if (a.state() == AmountEntry::State::Cancelled) { Serial.println("Cancelled"); return; }
  if (!wifiUp(10000)) Serial.println("Wi-Fi down: payment will be queued and retried (same id).");
  Result r = flow.start(a.value());
  r = settlePending(r);
  show(r);
  hold(r == Result::NetworkRetry ? 0 : 2500);
  if (r == Result::NetworkRetry) Serial.println("Still unconfirmed. It will be resent automatically on the next attempt or reboot.");
}

void setup() {
  Serial.begin(115200); pinMode(LED_PIN, OUTPUT); setLed(Led::Wait);
  fpSerial.begin(FP_BAUD, SERIAL_8N1, FP_RX_PIN, FP_TX_PIN);
  finger.begin(FP_BAUD);
  if (!finger.verifyPassword()) {  // never run without a sensor: a payment needs a real match
    Serial.println("R307S NOT FOUND. Check wiring/pins/baud. Halting."); setLed(Led::Fail);
    for (;;) { ledTick(); delay(10); }
  }
  finger.getParameters();
  prefs.begin("biopay", false);
  Serial.printf("R307S ok, capacity %u. Wi-Fi...\n", (unsigned)finger.capacity);
  Serial.println(wifiUp(15000) ? "Wi-Fi connected" : "Wi-Fi not connected yet; will retry on payment");
  if (flow.hasPending()) {  // reboot mid-payment: settle it before anything new
    Serial.println("Found an unconfirmed payment from before the reboot; resending it.");
    show(settlePending(flow.retry()));
  }
  setLed(Led::Idle);
  Serial.println("Ready. Press any key to pay, 'A' to enrol a finger.");
}

void loop() {
  ledTick();
  char k = keypad.getKey();
  if (!k) return;
  if (k == 'A') enrollFinger(); else payOnce();
  hold(300); setLed(Led::Idle);
  Serial.println("Ready.");
}
