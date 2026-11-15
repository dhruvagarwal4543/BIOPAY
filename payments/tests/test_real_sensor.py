from uuid import uuid4

from django.test import TransactionTestCase, override_settings

from payments.models import Payment, Wallet
from payments.services import reconcile

from .test_web import KEY_A, SETTINGS, TERMINAL_PAY, enroll, key_client, login_client, make_customer, make_merchant, make_terminal

# Real-sensor mode with DEBUG off: no demo API, no simulator, no mock enrollment.
REAL = {**SETTINGS, "DEBUG": False, "BIOPAY_ENABLE_DEMO_API": False, "BIOPAY_TERMINAL_REAL_SENSOR": True}


@override_settings(**REAL)
class RealSensorTests(TransactionTestCase):
    def setUp(self):
        self.customer = make_customer("c1")
        self.terminal = make_terminal(make_merchant("m1"), KEY_A)
        self.client = key_client(KEY_A)

    def pay(self, slot, amount=30, pid=None):
        return self.client.post(TERMINAL_PAY, {"payment_id": str(pid or uuid4()), "amount": amount, "sensor_slot": slot}, format="json")

    def real_enrollment(self, slot=1):
        e = enroll(self.customer, self.terminal, slot)
        e.source = "R307S"
        e.save()

    def test_real_enrollment_pays_once_tagged_r307s_and_replays(self):
        self.real_enrollment()
        pid = uuid4()
        r = self.pay(1, pid=pid)
        self.assertEqual(r.status_code, 201)
        self.assertIn("R307S", r.data["authentication"])
        self.assertEqual(Payment.objects.get(pk=pid).auth_method, "R307S")
        self.assertEqual(self.pay(1, pid=pid).status_code, 200)  # replay, no second debit
        self.assertEqual(Wallet.objects.get(customer=self.customer).balance, 470)
        self.assertEqual(reconcile(), [])

    def test_mock_enrollment_cannot_pay_on_real_sensor_path(self):
        enroll(self.customer, self.terminal, 1)  # source MOCK
        self.assertEqual(self.pay(1).status_code, 403)
        self.assertEqual(Wallet.objects.get(customer=self.customer).balance, 500)

    def test_bad_key_refused_and_simulator_and_mock_enroll_stay_off(self):
        self.assertEqual(key_client("wrong").post(TERMINAL_PAY, {}, format="json").status_code, 401)
        self.assertEqual(login_client("u-m1").post("/api/merchant/simulate/", {}, format="json").status_code, 404)

    def test_customer_enrollment_is_consented_real_and_simulator_off(self):
        c = login_client("u-c1")
        body = {"terminal_id": self.terminal.pk, "allow_simulator": True}
        self.assertEqual(c.post("/api/customer/enroll/", body, format="json").status_code, 400)  # no consent
        r = c.post("/api/customer/enroll/", {**body, "consent": True}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual((r.data["enrollment"]["source"], r.data["enrollment"]["simulator_allowed"]), ("R307S", False))
        self.assertEqual(self.pay(r.data["enrollment"]["sensor_slot"]).status_code, 201)
