#include "payflow.h"

#include <cstdio>
#include <cstdlib>

namespace biopay {
namespace {
const char* kKey = "pending";
// Record format: "<uuid> <slot> <amount>". uuid has no spaces.
std::string encode(const std::string& u, uint32_t slot, int64_t amount) {
  return u + " " + std::to_string(slot) + " " + std::to_string(amount);
}
bool decode(const std::string& s, std::string& u, uint32_t& slot, int64_t& amount) {
  char id[64]; unsigned long sl; long long am;
  if (std::sscanf(s.c_str(), "%63s %lu %lld", id, &sl, &am) != 3) return false;
  u = id; slot = static_cast<uint32_t>(sl); amount = am; return true;
}
bool has(const std::string& body, const char* code) { return body.find(code) != std::string::npos; }
}  // namespace

bool PayFlow::hasPending() { std::string k = kKey, v; return store_.load(k, v); }

Result PayFlow::start(int64_t amount) {
  if (amount < 1 || amount > max_) return Result::BadAmount;
  if (hasPending()) return retry();  // finish the unconfirmed payment first; never stack a second one
  uint32_t slot;
  if (!sensor_.match(slot)) return Result::NoMatch;
  std::string uuid = rng_.uuid4();
  store_.save(kKey, encode(uuid, slot, amount));
  return send(uuid, slot, amount);
}

Result PayFlow::retry() {
  std::string k = kKey, v, u; uint32_t slot; int64_t amount;
  if (!store_.load(k, v) || !decode(v, u, slot, amount)) { store_.erase(kKey); return Result::ServerError; }
  return send(u, slot, amount);
}

Result PayFlow::send(const std::string& uuid, uint32_t slot, int64_t amount) {
  std::string json = "{\"payment_id\":\"" + uuid + "\",\"amount\":" + std::to_string(amount) +
                     ",\"sensor_slot\":" + std::to_string(slot) + "}";
  std::string body;
  int status = http_.post(json, body);
  if (status == 0 || status >= 500) return Result::NetworkRetry;  // outcome unknown: keep the record, same UUID
  store_.erase(kKey);  // any definite answer settles this payment
  if (status == 200 || status == 201) return Result::Success;
  if (status == 422) return Result::InsufficientFunds;
  if (status == 409) return Result::Conflict;
  if (status == 401 && has(body, "terminal_revoked")) return Result::TerminalRevoked;
  if (status == 403) return Result::NoEnrollment;
  return Result::ServerError;
}

}  // namespace biopay
