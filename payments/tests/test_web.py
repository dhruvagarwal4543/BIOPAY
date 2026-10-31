from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier, Event, Timer
from unittest.mock import patch
from uuid import uuid4

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection, connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from payments.authentication import hash_terminal_key
from payments.models import Customer, Enrollment, LedgerEntry, Merchant, Payment, Terminal, Wallet

# Public, test-only values.
PASSWORD = "test-only-password-123"
KEY_A, KEY_B = "test-only-terminal-key-a", "test-only-terminal-key-b"
SETTINGS = {"DEBUG": True, "BIOPAY_ENABLE_DEMO_API": True, "BIOPAY_MAX_PAYMENT": 100,
            "BIOPAY_DEMO_TOKEN": "x" * 32, "ALLOWED_HOSTS": ["testserver"]}
TERMINAL_PAY = "/api/terminal/payments/"
User = get_user_model()


def make_customer(code, balance=500):
    user = User.objects.create_user(f"u-{code}", password=PASSWORD)
    customer = Customer.objects.create(code=code, name=f"Name {code}", user=user)
    Wallet.objects.create(customer=customer, opening_balance=balance, balance=balance)
    return customer


def make_merchant(code):
    user = User.objects.create_user(f"u-{code}", password=PASSWORD)
    merchant = Merchant.objects.create(code=code, name=f"Shop {code}", user=user)
    Wallet.objects.create(merchant=merchant)
    return merchant


def make_terminal(merchant, key):
    return Terminal.objects.create(merchant=merchant, name=f"T-{merchant.code}", key_hash=hash_terminal_key(key))


def enroll(customer, terminal, slot):
    return Enrollment.objects.create(customer=customer, terminal=terminal, sensor_slot=slot,
                                     consented_at=timezone.now())


def key_client(key):
    client = APIClient()
    client.credentials(HTTP_X_BIOPAY_TERMINAL_KEY=key)
    return client


def login_client(username):
    client = APIClient()
    assert client.login(username=username, password=PASSWORD)
    return client


@override_settings(**SETTINGS)
class Base(TransactionTestCase):
    def setUp(self):
        self.alice, self.bob = make_customer("alice"), make_customer("bob")
        self.shop_a, self.shop_b = make_merchant("shop-a"), make_merchant("shop-b")
        self.term_a, self.term_b = make_terminal(self.shop_a, KEY_A), make_terminal(self.shop_b, KEY_B)
        self.enr_alice = enroll(self.alice, self.term_a, 1)
        self.enr_bob = enroll(self.bob, self.term_a, 2)
        self.enr_bob_b = enroll(self.bob, self.term_b, 1)
        self.admin_user = User.objects.create_user("boss", password=PASSWORD, is_staff=True)
        self.terminal = key_client(KEY_A)

    def pay(self, slot=1, amount=40, payment_id=None, client=None, **extra):
        return (client or self.terminal).post(
            TERMINAL_PAY,
            {"payment_id": str(payment_id or uuid4()), "amount": amount, "sensor_slot": slot, **extra},
            format="json")

    def balance(self, **owner):
        return Wallet.objects.get(**owner).balance


