from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.core.management import call_command
from django.db import DatabaseError, IntegrityError, connection, connections, transaction
from django.db.models import Sum
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient

from payments.constants import DEMO_CUSTOMER_CODE, DEMO_MERCHANT_CODE, SIMULATION_WARNING
from payments.models import Customer, LedgerEntry, Merchant, Payment, Wallet
from payments.services import pay_demo


# Public, test-only token. Never use this for a running development server.
TEST_TOKEN = "test-only-mock-token-for-automated-tests"
DEMO_SETTINGS = {
    "DEBUG": True,
    "BIOPAY_ENABLE_DEMO_API": True,
    "BIOPAY_DEMO_TOKEN": TEST_TOKEN,
    "BIOPAY_MAX_PAYMENT": 100,
    "ALLOWED_HOSTS": ["testserver"],
}
PAYMENT_URL = "/api/dev/mock/payments/"
WALLET_URL = "/api/dev/mock/wallets/"
HISTORY_URL = "/api/dev/mock/history/"


def seed_demo():
    call_command("seed_demo", stdout=StringIO())


def mock_client():
    client = APIClient()
    client.credentials(HTTP_X_BIOPAY_DEMO_TOKEN=TEST_TOKEN)
    return client


@override_settings(**DEMO_SETTINGS)
class PaymentAPITests(TransactionTestCase):
    def setUp(self):
        seed_demo()
        self.client = mock_client()
        self.customer = Customer.objects.get(code=DEMO_CUSTOMER_CODE)
        self.merchant = Merchant.objects.get(code=DEMO_MERCHANT_CODE)

    def pay(self, amount=40, payment_id=None, **extra):
        return self.client.post(
            PAYMENT_URL,
            {"payment_id": str(payment_id or uuid4()), "amount": amount, **extra},
            format="json",
        )

    def assert_balances(self, customer=500, merchant=0):
        self.assertEqual(Wallet.objects.get(customer=self.customer).balance, customer)
        self.assertEqual(Wallet.objects.get(merchant=self.merchant).balance, merchant)
        for wallet in Wallet.objects.annotate(net=Sum("entries__delta")):
            self.assertEqual(wallet.balance, wallet.opening_balance + (wallet.net or 0))

    def test_successful_transfer_and_balanced_ledger(self):
        response = self.pay()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["warning"], SIMULATION_WARNING)
        self.assertIn("NO BIOMETRIC VERIFICATION", response.data["authentication"])
        self.assertFalse(response.data["replayed"])
        self.assertEqual(response.data["payment"]["status"], Payment.Status.SUCCESS)
        self.assert_balances(460, 40)
        self.assertCountEqual(LedgerEntry.objects.values_list("delta", flat=True), [-40, 40])
        self.assertEqual(LedgerEntry.objects.aggregate(total=Sum("delta"))["total"], 0)
        self.assertEqual(Payment.objects.count(), 1)

    def test_insufficient_funds_is_final_and_repeatable(self):
        for _ in range(5):
            self.assertEqual(self.pay(100).status_code, 201)
        payment_id = uuid4()
        for replayed in (False, True):
            response = self.pay(40, payment_id)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.data["error"]["code"], "insufficient_funds")
            self.assertEqual(response.data["payment"]["status"], Payment.Status.DECLINED)
            self.assertEqual(response.data["replayed"], replayed)
        self.assertEqual(Payment.objects.count(), 6)
        self.assertEqual(LedgerEntry.objects.count(), 10)
        self.assertFalse(Payment.objects.get(pk=payment_id).entries.exists())
        self.assert_balances(0, 500)

    def test_invalid_amounts_do_not_write(self):
        for amount in (0, -1, 1.5, 40.0, "40", "1.5", True, False, None, [], {}, 101, 2**63):
            with self.subTest(amount=amount):
                response = self.pay(amount)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["error"]["code"], "invalid_request")
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(LedgerEntry.objects.exists())
        self.assert_balances()

    def test_missing_and_invalid_payment_fields(self):
        for payload in (
            {}, {"amount": 40}, {"payment_id": str(uuid4())},
            {"payment_id": "not-a-uuid", "amount": 40},
            {"payment_id": None, "amount": 40}, [],
        ):
            with self.subTest(payload=payload):
                response = self.client.post(PAYMENT_URL, payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["error"]["code"], "invalid_request")
        self.assertFalse(Payment.objects.exists())

    def test_account_selection_and_unknown_fields_are_rejected(self):
        for field in ("customer_id", "payer_id", "merchant_id", "balance", "fingerprint_verified"):
            with self.subTest(field=field):
                self.assertEqual(self.pay(**{field: 123}).status_code, 400)
        self.assertFalse(Payment.objects.exists())

    def test_payment_id_must_be_a_uuid_string(self):
        for payment_id in (1, True, False, 1.5, [], {}):
            with self.subTest(payment_id=payment_id):
                response = self.client.post(
                    PAYMENT_URL, {"payment_id": payment_id, "amount": 40}, format="json"
                )
                self.assertEqual(response.status_code, 400)
        self.assertFalse(Payment.objects.exists())

    def test_duplicate_request_does_not_transfer_again(self):
        payment_id = uuid4()
        first = self.pay(payment_id=payment_id)
        # Equivalent UUID text is canonicalized before comparing requests.
        repeated = self.pay(payment_id=str(payment_id).upper())
        self.assertEqual(first.status_code, 201)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(first.data["payment"], repeated.data["payment"])
        self.assertTrue(repeated.data["replayed"])
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(LedgerEntry.objects.count(), 2)
        self.assert_balances(460, 40)

    def test_same_uuid_changed_amount_conflicts(self):
        payment_id = uuid4()
        self.pay(payment_id=payment_id)
        response = self.pay(amount=41, payment_id=payment_id)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "payment_conflict")
        self.assertEqual(Payment.objects.count(), 1)
        self.assert_balances(460, 40)

    def test_failure_after_ledger_and_debit_rolls_back_everything(self):
        original_save = Wallet.save

        def fail_on_credit(wallet, *args, **kwargs):
            if wallet.merchant_id:
                # Debit and ledger writes have already happened inside the transaction.
                self.assertEqual(Wallet.objects.get(customer=self.customer).balance, 460)
                self.assertEqual(LedgerEntry.objects.count(), 2)
                raise DatabaseError("injected credit failure")
            return original_save(wallet, *args, **kwargs)

        payment_id = uuid4()
        with patch.object(Wallet, "save", autospec=True, side_effect=fail_on_credit):
            with self.assertRaisesMessage(DatabaseError, "injected credit failure"):
                self.pay(payment_id=payment_id)
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(LedgerEntry.objects.exists())
        self.assert_balances()
        self.assertEqual(self.pay(payment_id=payment_id).status_code, 201)
        self.assert_balances(460, 40)

    def test_commit_failure_never_returns_success(self):
        with patch.object(connection, "_commit", side_effect=DatabaseError("injected commit failure")):
            with self.assertRaisesMessage(DatabaseError, "injected commit failure"):
                self.pay()
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(LedgerEntry.objects.exists())
        self.assert_balances()

    def test_seed_is_repeatable_even_after_spending(self):
        self.pay()
        seed_demo()
        seed_demo()
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Merchant.objects.count(), 1)
        self.assertEqual(Wallet.objects.count(), 2)
        self.assertEqual(Payment.objects.count(), 1)
        self.assert_balances(460, 40)

    def test_wallet_status_and_history(self):
        payment_id = uuid4()
        self.pay(payment_id=payment_id)
        wallets = self.client.get(WALLET_URL)
        self.assertEqual(wallets.status_code, 200)
        self.assertEqual(wallets.data["customer"]["balance"], 460)
        self.assertEqual(wallets.data["merchant"]["balance"], 40)
        detail = self.client.get(f"{PAYMENT_URL}{payment_id}/")
        self.assertEqual(detail.status_code, 200)
        history = self.client.get(HISTORY_URL)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.data["count"], 1)
        self.assertEqual(history.data["results"], [detail.data["payment"]])

    def test_history_is_paginated_and_scoped_to_demo(self):
        other_customer = Customer.objects.create(code="other", name="Other")
        Payment.objects.create(
            id=uuid4(), payer=other_customer, merchant=self.merchant,
            amount=40, status=Payment.Status.DECLINED, decline_reason="insufficient_funds",
        )
        for _ in range(21):
            self.pay(amount=1)
        history = self.client.get(HISTORY_URL)
        self.assertEqual(history.data["count"], 21)
        self.assertEqual(len(history.data["results"]), 20)
        self.assertIsNotNone(history.data["next"])
        page_two = self.client.get(HISTORY_URL, {"page": 2})
        self.assertEqual(len(page_two.data["results"]), 1)
        other_payment = Payment.objects.get(payer=other_customer)
        self.assertEqual(self.client.get(f"{PAYMENT_URL}{other_payment.pk}/").status_code, 404)

    def test_missing_and_invalid_status_ids(self):
        missing = self.client.get(f"{PAYMENT_URL}{uuid4()}/")
        invalid = self.client.get(f"{PAYMENT_URL}invalid/")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.data["error"]["code"], "not_found")
        self.assertEqual(invalid.status_code, 400)

    def test_missing_setup_returns_503_without_payment(self):
        Wallet.objects.all().delete()
        for url in (PAYMENT_URL, WALLET_URL):
            response = self.pay() if url == PAYMENT_URL else self.client.get(url)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.data["error"]["code"], "demo_not_ready")
        self.assertFalse(Payment.objects.exists())
        Customer.objects.all().delete()
        self.assertEqual(self.pay().status_code, 503)

    def test_mock_token_required_on_every_endpoint(self):
        for token in (None, "wrong-token", "é" * 32):
            client = APIClient()
            if token:
                client.credentials(HTTP_X_BIOPAY_DEMO_TOKEN=token)
            for url in (PAYMENT_URL, WALLET_URL, HISTORY_URL, f"{PAYMENT_URL}{uuid4()}/"):
                with self.subTest(token=token, url=url):
                    response = client.post(url, {}, format="json") if url == PAYMENT_URL else client.get(url)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.data["error"]["code"], "authentication_failed")

    def test_api_disabled_without_opt_in_or_with_debug_off(self):
        for settings in (
            {"BIOPAY_ENABLE_DEMO_API": False}, {"DEBUG": False},
        ):
            with self.subTest(settings=settings), override_settings(**settings):
                self.assertEqual(self.pay().status_code, 404)
                self.assertEqual(self.client.get(WALLET_URL).status_code, 404)
                self.assertEqual(self.client.get(HISTORY_URL).status_code, 404)
        self.assertFalse(Payment.objects.exists())

    def test_empty_token_fails_closed(self):
        with override_settings(BIOPAY_DEMO_TOKEN=""):
            client = APIClient()
            self.assertEqual(client.get(WALLET_URL).status_code, 401)

    def test_balance_editing_and_funding_endpoints_do_not_exist(self):
        self.assertEqual(self.client.patch(WALLET_URL, {"balance": 999}, format="json").status_code, 405)
        self.assertEqual(self.client.post("/api/dev/mock/fund/", {}, format="json").status_code, 404)
        self.assert_balances()

    def test_malformed_json_has_stable_error(self):
        response = self.client.post(PAYMENT_URL, '{"amount":', content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "parse_error")

    def test_database_constraints_reject_negative_balances_and_invalid_owners(self):
        customer_wallet = Wallet.objects.get(customer=self.customer)
        for change in ({"balance": -1}, {"customer": None}, {"merchant": self.merchant}):
            with self.subTest(change=change), self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Wallet.objects.filter(pk=customer_wallet.pk).update(**change)
        self.assert_balances()

    def test_service_rejects_invalid_amounts_even_without_serializer(self):
        for amount in (True, 40.0, -1, 101):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                pay_demo(payment_id=uuid4(), amount=amount)
        self.assertFalse(Payment.objects.exists())


