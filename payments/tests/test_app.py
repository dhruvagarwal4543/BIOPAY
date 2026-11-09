from uuid import uuid4

from django.test import override_settings
from rest_framework.test import APIClient

from payments.models import AuditEvent, Customer, Enrollment, LedgerEntry, Wallet
from payments.services import reconcile

from .test_web import PASSWORD, Base, login_client

GOOD = {"username": "newbie", "password": "a-long-test-only-pass-77", "name": "New Bie", "consent": True}


class RegistrationTests(Base):
    def register(self, **over):
        return APIClient(enforce_csrf_checks=False).post("/api/auth/register/", {**GOOD, **over}, format="json")

    def test_register_creates_wallet_with_grant_logs_in_and_audits(self):
        with override_settings(BIOPAY_SIGNUP_GRANT=100):
            r = self.register()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["user"]["role"], "customer")
        w = Wallet.objects.get(customer__code="newbie")
        self.assertEqual((w.opening_balance, w.balance), (100, 100))
        self.assertEqual(reconcile(), [])
        self.assertTrue(AuditEvent.objects.filter(action="customer.registered").exists())

    def test_consent_is_mandatory(self):
        for bad in (False, "true", None):
            self.assertEqual(self.register(consent=bad).status_code, 400)
        self.assertFalse(Customer.objects.filter(code="newbie").exists())

    def test_weak_password_bad_username_and_duplicate_rejected(self):
        self.assertEqual(self.register(password="short").status_code, 400)
        self.assertEqual(self.register(username="Bad Name!").status_code, 400)
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.register().status_code, 400)

    def test_cannot_register_as_staff(self):
        self.register(is_staff=True, role="admin")
        self.assertEqual(self.register(username="other").data["user"]["role"], "customer")


