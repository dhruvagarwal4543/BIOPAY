// Hardware-independent payment flow. Everything the ESP32 touches sits behind the small
// interfaces below, so this file compiles and is tested natively (see firmware/test).
#pragma once
#include <cstdint>
#include <string>

namespace biopay {

struct Http {  // POST JSON to /api/terminal/payments/. status 0 = no response (network error/timeout).
  virtual ~Http() = default;
  virtual int post(const std::string& json, std::string& body) = 0;
};
struct Store {  // Non-volatile (ESP32 NVS). Survives reboot so a retry reuses the same UUID.
  virtual ~Store() = default;
  virtual bool load(std::string& key, std::string& value) = 0;
  virtual void save(const std::string& key, const std::string& value) = 0;
  virtual void erase(const std::string& key) = 0;
};
struct Sensor {  // Matching happens ON the sensor. Only its slot number leaves this class, never a template.
  virtual ~Sensor() = default;
  virtual bool match(uint32_t& slot) = 0;  // false = no finger / no match
};
struct Rng {
  virtual ~Rng() = default;
  virtual std::string uuid4() = 0;
};

enum class Result { Success, InsufficientFunds, NoEnrollment, TerminalRevoked, Conflict, NetworkRetry, NoMatch, BadAmount, ServerError };

class PayFlow {
 public:
  PayFlow(Http& h, Store& s, Sensor& f, Rng& r, int64_t maxAmount) : http_(h), store_(s), sensor_(f), rng_(r), max_(maxAmount) {}
  // New payment: needs a fingerprint match, then persists {uuid, slot, amount} BEFORE sending.
  Result start(int64_t amount);
  // After NetworkRetry (or a reboot): resend the stored payment unchanged. Never creates a new UUID.
  Result retry();
  bool hasPending();

 private:
  Result send(const std::string& uuid, uint32_t slot, int64_t amount);
  Http& http_; Store& store_; Sensor& sensor_; Rng& rng_; int64_t max_;
};

}  // namespace biopay