class TerminalPaymentTests(Base):
    def test_40_biocoin_transfer_derives_parties_and_is_labelled_mock(self):
        r = self.pay()
        self.assertEqual(r.status_code, 201)
        self.assertIn("NOT A PHYSICAL FINGERPRINT MATCH", r.data["authentication"])
        self.assertEqual(r.data["warning"], "SIMULATED — NO REAL MONEY")
        payment = Payment.objects.get()
        self.assertEqual((payment.payer, payment.merchant, payment.terminal, payment.auth_method),
                         (self.alice, self.shop_a, self.term_a, "MOCK"))
        self.assertEqual((self.balance(customer=self.alice), self.balance(merchant=self.shop_a)), (460, 40))
        self.assertEqual(LedgerEntry.objects.count(), 2)

    def test_terminal_cannot_choose_payer_or_merchant(self):
        for extra in ({"payer": self.bob.pk}, {"merchant": self.shop_b.pk}, {"customer_id": 2}):
            self.assertEqual(self.pay(**extra).status_code, 400)
        self.assertFalse(Payment.objects.exists())

    def test_duplicate_uuid_transfers_once(self):
        pid = uuid4()
        self.assertEqual(self.pay(payment_id=pid).status_code, 201)
        r = self.pay(payment_id=pid)
        self.assertEqual((r.status_code, r.data["replayed"]), (200, True))
        self.assertEqual(self.balance(customer=self.alice), 460)
        self.assertEqual(LedgerEntry.objects.count(), 2)

    def test_same_uuid_changed_fields_conflict(self):
        pid = uuid4()
        self.pay(payment_id=pid)
        self.assertEqual(self.pay(payment_id=pid, amount=41).status_code, 409)
        self.assertEqual(self.pay(slot=2, payment_id=pid).status_code, 409)  # different payer
        self.assertEqual(self.balance(customer=self.alice), 460)
        self.assertEqual(self.balance(customer=self.bob), 500)

    def test_insufficient_balance_is_declined_without_ledger(self):
        Wallet.objects.filter(customer=self.alice).update(balance=10, opening_balance=10)
        r = self.pay()
        self.assertEqual((r.status_code, r.data["error"]["code"]), (422, "insufficient_funds"))
        self.assertEqual(self.balance(customer=self.alice), 10)
        self.assertFalse(LedgerEntry.objects.exists())

    def test_failure_rolls_back_atomically_then_retry_succeeds(self):
        original = Wallet.save

        def fail_on_credit(wallet, *a, **kw):
            if wallet.merchant_id:
                raise DatabaseError("injected")
            return original(wallet, *a, **kw)

        pid = uuid4()
        with patch.object(Wallet, "save", autospec=True, side_effect=fail_on_credit):
            with self.assertRaises(DatabaseError):
                self.pay(payment_id=pid)
        self.assertFalse(Payment.objects.exists() or LedgerEntry.objects.exists())
        self.assertEqual(self.balance(customer=self.alice), 500)
        self.assertEqual(self.pay(payment_id=pid).status_code, 201)

    def test_unknown_slot_is_forbidden(self):
        r = self.pay(slot=99)
        self.assertEqual((r.status_code, r.data["error"]["code"]), (403, "enrollment_inactive"))

    def test_slot_is_scoped_to_the_authenticated_terminal(self):
        # Bob's slot 2 exists only on terminal A, so terminal B cannot use it.
        self.assertEqual(self.pay(slot=2, client=key_client(KEY_B)).status_code, 403)
        r = self.pay(slot=1, client=key_client(KEY_B))  # Bob's slot 1 on terminal B
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Payment.objects.get().payer, self.bob)
        self.assertEqual(Payment.objects.get().merchant, self.shop_b)

    def test_revoked_terminal_key_is_rejected(self):
        Terminal.objects.filter(pk=self.term_a.pk).update(revoked_at=timezone.now())
        self.assertEqual(self.pay().status_code, 401)
        self.assertFalse(Payment.objects.exists())

    def test_bad_missing_keys_and_key_separation(self):
        self.assertEqual(self.pay(client=APIClient()).status_code, 401)
        self.assertEqual(self.pay(client=key_client("nope")).status_code, 401)
        demo = APIClient()
        demo.credentials(HTTP_X_BIOPAY_DEMO_TOKEN="x" * 32)
        self.assertEqual(self.pay(client=demo).status_code, 401)  # demo token is not a terminal key
        r = key_client(KEY_A).post("/api/dev/mock/payments/", {"payment_id": str(uuid4()), "amount": 1}, format="json")
        self.assertEqual(r.status_code, 401)  # terminal key is not the demo token

    def test_terminal_api_off_without_mock_opt_in(self):
        with override_settings(BIOPAY_ENABLE_DEMO_API=False):
            self.assertEqual(self.pay().status_code, 404)

    def test_last_seen_and_status_isolation(self):
        pid = uuid4()
        self.pay(payment_id=pid)
        self.term_a.refresh_from_db()
        self.assertIsNotNone(self.term_a.last_seen)
        self.assertEqual(self.terminal.get(f"{TERMINAL_PAY}{pid}/").status_code, 200)
        self.assertEqual(key_client(KEY_B).get(f"{TERMINAL_PAY}{pid}/").status_code, 404)

    def test_deletion_request_revocation_and_stale_enrollment_block_payment(self):
        login_client("u-alice").post(f"/api/customer/enrollments/{self.enr_alice.pk}/deletion-request/")
        r = self.pay()
        self.assertEqual((r.status_code, r.data["error"]["code"]), (403, "enrollment_inactive"))
        admin = login_client("boss")
        self.assertEqual(admin.post(f"/api/admin/enrollments/{self.enr_alice.pk}/revoke/").status_code, 200)
        self.assertEqual(self.pay().status_code, 403)
        self.enr_alice.refresh_from_db()
        self.assertEqual((self.enr_alice.status, self.enr_alice.revoked_at is not None), ("REVOKED", True))
        self.assertFalse(Payment.objects.exists())
        # A revoked slot may be re-enrolled; only one live enrollment per slot.
        enroll(self.alice, self.term_a, 1)
        self.assertEqual(self.pay().status_code, 201)


