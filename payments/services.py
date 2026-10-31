from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce

from .api_errors import DemoNotReady, EnrollmentInactive, PaymentConflict, TerminalRevoked
from .constants import DEMO_CUSTOMER_CODE, DEMO_MERCHANT_CODE
from .models import Customer, Enrollment, LedgerEntry, Merchant, Payment, Terminal, Wallet


def _check_amount(amount):
    if type(amount) is not int or not 1 <= amount <= settings.BIOPAY_MAX_PAYMENT:
        raise ValueError("Amount must be a positive integer within the development limit.")


def _transfer(*, payment_id, customer, merchant, amount, terminal=None, sensor_slot=None):
    """Must run inside the caller's durable transaction."""
    # get_or_create uses the UUID uniqueness constraint to resolve racing inserts.
    payment, created = Payment.objects.get_or_create(
        id=payment_id,
        defaults={
            "payer": customer,
            "merchant": merchant,
            "amount": amount,
            "terminal": terminal,
            "sensor_slot": sensor_slot,
            "status": Payment.Status.DECLINED,
            "decline_reason": "insufficient_funds",
        },
    )
    if not created:
        # The whole canonical request must match, including which terminal and sensor slot.
        if (payment.payer_id, payment.merchant_id, payment.amount, payment.terminal_id,
                payment.sensor_slot) != (
            customer.pk, merchant.pk, amount, terminal.pk if terminal else None, sensor_slot
        ):
            raise PaymentConflict
        return payment, False

    wallets = list(
        Wallet.objects.select_for_update()
        .filter(Q(customer=customer) | Q(merchant=merchant))
        .order_by("pk")
    )
    if len(wallets) != 2:
        raise DemoNotReady
    payer_wallet = next(wallet for wallet in wallets if wallet.customer_id == customer.pk)
    merchant_wallet = next(wallet for wallet in wallets if wallet.merchant_id == merchant.pk)
    if payer_wallet.balance < amount:
        return payment, True

    LedgerEntry.objects.bulk_create([
        LedgerEntry(payment=payment, wallet=payer_wallet, delta=-amount),
        LedgerEntry(payment=payment, wallet=merchant_wallet, delta=amount),
    ])
    payer_wallet.balance -= amount
    merchant_wallet.balance += amount
    payer_wallet.save(update_fields=["balance"])
    merchant_wallet.save(update_fields=["balance"])
    payment.status = Payment.Status.SUCCESS
    payment.decline_reason = ""
    payment.save(update_fields=["status", "decline_reason"])
    return payment, True


@transaction.atomic(durable=True)
def pay_demo(*, payment_id, amount):
    """Transfer only between the fixed demo accounts; return after commit."""
    _check_amount(amount)
    try:
        customer = Customer.objects.get(code=DEMO_CUSTOMER_CODE)
        merchant = Merchant.objects.get(code=DEMO_MERCHANT_CODE)
    except (Customer.DoesNotExist, Merchant.DoesNotExist):
        raise DemoNotReady from None
    return _transfer(payment_id=payment_id, customer=customer, merchant=merchant, amount=amount)


@transaction.atomic(durable=True)
def pay_at_terminal(*, terminal, sensor_slot, payment_id, amount):
    """Payer and merchant come from server records: the slot's enrollment and the terminal."""
    _check_amount(amount)
    # Lock order is fixed everywhere: terminal -> enrollment -> payment row -> wallets (by pk).
    # Revoking a terminal updates this same row, so a revoke either commits before this lock
    # (we see revoked_at and refuse) or waits until this payment commits. The key check in
    # TerminalKeyAuthentication runs before the transaction and cannot guarantee that alone.
    terminal = Terminal.objects.select_for_update(of=("self",)).select_related("merchant").get(pk=terminal.pk)
    if terminal.revoked_at is not None:
        raise TerminalRevoked
    # Locking the enrollment makes a concurrent revoke/deletion request wait or win cleanly.
    enrollment = (
        Enrollment.objects.select_for_update()
        .select_related("customer")
        .filter(terminal=terminal, sensor_slot=sensor_slot, status=Enrollment.Status.ACTIVE)
        .first()
    )
    if enrollment is None:
        # The slot may have been revoked after this exact request already ran. Return that stored
        # result so a terminal that lost the reply learns the truth. Nothing is written, and only
        # this unrevoked terminal's own payment with the same amount and slot qualifies.
        existing = Payment.objects.filter(pk=payment_id).first()
        if existing is None:
            raise EnrollmentInactive
        if (existing.terminal_id, existing.amount, existing.sensor_slot) != (terminal.pk, amount, sensor_slot):
            raise PaymentConflict
        return existing, False
    return _transfer(
        payment_id=payment_id, customer=enrollment.customer, merchant=terminal.merchant,
        amount=amount, terminal=terminal, sensor_slot=sensor_slot,
    )


def reconcile():
    """Invariants, each read in one SQL statement so concurrent payments cannot fake a mismatch.

    wallet: opening_balance + sum(its ledger deltas) == balance
    payment: SUCCESS has two entries summing to zero; DECLINED has none.
    Returns a list of problem strings; empty means consistent.
    """
    problems = []
    wallets = Wallet.objects.annotate(net=Coalesce(Sum("entries__delta"), 0))
    for w in wallets:
        if w.opening_balance + w.net != w.balance:
            problems.append(f"wallet {w.pk}: opening {w.opening_balance} + ledger {w.net} != balance {w.balance}")
    payments = Payment.objects.annotate(
        n=Count("entries"), net=Coalesce(Sum("entries__delta"), 0)
    )
    for p in payments:
        ok = (p.n == 2 and p.net == 0) if p.status == Payment.Status.SUCCESS else p.n == 0
        if not ok:
            problems.append(f"payment {p.pk}: {p.status} has {p.n} entries summing to {p.net}")
    return problems
