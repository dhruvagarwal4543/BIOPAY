from datetime import timedelta
from uuid import uuid4

from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from payments.models import TerminalStatus

from .test_real_sensor import REAL
from .test_web import KEY_A, KEY_B, SETTINGS, TERMINAL_PAY, enroll, key_client, login_client, make_customer, make_merchant, make_terminal

STATUS, LIVE = "/api/terminal/status/", "/api/merchant/terminals/live/"


@override_settings(**REAL)
class LiveTests(TransactionTestCase):
    def setUp(self):
        self.m1, self.m2 = make_merchant("m1"), make_merchant("m2")
        self.t1, self.t2 = make_terminal(self.m1, KEY_A), make_terminal(self.m2, KEY_B)
        self.dev = key_client(KEY_A)

    def live(self, user="u-m1"):
        return login_client(user).get(LIVE)

    def test_publish_then_owner_sees_live_screen(self):
        self.assertEqual(self.dev.post(STATUS, {"screen": "amount", "entry": "25"}, format="json").status_code, 200)
        t = self.live().data["terminals"][0]
        self.assertEqual((t["online"], t["screen"], t["data"]["entry"], t["data"]["mock"]), (True, "amount", "25", False))

    def test_never_live_without_a_device_and_stale_is_offline(self):
        self.assertEqual(self.live().data["terminals"][0]["screen"], None)  # no events ever: offline, nothing invented
        self.dev.post(STATUS, {"screen": "idle"}, format="json")
        TerminalStatus.objects.update(updated_at=timezone.now() - timedelta(seconds=60))
        t = self.live().data["terminals"][0]
        self.assertEqual((t["online"], t["screen"]), (False, None))
        self.dev.post(STATUS, {"screen": "idle"}, format="json")  # heartbeat = reconnect
        self.assertTrue(self.live().data["terminals"][0]["online"])

    def test_authorization(self):
        make_customer("c1")
        self.assertEqual(key_client("bad").post(STATUS, {"screen": "idle"}, format="json").status_code, 401)
        self.assertEqual(login_client("u-c1").get(LIVE).status_code, 403)
        self.assertEqual(login_client("u-m1").get(LIVE).data["terminals"][0]["id"], self.t1.pk)
        self.assertEqual([t["id"] for t in login_client("u-m2").get(LIVE).data["terminals"]], [self.t2.pk])
        from django.test import Client
        self.assertIn(Client().get(LIVE).status_code, (401, 403))

    def test_device_input_is_whitelisted(self):
        for bad in ({"screen": "success"}, {"screen": "idle", "entry": "12x"}, {"screen": "error", "code": "<b>"}, {"screen": "idle", "template": "AAAA"}):
            r = self.dev.post(STATUS, bad, format="json")
            if "template" in bad:
                self.assertEqual(r.status_code, 200)  # unknown fields are dropped, never stored
                self.assertNotIn("template", TerminalStatus.objects.get().data)
            else:
                self.assertEqual(r.status_code, 400, bad)  # a device cannot announce a payment result

    def test_payment_result_is_written_by_server_and_late_processing_dropped(self):
        c = make_customer("c1", balance=40)
        e = enroll(c, self.t1, 1); e.source = "R307S"; e.save()
        pid = uuid4()
        self.dev.post(TERMINAL_PAY, {"payment_id": str(pid), "amount": 30, "sensor_slot": 1}, format="json")
        self.dev.post(STATUS, {"screen": "processing"}, format="json")  # arrives after the result
        t = self.live().data["terminals"][0]
        self.assertEqual((t["screen"], t["data"]["amount"], t["data"]["ref"]), ("success", 30, str(pid)[:8]))
        self.dev.post(TERMINAL_PAY, {"payment_id": str(uuid4()), "amount": 30, "sensor_slot": 1}, format="json")
        self.assertEqual(self.live().data["terminals"][0]["screen"], "declined")  # only 10 left

    @override_settings(**SETTINGS, BIOPAY_TERMINAL_REAL_SENSOR=False)
    def test_mock_mode_is_flagged(self):
        self.dev.post(STATUS, {"screen": "idle"}, format="json")
        self.assertTrue(self.live().data["terminals"][0]["data"]["mock"])