class AccessTests(Base):
    def setUp(self):
        super().setUp()
        self.pay(slot=1)  # alice -> shop A
        self.pay(slot=2, amount=15)  # bob -> shop A
        self.pay(slot=1, amount=7, client=key_client(KEY_B))  # bob -> shop B

    def test_customer_sees_only_own_wallet_history_and_enrollments(self):
        c = login_client("u-alice")
        o = c.get("/api/customer/overview/").data
        self.assertEqual(o["balance"], 460)
        self.assertEqual([p["amount"] for p in c.get("/api/customer/payments/").data["results"]], [40])
        self.assertEqual([e["id"] for e in o["enrollments"]], [self.enr_alice.pk])
        self.assertEqual(c.get("/api/customer/payments/").data["count"], 1)
        bob = login_client("u-bob").get("/api/customer/overview/").data
        self.assertEqual(bob["balance"], 500 - 15 - 7)

    def test_customer_cannot_act_on_another_customers_enrollment(self):
        r = login_client("u-alice").post(f"/api/customer/enrollments/{self.enr_bob.pk}/deletion-request/")
        self.assertEqual(r.status_code, 404)
        self.enr_bob.refresh_from_db()
        self.assertEqual(self.enr_bob.status, "ACTIVE")

    def test_customer_cannot_pass_ids_to_read_others(self):
        c = login_client("u-alice")
        for q in ("?customer=2", f"?customer_id={self.bob.pk}", f"?payer={self.bob.pk}"):
            self.assertEqual(c.get("/api/customer/payments/" + q).data["count"], 1)

    def test_merchant_isolation_and_opaque_customer(self):
        a = login_client("u-shop-a").get("/api/merchant/overview/").data
        b = login_client("u-shop-b").get("/api/merchant/overview/").data
        self.assertEqual((a["balance"], b["balance"]), (55, 7))
        self.assertEqual([t["name"] for t in a["terminals"]], ["T-shop-a"])
        self.assertEqual(login_client("u-shop-b").get("/api/merchant/payments/").data["count"], 1)
        history = login_client("u-shop-a").get("/api/merchant/payments/").data["results"]
        self.assertNotIn("Name alice", str(a) + str(history))
        self.assertTrue(all(p["payer"].startswith("Customer #") for p in history))

    def test_roles_cannot_cross_into_other_dashboards(self):
        cust, merch, admin = (login_client(u) for u in ("u-alice", "u-shop-a", "boss"))
        for client, allowed in ((cust, "customer"), (merch, "merchant"), (admin, "admin")):
            for role in ("customer", "merchant", "admin"):
                if role != allowed:
                    self.assertEqual(client.get(f"/api/{role}/overview/").status_code, 403, (allowed, role))
        self.assertEqual(cust.post(f"/api/admin/terminals/{self.term_a.pk}/revoke/").status_code, 403)
        self.assertEqual(merch.post(f"/api/admin/enrollments/{self.enr_bob.pk}/revoke/").status_code, 403)

    def test_anonymous_and_unlinked_users_are_denied(self):
        User.objects.create_user("ghost", password=PASSWORD)
        # No session -> 401 (sign in); signed in without a role -> 403 (not allowed).
        for client, expected in ((APIClient(), 401), (login_client("ghost"), 403)):
            for path in ("customer", "merchant", "admin"):
                self.assertEqual(client.get(f"/api/{path}/overview/").status_code, expected)
        self.assertEqual(login_client("ghost").get("/api/auth/me/").data["user"], None)

    def test_inactive_admin_is_denied(self):
        c = login_client("boss")
        User.objects.filter(username="boss").update(is_active=False)
        self.assertEqual(c.get("/api/admin/overview/").status_code, 401)  # session no longer valid

    def test_admin_overview_and_controls(self):
        admin = login_client("boss")
        o = admin.get("/api/admin/overview/").data
        self.assertTrue(o["reconciliation"]["ok"])
        self.assertEqual(len(o["customers"]), 2)
        self.assertEqual(admin.get("/api/admin/payments/").data["count"], 3)
        admin.post(f"/api/admin/terminals/{self.term_a.pk}/revoke/")
        self.assertEqual(self.pay().status_code, 401)
        self.assertEqual(admin.post("/api/admin/terminals/9999/revoke/").status_code, 404)

    def test_no_balance_editing_endpoint_or_admin_permission(self):
        admin = login_client("boss")
        for method in (admin.post, admin.put, admin.patch):
            self.assertIn(method("/api/admin/wallets/1/", {"balance": 9999}, format="json").status_code, (404, 405))
        request = type("R", (), {"user": self.admin_user})()
        for model in (Wallet, Payment, LedgerEntry):
            ma = admin_site_model(model)
            self.assertFalse(ma.has_change_permission(request) or ma.has_add_permission(request)
                             or ma.has_delete_permission(request))


