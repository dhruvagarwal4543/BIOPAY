# Native (laptop) tests of the hardware-independent logic. No ESP32 needed.
.PHONY: test
test:
	c++ -std=c++17 -Wall -Wextra -o /tmp/payflow_test test/test_payflow.cpp lib/payflow/payflow.cpp && /tmp/payflow_test
	c++ -std=c++17 -Wall -Wextra -o /tmp/amountentry_test test/test_amountentry.cpp && /tmp/amountentry_test