@override_settings(**DEMO_SETTINGS)
class PaymentConcurrencyTests(TransactionTestCase):
    def setUp(self):
        # Fail, never silently skip or substitute SQLite, if the engine changes.
        self.assertEqual(connection.vendor, "postgresql")
        seed_demo()

    def concurrent_payments(self, payloads):
        rendezvous = Barrier(2)
        original_get_or_create = Payment.objects.get_or_create

        def synchronized_insert(*args, **kwargs):
            # Both requests have entered their DB transactions before either inserts.
            rendezvous.wait(timeout=10)
            return original_get_or_create(*args, **kwargs)

        def worker(payload):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '10s'")
                    cursor.execute("SET statement_timeout = '15s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    backend_pid = cursor.fetchone()[0]
                response = mock_client().post(PAYMENT_URL, payload, format="json")
                return response.status_code, response.data, backend_pid
            finally:
                connections.close_all()

        with patch.object(Payment.objects, "get_or_create", side_effect=synchronized_insert):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(worker, payloads))
        self.assertEqual(len({result[2] for result in results}), 2)
        return results

    def test_same_uuid_concurrently_transfers_once(self):
        payload = {"payment_id": str(uuid4()), "amount": 40}
        results = self.concurrent_payments([payload, payload])
        self.assertCountEqual([result[0] for result in results], [201, 200])
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(LedgerEntry.objects.count(), 2)
        self.assertEqual(Wallet.objects.get(customer__isnull=False).balance, 460)
        self.assertEqual(Wallet.objects.get(merchant__isnull=False).balance, 40)

    def test_same_uuid_different_amounts_concurrently_conflict(self):
        payment_id = str(uuid4())
        results = self.concurrent_payments([
            {"payment_id": payment_id, "amount": 40},
            {"payment_id": payment_id, "amount": 41},
        ])
        self.assertCountEqual([result[0] for result in results], [201, 409])
        payment = Payment.objects.get()
        self.assertEqual(Wallet.objects.get(customer__isnull=False).balance, 500 - payment.amount)
        self.assertEqual(Wallet.objects.get(merchant__isnull=False).balance, payment.amount)
        self.assertEqual(LedgerEntry.objects.count(), 2)

    @override_settings(BIOPAY_MAX_PAYMENT=500)
    def test_different_uuids_cannot_overdraw(self):
        results = self.concurrent_payments([
            {"payment_id": str(uuid4()), "amount": 400},
            {"payment_id": str(uuid4()), "amount": 400},
        ])
        self.assertCountEqual([result[0] for result in results], [201, 422])
        self.assertCountEqual(Payment.objects.values_list("status", flat=True), ["SUCCESS", "DECLINED"])
        self.assertEqual(LedgerEntry.objects.count(), 2)
        self.assertEqual(LedgerEntry.objects.aggregate(total=Sum("delta"))["total"], 0)
        self.assertEqual(Wallet.objects.get(customer__isnull=False).balance, 100)
        self.assertEqual(Wallet.objects.get(merchant__isnull=False).balance, 400)