def admin_site_model(model):
    return admin.site._registry[model]


class AuthTests(Base):
    def test_login_logout_flow_with_csrf(self):
        c = APIClient(enforce_csrf_checks=True)
        body = {"username": "u-alice", "password": PASSWORD}
        self.assertEqual(c.post("/api/auth/login/", body, format="json").status_code, 403)  # no CSRF token
        token = c.get("/api/auth/csrf/").data["csrf_token"]
        self.assertEqual(c.post("/api/auth/login/", {**body, "password": "wrong"}, format="json",
                                HTTP_X_CSRFTOKEN=token).status_code, 401)
        r = c.post("/api/auth/login/", body, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual((r.status_code, r.data["user"]["role"]), (200, "customer"))
        token = c.cookies["csrftoken"].value
        self.assertEqual(c.post("/api/auth/logout/").status_code, 403)  # session write needs CSRF
        self.assertEqual(c.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertIsNone(c.get("/api/auth/me/").data["user"])

    def test_admin_state_change_requires_csrf(self):
        c = APIClient(enforce_csrf_checks=True)
        c.login(username="boss", password=PASSWORD)
        self.assertEqual(c.post(f"/api/admin/terminals/{self.term_a.pk}/revoke/").status_code, 403)
        self.term_a.refresh_from_db()
        self.assertIsNone(self.term_a.revoked_at)

    def test_login_ignores_role_supplied_by_browser(self):
        r = APIClient().post("/api/auth/login/", {"username": "u-alice", "password": PASSWORD, "role": "admin"}, format="json")
        self.assertEqual(r.data["user"]["role"], "customer")

    def test_passwords_are_hashed(self):
        self.assertTrue(User.objects.get(username="u-alice").password.startswith("pbkdf2_"))


class ReconciliationTests(Base):
    def test_consistent_after_payments_and_detects_tampering(self):
        self.pay()
        self.pay(slot=2, amount=3)
        call_command("reconcile", stdout=StringIO())
        Wallet.objects.filter(customer=self.alice).update(balance=1000)  # privileged tampering
        with self.assertRaisesMessage(CommandError, "wallet"):
            call_command("reconcile", stdout=StringIO())
        self.assertFalse(login_client("boss").get("/api/admin/overview/").data["reconciliation"]["ok"])

    def test_detects_unbalanced_payment(self):
        self.pay()
        LedgerEntry.objects.filter(payment=Payment.objects.get()).first().delete()
        with self.assertRaises(CommandError):
            call_command("reconcile", stdout=StringIO())


class SeedCommandTests(TransactionTestCase):
    @override_settings(**SETTINGS)
    def test_demo_users_need_a_password_and_work_end_to_end(self):
        with self.assertRaises(CommandError), patch.dict("os.environ", {"BIOPAY_DEMO_PASSWORD": ""}):
            call_command("seed_demo_users", stdout=StringIO())
        out = StringIO()
        with patch.dict("os.environ", {"BIOPAY_DEMO_PASSWORD": PASSWORD}):
            call_command("seed_demo_users", stdout=out)
            call_command("seed_demo_users", stdout=StringIO())  # repeatable
        self.assertNotIn(PASSWORD, out.getvalue())
        key = out.getvalue().split("shown once): ")[1].split()[0]
        self.assertEqual(Terminal.objects.count(), 1)
        r = key_client(key).post(TERMINAL_PAY, {"payment_id": str(uuid4()), "amount": 40, "sensor_slot": 1}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(login_client("demo-customer").get("/api/customer/overview/").data["balance"], 460)


class SessionSemanticsTests(Base):
    """The browser redirects to login on 401 only, so 401 vs 403 must be exact."""

    def test_expired_or_missing_session_is_401_but_wrong_role_is_403(self):
        c = login_client("u-alice")
        self.assertEqual(c.get("/api/customer/overview/").status_code, 200)
        self.assertEqual(c.get("/api/admin/overview/").status_code, 403)  # still signed in
        c.post("/api/auth/logout/")
        for path in ("/api/customer/overview/", "/api/admin/overview/", "/api/customer/payments/"):
            r = c.get(path)
            self.assertEqual(r.status_code, 401, path)
            self.assertEqual(r.headers["WWW-Authenticate"], "Session")

    def test_deleted_session_row_is_401(self):
        from django.contrib.sessions.models import Session
        c = login_client("u-alice")
        Session.objects.all().delete()
        self.assertEqual(c.get("/api/customer/overview/").status_code, 401)

    def test_failed_login_stays_401_with_message(self):
        r = APIClient().post("/api/auth/login/", {"username": "u-alice", "password": "wrong"}, format="json")
        self.assertEqual((r.status_code, r.data["error"]["code"]), (401, "authentication_failed"))

    def test_csrf_failure_is_403_not_401(self):
        c = APIClient(enforce_csrf_checks=True)
        c.login(username="u-alice", password=PASSWORD)
        self.assertEqual(c.post("/api/auth/logout/").status_code, 403)

    def test_missing_wallet_is_503_not_500(self):
        Wallet.objects.filter(customer=self.alice).delete()
        r = login_client("u-alice").get("/api/customer/overview/")
        self.assertEqual((r.status_code, r.data["error"]["code"]), (503, "demo_not_ready"))


class EnrollmentAdminTests(Base):
    def setUp(self):
        super().setUp()
        self.su = User.objects.create_superuser("root", password=PASSWORD)
        self.web = login_client("root")

    def change_url(self, pk):
        return f"/admin/payments/enrollment/{pk}/change/"

    def test_identity_fields_are_read_only_after_creation(self):
        model_admin = admin_site_model(Enrollment)
        request = type("R", (), {"user": self.su})()
        self.assertCountEqual(
            model_admin.get_readonly_fields(request, self.enr_alice),
            ["source", "customer", "terminal", "sensor_slot", "consented_at"],
        )
        self.assertEqual(model_admin.get_readonly_fields(request, None), ["source"])
        self.assertNotIn("status", model_admin.get_readonly_fields(request, self.enr_alice))

    def test_posting_changed_identity_fields_through_admin_changes_nothing(self):
        before = Enrollment.objects.get(pk=self.enr_alice.pk)
        r = self.web.post(self.change_url(before.pk), {
            "customer": self.bob.pk, "terminal": self.term_b.pk, "sensor_slot": 77,
            "consented_at_0": "2001-01-01", "consented_at_1": "00:00:00",
            "source": "SENSOR", "status": "ACTIVE",
        })
        self.assertIn(r.status_code, (200, 302))
        after = Enrollment.objects.get(pk=before.pk)
        self.assertEqual(
            (after.customer_id, after.terminal_id, after.sensor_slot, after.consented_at, after.source),
            (before.customer_id, before.terminal_id, before.sensor_slot, before.consented_at, "MOCK"),
        )

    def test_status_remains_editable_and_enrollment_can_still_be_created(self):
        self.web.post(self.change_url(self.enr_alice.pk), {"status": "REVOKED"})
        self.enr_alice.refresh_from_db()
        self.assertEqual(self.enr_alice.status, "REVOKED")
        self.assertEqual(self.web.get("/admin/payments/enrollment/add/").status_code, 200)
        self.assertEqual(self.web.get(self.change_url(self.enr_alice.pk)).status_code, 200)


class TerminalRevocationRaceTests(Base):
    def setUp(self):
        super().setUp()
        self.assertEqual(connection.vendor, "postgresql")  # never substitute SQLite

    def assert_consistent(self):
        call_command("reconcile", stdout=StringIO())
        self.assertEqual(LedgerEntry.objects.count(), Payment.objects.filter(status="SUCCESS").count() * 2)

    def test_revocation_after_key_check_but_before_payment_is_rejected(self):
        """The auth step passed on a not-yet-revoked terminal; revoke commits before the payment."""
        from payments.api_errors import TerminalRevoked
        from payments.services import pay_at_terminal
        stale = Terminal.objects.get(pk=self.term_a.pk)
        self.assertIsNone(stale.revoked_at)
        Terminal.objects.filter(pk=stale.pk).update(revoked_at=timezone.now())
        with self.assertRaises(TerminalRevoked):
            pay_at_terminal(terminal=stale, sensor_slot=1, payment_id=uuid4(), amount=40)
        self.assertFalse(Payment.objects.exists() or LedgerEntry.objects.exists())
        self.assertEqual((self.balance(customer=self.alice), self.balance(merchant=self.shop_a)), (500, 0))
        self.assert_consistent()

    def test_revoke_waits_for_an_in_flight_payment_then_applies(self):
        """The payment holds the terminal row lock mid-transaction; revoke must queue behind it."""
        in_txn, payment_may_finish = Event(), Event()
        original = Payment.objects.get_or_create

        def pause_inside_transaction(*args, **kwargs):
            in_txn.set()  # the terminal row is already locked at this point
            payment_may_finish.wait(timeout=10)
            return original(*args, **kwargs)

        def pay_worker():
            try:
                return self.pay(client=key_client(KEY_A)).status_code
            finally:
                connections.close_all()

        revoke_client = login_client("boss")

        def revoke_worker():
            try:
                self.assertTrue(in_txn.wait(timeout=10))
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '10s'")
                Timer(0.7, payment_may_finish.set).start()  # release the payment once revoke has queued
                status = revoke_client.post(f"/api/admin/terminals/{self.term_a.pk}/revoke/").status_code
                # If revoke had not waited, it would return before the payment was released.
                return status, payment_may_finish.is_set()
            finally:
                connections.close_all()

        with patch.object(Payment.objects, "get_or_create", side_effect=pause_inside_transaction):
            with ThreadPoolExecutor(max_workers=2) as pool:
                pay_future, revoke_future = pool.submit(pay_worker), pool.submit(revoke_worker)
                pay_status, (revoke_status, payment_had_finished) = pay_future.result(), revoke_future.result()
        self.assertEqual(pay_status, 201)
        self.assertEqual(revoke_status, 200)
        self.assertTrue(payment_had_finished, "revoke returned while the payment was still open")
        self.assertEqual((self.balance(customer=self.alice), self.balance(merchant=self.shop_a)), (460, 40))
        self.assertEqual(self.pay().status_code, 401)  # revoked now: later payments fail
        self.assertEqual(Payment.objects.count(), 1)
        self.assert_consistent()

    def test_unsynchronized_race_has_only_the_two_allowed_outcomes(self):
        for attempt in range(5):
            Terminal.objects.filter(pk=self.term_a.pk).update(revoked_at=None)
            Wallet.objects.filter(customer=self.alice).update(balance=500)
            Wallet.objects.filter(merchant=self.shop_a).update(balance=0)
            LedgerEntry.objects.all().delete()
            Payment.objects.all().delete()
            start = Barrier(2)
            revoke_client = login_client("boss")

            def pay_worker():
                try:
                    start.wait(timeout=10)
                    return self.pay(client=key_client(KEY_A)).status_code
                finally:
                    connections.close_all()

            def revoke_worker():
                try:
                    start.wait(timeout=10)
                    return revoke_client.post(f"/api/admin/terminals/{self.term_a.pk}/revoke/").status_code
                finally:
                    connections.close_all()

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(pay_worker), pool.submit(revoke_worker)]
                pay_status, revoke_status = (f.result() for f in futures)
            self.assertEqual(revoke_status, 200)
            if pay_status == 201:  # payment won
                self.assertEqual((self.balance(customer=self.alice), LedgerEntry.objects.count()), (460, 2))
            else:  # revocation won
                self.assertEqual(pay_status, 401, attempt)
                self.assertEqual((self.balance(customer=self.alice), LedgerEntry.objects.count()), (500, 0))
            self.assert_consistent()
            self.assertIsNotNone(Terminal.objects.get(pk=self.term_a.pk).revoked_at)


class TerminalLifecycleTests(Base):
    def revoke(self, terminal):
        Terminal.objects.filter(pk=terminal.pk).update(revoked_at=timezone.now())

    def test_admin_cannot_clear_revoked_at(self):
        self.revoke(self.term_a)
        su = User.objects.create_superuser("root", password=PASSWORD)
        model_admin = admin_site_model(Terminal)
        request = type("R", (), {"user": su})()
        self.assertIn("revoked_at", model_admin.get_readonly_fields(request, self.term_a))
        web = login_client("root")
        for body in ({"revoked_at_0": "", "revoked_at_1": ""}, {"revoked_at": ""}, {}):
            web.post(f"/admin/payments/terminal/{self.term_a.pk}/change/", body)
        self.assertIsNotNone(Terminal.objects.get(pk=self.term_a.pk).revoked_at)
        self.assertEqual(self.pay().status_code, 401)  # the old key still does not work
        self.assertFalse(Payment.objects.exists())

    def test_model_save_refuses_to_reactivate(self):
        self.revoke(self.term_a)
        terminal = Terminal.objects.get(pk=self.term_a.pk)
        terminal.revoked_at = None
        with self.assertRaisesMessage(ValueError, "cannot be reactivated"):
            terminal.save()
        self.assertIsNotNone(Terminal.objects.get(pk=self.term_a.pk).revoked_at)

    def test_ordinary_saves_of_a_live_terminal_still_work(self):
        terminal = Terminal.objects.get(pk=self.term_a.pk)
        terminal.name = "Renamed"
        terminal.save()
        self.assertEqual(Terminal.objects.get(pk=terminal.pk).name, "Renamed")

    def test_replace_terminal_issues_a_new_key_and_never_restores_the_old_one(self):
        out = StringIO()
        call_command("replace_terminal", str(self.term_a.pk), stdout=out)
        new_key = out.getvalue().split("shown once): ")[1].split()[0]
        old, new = Terminal.objects.get(pk=self.term_a.pk), Terminal.objects.exclude(pk=self.term_a.pk).get(merchant=self.shop_a)
        self.assertIsNotNone(old.revoked_at)
        self.assertEqual((new.replaces_id, new.revoked_at), (old.pk, None))
        self.assertNotEqual(new.key_hash, old.key_hash)
        self.assertEqual(old.key_hash, hash_terminal_key(KEY_A))  # old credential unchanged
        self.assertEqual(self.pay().status_code, 401)  # old key stays dead
        # Enrollments are not copied: the new terminal pays nobody until a supervisor enrolls.
        fresh = key_client(new_key)
        self.assertEqual(self.pay(client=fresh).status_code, 403)
        enroll(self.alice, new, 1)
        self.assertEqual(self.pay(client=fresh).status_code, 201)
        self.assertEqual(Payment.objects.get().terminal_id, new.pk)

    def test_rerunning_replace_revokes_the_earlier_replacement(self):
        first, second = StringIO(), StringIO()
        call_command("replace_terminal", str(self.term_a.pk), stdout=first)  # key "lost"
        call_command("replace_terminal", str(self.term_a.pk), stdout=second)
        key = lambda out: out.getvalue().split("shown once): ")[1].split()[0]
        live = Terminal.objects.filter(merchant=self.shop_a, revoked_at__isnull=True)
        self.assertEqual(live.count(), 1)
        self.assertEqual(self.pay(client=key_client(key(first))).status_code, 401)
        self.assertEqual(live.get().key_hash, hash_terminal_key(key(second)))

    def test_replace_unknown_terminal_fails(self):
        with self.assertRaises(CommandError):
            call_command("replace_terminal", "99999", stdout=StringIO())


class ReplayAfterRevocationTests(Base):
    """A terminal that lost the reply must learn the stored result, never get charged twice."""

    def setUp(self):
        super().setUp()
        self.pid = uuid4()
        self.first = self.pay(payment_id=self.pid)
        self.assertEqual(self.first.status_code, 201)

    def assert_no_new_money_movement(self):
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(LedgerEntry.objects.count(), 2)
        self.assertEqual((self.balance(customer=self.alice), self.balance(merchant=self.shop_a)), (460, 40))
        call_command("reconcile", stdout=StringIO())

    def test_replay_after_enrollment_revoked_returns_original_result(self):
        Enrollment.objects.filter(pk=self.enr_alice.pk).update(status="REVOKED", revoked_at=timezone.now())
        r = self.pay(payment_id=self.pid)
        self.assertEqual((r.status_code, r.data["replayed"]), (200, True))
        self.assertEqual(r.data["payment"]["payment_id"], str(self.pid))
        self.assertEqual(r.data["payment"]["status"], "SUCCESS")
        self.assert_no_new_money_movement()

    def test_replay_after_deletion_request_returns_original_result(self):
        login_client("u-alice").post(f"/api/customer/enrollments/{self.enr_alice.pk}/deletion-request/")
        self.assertEqual(self.pay(payment_id=self.pid).status_code, 200)
        self.assert_no_new_money_movement()

    def test_new_payment_after_revocation_is_still_refused(self):
        Enrollment.objects.filter(pk=self.enr_alice.pk).update(status="REVOKED", revoked_at=timezone.now())
        r = self.pay()  # new UUID
        self.assertEqual((r.status_code, r.data["error"]["code"]), (403, "enrollment_inactive"))
        self.assert_no_new_money_movement()

    def test_changed_fields_after_revocation_are_rejected_not_replayed(self):
        Enrollment.objects.filter(pk=self.enr_alice.pk).update(status="REVOKED", revoked_at=timezone.now())
        for kwargs in ({"amount": 41}, {"slot": 99}):
            r = self.pay(payment_id=self.pid, **kwargs)
            self.assertEqual(r.status_code, 409, kwargs)
            self.assertNotIn("payment", r.data)
        self.assert_no_new_money_movement()

    def test_revoked_terminal_cannot_replay(self):
        Terminal.objects.filter(pk=self.term_a.pk).update(revoked_at=timezone.now())
        r = self.pay(payment_id=self.pid)
        self.assertEqual(r.status_code, 401)
        self.assertNotIn("payment", r.data)
        self.assert_no_new_money_movement()

    def test_another_terminal_cannot_replay_or_read_the_payment(self):
        other = key_client(KEY_B)
        for slot in (1, 2, 99):  # bob has slot 1 on terminal B; others are unknown there
            r = self.pay(payment_id=self.pid, slot=slot, client=other)
            self.assertEqual(r.status_code, 409, slot)
            self.assertNotIn("payment", r.data)
        self.assertEqual(other.get(f"{TERMINAL_PAY}{self.pid}/").status_code, 404)
        self.assert_no_new_money_movement()

    def test_declined_result_is_replayed_as_declined_after_revocation(self):
        Wallet.objects.filter(customer=self.bob).update(balance=5, opening_balance=5)
        declined_id = uuid4()
        self.assertEqual(self.pay(slot=2, payment_id=declined_id).status_code, 422)
        Enrollment.objects.filter(pk=self.enr_bob.pk).update(status="REVOKED", revoked_at=timezone.now())
        r = self.pay(slot=2, payment_id=declined_id)
        self.assertEqual((r.status_code, r.data["error"]["code"], r.data["replayed"]), (422, "insufficient_funds", True))
        self.assertEqual(LedgerEntry.objects.count(), 2)

    def test_slot_is_part_of_the_stored_identity(self):
        self.assertEqual(Payment.objects.get(pk=self.pid).sensor_slot, 1)
        # Same customer, same terminal, but a different slot with the same UUID is a different request.
        enroll(self.alice, self.term_a, 5)
        self.assertEqual(self.pay(slot=5, payment_id=self.pid).status_code, 409)
        self.assert_no_new_money_movement()

    def test_demo_route_payment_cannot_be_replayed_from_a_terminal(self):
        demo_id = uuid4()
        Payment.objects.create(id=demo_id, payer=self.alice, merchant=self.shop_a, amount=40, status="SUCCESS")
        self.assertEqual(self.pay(payment_id=demo_id).status_code, 409)
