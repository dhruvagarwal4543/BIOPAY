// Keypad amount entry as a pure state machine (native-tested). Keys: 0-9 digit, * backspace/cancel, # confirm.
#pragma once
#include <cstdint>

namespace biopay {

class AmountEntry {
 public:
  enum class State { Entering, Confirming, Done, Cancelled };
  explicit AmountEntry(int64_t max) : max_(max) {}
  State feed(char k) {
    if (state_ == State::Done || state_ == State::Cancelled) return state_;
    if (state_ == State::Confirming) {  // '#' pays this amount; '*' goes back to correct it
      if (k == '#') state_ = State::Done;
      else if (k == '*') state_ = State::Entering;
      return state_;
    }
    if (k >= '0' && k <= '9') {
      int64_t next = value_ * 10 + (k - '0');
      if (next <= max_) value_ = next;  // ignore a digit that would exceed the limit
    } else if (k == '*') {
      if (value_ == 0) state_ = State::Cancelled; else value_ /= 10;
    } else if (k == '#' && value_ >= 1) {
      state_ = State::Confirming;
    }
    return state_;
  }
  int64_t value() const { return value_; }
  State state() const { return state_; }

 private:
  int64_t max_, value_ = 0;
  State state_ = State::Entering;
};

}  // namespace biopay
