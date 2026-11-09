// Native test: `make -C firmware test`. Fakes stand in for Wi-Fi, NVS, the sensor and the RNG.
#include <cassert>
#include <cstdio>
#include <map>
#include <vector>
#include "../lib/payflow/payflow.h"
using namespace biopay;

struct FakeHttp : Http {
  std::vector<int> script; std::vector<std::string> bodies, sent;
  int post(const std::string& j, std::string& b) override {
    sent.push_back(j); int i = sent.size() - 1;
    b = i < (int)bodies.size() ? bodies[i] : ""; return script.at(i);
  }
};
struct FakeStore : Store {
  std::map<std::string, std::string> m;
  bool load(std::string& k, std::string& v) override { if (!m.count(k)) return false; v = m[k]; return true; }
  void save(const std::string& k, const std::string& v) override { m[k] = v; }
  void erase(const std::string& k) override { m.erase(k); }
};
struct FakeSensor : Sensor { bool ok = true; uint32_t slot = 7; bool match(uint32_t& s) override { s = slot; return ok; } };
struct FakeRng : Rng { int n = 0; std::string uuid4() override { return "uuid-" + std::to_string(++n); } };

struct Rig { FakeHttp h; FakeStore s; FakeSensor f; FakeRng r; PayFlow flow{h, s, f, r, 100}; };

int main() {
  { Rig t; t.h.script = {201};  // happy path: slot (not a template) and amount only
    assert(t.flow.start(40) == Result::Success);
    assert(t.h.sent[0] == "{\"payment_id\":\"uuid-1\",\"amount\":40,\"sensor_slot\":7}");
    assert(!t.flow.hasPending()); }
  { Rig t; t.h.script = {0, 0, 200};  // timeouts reuse the SAME uuid, then a replay is success
    assert(t.flow.start(40) == Result::NetworkRetry);
    assert(t.flow.retry() == Result::NetworkRetry);
    assert(t.flow.retry() == Result::Success);
    assert(t.h.sent[0] == t.h.sent[1] && t.h.sent[1] == t.h.sent[2]);
    assert(t.r.n == 1); }
  { Rig t; t.h.script = {0, 201}; t.flow.start(40);  // reboot: a fresh PayFlow over the same Store resumes
    PayFlow after{t.h, t.s, t.f, t.r, 100};
    assert(after.hasPending() && after.retry() == Result::Success);
    assert(t.h.sent[0] == t.h.sent[1]); }
  { Rig t; t.h.script = {0, 201};  // a new start while one is unconfirmed completes the old one, no 2nd UUID
    t.flow.start(40); t.flow.start(55);
    assert(t.h.sent[1] == t.h.sent[0] && t.r.n == 1); }
  { Rig t; t.h.script = {422}; assert(t.flow.start(40) == Result::InsufficientFunds); assert(!t.flow.hasPending()); }
  { Rig t; t.h.script = {403}; assert(t.flow.start(40) == Result::NoEnrollment); }
  { Rig t; t.h.script = {401}; t.h.bodies = {"{\"error\":{\"code\":\"terminal_revoked\"}}"};
    assert(t.flow.start(40) == Result::TerminalRevoked); assert(!t.flow.hasPending()); }
  { Rig t; t.h.script = {503}; assert(t.flow.start(40) == Result::NetworkRetry); assert(t.flow.hasPending()); }
  { Rig t; assert(t.flow.start(0) == Result::BadAmount); assert(t.flow.start(101) == Result::BadAmount); assert(t.h.sent.empty()); }
  { Rig t; t.f.ok = false; assert(t.flow.start(40) == Result::NoMatch); assert(!t.flow.hasPending() && t.h.sent.empty()); }
  std::puts("payflow: all tests passed");
}
