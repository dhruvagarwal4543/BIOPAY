from django.conf import settings
from django.db import models
from django.db.models import Q


class Customer(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    # The web login for this customer; the role comes from this link, never from the browser.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT
    )

    def __str__(self):
        return self.name


class Merchant(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT
    )

    def __str__(self):
        return self.name


class Wallet(models.Model):
    customer = models.OneToOneField(Customer, null=True, blank=True, on_delete=models.PROTECT)
    merchant = models.OneToOneField(Merchant, null=True, blank=True, on_delete=models.PROTECT)
    # Opening funds are seed data, not a transfer; preserve them for reconciliation.
    opening_balance = models.BigIntegerField(default=0)
    balance = models.BigIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(customer__isnull=False, merchant__isnull=True)
                    | Q(customer__isnull=True, merchant__isnull=False)
                ),
                name="wallet_exactly_one_owner",
            ),
            models.CheckConstraint(condition=Q(balance__gte=0), name="wallet_nonnegative_balance"),
            models.CheckConstraint(
                condition=Q(opening_balance__gte=0), name="wallet_nonnegative_opening_balance"
            ),
        ]


class Terminal(models.Model):
    """A merchant's checkout device. Authenticates with its own key, never a web login."""

    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="terminals")
    name = models.CharField(max_length=100)
    # SHA-256 of a high-entropy random key; the key itself is shown once at creation.
    key_hash = models.CharField(max_length=64, unique=True, editable=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True, editable=False)
    # Audit trail: a replacement terminal points at the revoked one it replaces.
    replaces = models.ForeignKey(
        "self", null=True, blank=True, editable=False, on_delete=models.PROTECT,
        related_name="replacements",
    )

    def __str__(self):
        return f"{self.name} ({self.merchant.code})"

    def save(self, *args, **kwargs):
        # Revocation is one-way. A new key comes from `replace_terminal`, never from clearing this.
        if (self.pk and self.revoked_at is None
                and Terminal.objects.filter(pk=self.pk, revoked_at__isnull=False).exists()):
            raise ValueError("A revoked terminal cannot be reactivated. Use replace_terminal.")
        super().save(*args, **kwargs)


class Enrollment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        DELETION_REQUESTED = "DELETION_REQUESTED"
        REVOKED = "REVOKED"

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="enrollments")
    terminal = models.ForeignKey(Terminal, on_delete=models.PROTECT, related_name="enrollments")
    # The sensor's own template slot; the template itself never reaches this server.
    sensor_slot = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    consented_at = models.DateTimeField()
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    # Software development only. Becomes a real sensor type when hardware is integrated.
    source = models.CharField(max_length=16, default="MOCK", editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["terminal", "sensor_slot"],
                condition=~Q(status="REVOKED"),
                name="enrollment_one_live_per_slot",
            ),
        ]


class Payment(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "SUCCESS"
        DECLINED = "DECLINED"

    # The caller's UUID is both the payment identity and the idempotency key.
    id = models.UUIDField(primary_key=True, editable=False)
    payer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT)
    amount = models.BigIntegerField()
    status = models.CharField(max_length=8, choices=Status.choices)
    decline_reason = models.CharField(max_length=32, blank=True, default="")
    terminal = models.ForeignKey(Terminal, null=True, on_delete=models.PROTECT)
    # Part of the request's identity for idempotency; null for the shared-token demo route.
    sensor_slot = models.PositiveIntegerField(null=True, editable=False)
    # MOCK = development simulation, not a physical fingerprint match.
    auth_method = models.CharField(max_length=16, default="MOCK", editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_positive_amount"),
            models.CheckConstraint(
                condition=(
                    Q(status="SUCCESS", decline_reason="")
                    | Q(status="DECLINED", decline_reason="insufficient_funds")
                ),
                name="payment_final_result",
            ),
        ]


class LedgerEntry(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="entries")
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="entries")
    delta = models.BigIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(delta=0), name="ledger_nonzero_delta"),
            models.UniqueConstraint(fields=["payment", "wallet"], name="ledger_once_per_wallet"),
        ]


class AuditEvent(models.Model):
    """Append-only operational log. shortcut: immutability is by convention (no update/delete
    endpoint), not a DB trigger; add one before real use."""

    actor = models.CharField(max_length=150)
    action = models.CharField(max_length=40)
    detail = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def log(cls, actor, action, detail=""):
        cls.objects.create(actor=str(actor), action=action, detail=detail)
