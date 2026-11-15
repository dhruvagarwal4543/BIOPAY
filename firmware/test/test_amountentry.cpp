// Native test: `make -C firmware test`.
#include <cassert>
#include <cstdio>
#include "../lib/amountentry/amountentry.h"
using namespace biopay;
using S = AmountEntry::State;

static AmountEntry run(const char* keys, int64_t max = 100) {
  AmountEntry a(max);
  for (; *keys; ++keys) a.feed(*keys);
  return a;
}

int main() {
  assert(run("25").value() == 25);
  assert(run("255").value() == 25);                       // 255 > max 100: digit ignored
  assert(run("25*").value() == 2);                        // backspace corrects
  assert(run("#").state() == S::Entering);                // cannot confirm zero
  assert(run("0#").state() == S::Entering);
  assert(run("*").state() == S::Cancelled);               // backspace on empty cancels
  assert(run("25#").state() == S::Confirming);
  assert(run("25#*").state() == S::Entering);             // go back and correct
  AmountEntry a = run("25#*");
  a.feed('*'); a.feed('3'); a.feed('#'); a.feed('#');
  assert(a.state() == S::Done && a.value() == 23);
  a.feed('9'); assert(a.value() == 23);                   // finished: further keys ignored
  assert(run("25#A").state() == S::Confirming);           // stray key does nothing
  std::puts("amountentry ok");
}