class EnrollmentAndSimulatorTests(Base):
    def setUp(self):
        super().setUp()
        Enrollment.objects.update(simulator_allowed=True)

    def test_enroll_gets_fresh_slot_and_can_pay_through_simulator(self):
        carol = login_client(self.alice.user.username)
        r = carol.post("/api/customer/enroll/", {"terminal_id": self.term_b.pk, "consent": True,
                                                   "allow_simulator": True}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        e = Enrollment.objects.get(pk=r.data["enrollment"]["id"])
        self.assertEqual(e.sensor_slot, 2)  # term_b already has slot 1; never reused
        shop = login_client(self.shop_b.user.username)
        pay = shop.post("/api/merchant/simulate/", {"payment_id": str(uuid4()), "amount": 25,
                        "sensor_slot": 2, "terminal_id": self.term_b.pk}, format="json")
        self.assertEqual(pay.status_code, 201, pay.data)
        self.assertEqual(self.balance(customer=self.alice), 475)
        self.assertEqual(reconcile(), [])

    def test_enroll_needs_consent_and_rejects_duplicates(self):
        c = login_client(self.alice.user.username)
        body = {"terminal_id": self.term_b.pk}
        self.assertEqual(c.post("/api/customer/enroll/", body, format="json").status_code, 400)
        self.assertEqual(c.post("/api/customer/enroll/", {**body, "consent": True}, format="json").status_code, 201)
        self.assertEqual(c.post("/api/customer/enroll/", {**body, "consent": True}, format="json").status_code, 400)

    def test_simulator_only_for_own_terminal_and_merchant_role(self):
        shop = login_client(self.shop_a.user.username)
        body = {"payment_id": str(uuid4()), "amount": 5, "sensor_slot": 1}
        self.assertEqual(shop.post("/api/merchant/simulate/", {**body, "terminal_id": self.term_b.pk}, format="json").status_code, 404)
        cust = login_client(self.alice.user.username)
        self.assertEqual(cust.post("/api/merchant/simulate/", {**body, "terminal_id": self.term_a.pk}, format="json").status_code, 403)

    def test_simulator_revoked_is_403_not_401_and_unknown_slot_403(self):
        shop = login_client(self.shop_a.user.username)
        body = {"payment_id": str(uuid4()), "amount": 5, "terminal_id": self.term_a.pk}
        self.assertEqual(shop.post("/api/merchant/simulate/", {**body, "sensor_slot": 99}, format="json").status_code, 403)
        login_client("boss").post(f"/api/admin/terminals/{self.term_a.pk}/revoke/")
        r = shop.post("/api/merchant/simulate/", {**body, "sensor_slot": 1}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(LedgerEntry.objects.count(), 0)

    def test_simulator_idempotent_retry(self):
        shop = login_client(self.shop_a.user.username)
        body = {"payment_id": str(uuid4()), "amount": 5, "terminal_id": self.term_a.pk, "sensor_slot": 1}
        self.assertEqual(shop.post("/api/merchant/simulate/", body, format="json").status_code, 201)
        self.assertEqual(shop.post("/api/merchant/simulate/", body, format="json").status_code, 200)
        self.assertEqual(self.balance(customer=self.alice), 495)

    @override_settings(BIOPAY_ENABLE_DEMO_API=False)
    def test_simulator_and_enroll_off_without_opt_in(self):
        shop = login_client(self.shop_a.user.username)
        self.assertEqual(shop.post("/api/merchant/simulate/", {}, format="json").status_code, 404)
        c = login_client(self.alice.user.username)
        self.assertEqual(c.post("/api/customer/enroll/", {"terminal_id": 1, "consent": True}, format="json").status_code, 404)


class DetailAndAuditTests(Base):
    def test_payment_detail_is_scoped_to_owner(self):
        pid = self.pay(slot=1).data["payment"]["payment_id"]
        self.assertEqual(login_client(self.alice.user.username).get(f"/api/customer/payments/{pid}/").status_code, 200)
        self.assertEqual(login_client(self.bob.user.username).get(f"/api/customer/payments/{pid}/").status_code, 404)
        self.assertEqual(login_client(self.shop_a.user.username).get(f"/api/merchant/payments/{pid}/").status_code, 200)
        self.assertEqual(login_client(self.shop_b.user.username).get(f"/api/merchant/payments/{pid}/").status_code, 404)
        self.assertEqual(login_client(self.alice.user.username).get("/api/customer/payments/not-a-uuid/").status_code, 400)

    def test_audit_log_records_admin_actions_and_is_admin_only(self):
        admin = login_client("boss")
        admin.post(f"/api/admin/enrollments/{self.enr_alice.pk}/revoke/")
        rows = admin.get("/api/admin/audit/").data["results"]
        self.assertEqual(rows[0]["action"], "enrollment.revoked")
        self.assertEqual(rows[0]["actor"], "boss")
        self.assertEqual(login_client(self.alice.user.username).get("/api/admin/audit/").status_code, 403)


class AuditCoverageTests(Base):
    def actions(self):
        return set(AuditEvent.objects.values_list("action", flat=True))

    def test_every_sensitive_action_is_logged(self):
        alice = login_client(self.alice.user.username)
        alice.post(f"/api/customer/enrollments/{self.enr_alice.pk}/deletion-request/")
        alice.post("/api/customer/enroll/", {"terminal_id": self.term_b.pk, "consent": True}, format="json")
        admin = login_client("boss")
        admin.post(f"/api/admin/terminals/{self.term_b.pk}/revoke/")
        self.assertTrue({"enrollment.deletion_requested", "enrollment.created", "terminal.revoked"} <= self.actions())

    def test_simulator_revoked_error_code_is_stable(self):
        login_client("boss").post(f"/api/admin/terminals/{self.term_a.pk}/revoke/")
        r = login_client(self.shop_a.user.username).post("/api/merchant/simulate/", {
            "payment_id": str(uuid4()), "amount": 5, "terminal_id": self.term_a.pk, "sensor_slot": 1}, format="json")
        self.assertEqual(r.data["error"]["code"], "terminal_revoked")


class SimulatorAuthorizationTests(Base):
    """The merchant simulator may only charge enrollments whose owner explicitly allowed it."""

    def sim(self, slot=1, amount=5, pid=None, term=None, user=None):
        return login_client(user or self.shop_a.user.username).post("/api/merchant/simulate/", {
            "payment_id": str(pid or uuid4()), "amount": amount, "sensor_slot": slot,
            "terminal_id": (term or self.term_a).pk}, format="json")

    def allow(self, enrollment, allowed=True):
        r = login_client(enrollment.customer.user.username).post(
            f"/api/customer/enrollments/{enrollment.pk}/simulator/", {"allowed": allowed}, format="json")
        self.assertEqual(r.status_code, 200, r.data)

    def test_default_is_off_so_unauthorized_slots_cannot_be_charged(self):
        for slot in (1, 2, 99):  # real enrollments and a guess, all refused
            self.assertEqual(self.sim(slot=slot).status_code, 403)
        self.assertEqual(LedgerEntry.objects.count(), 0)
        self.assertEqual(self.balance(customer=self.alice), 500)

    def test_customer_opt_in_enables_only_that_enrollment(self):
        self.allow(self.enr_alice)
        self.assertEqual(self.sim(slot=1).status_code, 201)
        self.assertEqual(self.sim(slot=2).status_code, 403)  # bob never opted in
        self.assertEqual(self.balance(customer=self.bob), 500)

    def test_revoking_simulator_consent_blocks_new_payments_but_replays_old_result(self):
        self.allow(self.enr_alice)
        pid = uuid4()
        self.assertEqual(self.sim(pid=pid).status_code, 201)
        self.allow(self.enr_alice, False)
        self.assertEqual(self.sim().status_code, 403)
        again = self.sim(pid=pid)
        self.assertEqual((again.status_code, again.data["replayed"]), (200, True))
        self.assertEqual(self.balance(customer=self.alice), 495)
        self.assertEqual(LedgerEntry.objects.count(), 2)

    def test_revoked_enrollment_is_refused_even_with_consent(self):
        self.allow(self.enr_alice)
        login_client("boss").post(f"/api/admin/enrollments/{self.enr_alice.pk}/revoke/")
        self.assertEqual(self.sim().status_code, 403)
        self.assertEqual(LedgerEntry.objects.count(), 0)

    def test_terminal_ownership(self):
        self.allow(self.enr_bob_b)
        # shop_a cannot use shop_b's terminal, even for a consenting customer.
        self.assertEqual(self.sim(slot=1, term=self.term_b).status_code, 404)
        self.assertEqual(self.sim(slot=1, term=self.term_b, user=self.shop_b.user.username).status_code, 201)

    def test_same_uuid_charges_once_and_changed_payload_conflicts(self):
        self.allow(self.enr_alice)
        pid = uuid4()
        self.assertEqual(self.sim(pid=pid, amount=5).status_code, 201)
        self.assertEqual(self.sim(pid=pid, amount=5).status_code, 200)
        self.assertEqual(self.sim(pid=pid, amount=6).status_code, 409)
        self.assertEqual(self.balance(customer=self.alice), 495)
        self.assertEqual(LedgerEntry.objects.count(), 2)

    def test_insufficient_funds_declines_without_ledger(self):
        self.allow(self.enr_alice)
        Wallet.objects.filter(customer=self.alice).update(balance=3, opening_balance=3)
        r = self.sim(amount=5)
        self.assertEqual((r.status_code, r.data["error"]["code"]), (422, "insufficient_funds"))
        self.assertEqual(LedgerEntry.objects.count(), 0)

    def test_only_the_owner_can_toggle_consent_and_input_is_strict(self):
        c = login_client(self.bob.user.username)
        url = f"/api/customer/enrollments/{self.enr_alice.pk}/simulator/"
        self.assertEqual(c.post(url, {"allowed": True}, format="json").status_code, 404)
        own = f"/api/customer/enrollments/{self.enr_bob.pk}/simulator/"
        self.assertEqual(c.post(own, {"allowed": "yes"}, format="json").status_code, 400)
        self.assertEqual(login_client(self.shop_a.user.username).post(own, {"allowed": True}, format="json").status_code, 403)
        self.assertEqual(self.balance(customer=self.alice), 500)

    def test_consent_changes_are_audited(self):
        self.allow(self.enr_alice)
        self.allow(self.enr_alice, False)
        actions = set(AuditEvent.objects.values_list("action", flat=True))
        self.assertTrue({"enrollment.simulator_on", "enrollment.simulator_off"} <= actions)
