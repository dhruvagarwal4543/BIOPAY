# Native (laptop) test of the hardware-independent payment flow. No ESP32 needed.
.PHONY: test
test:
	c++ -std=c++17 -Wall -Wextra -o /tmp/payflow_test test/test_payflow.cpp lib/payflow/payflow.cpp && /tmp/payflow_test
