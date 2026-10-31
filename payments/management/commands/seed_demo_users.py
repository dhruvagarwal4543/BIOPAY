import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from payments.constants import DEMO_CUSTOMER_CODE, DEMO_MERCHANT_CODE
from payments.models import Customer, Enrollment, Merchant, Terminal

USERS = {
    "demo-customer": "customer",
    "demo-merchant": "merchant",
    "demo-admin": "admin",
}


class Command(BaseCommand):
    help = (
        "Create demo logins, one terminal and one MOCK enrollment. "
        "Password is read from BIOPAY_DEMO_PASSWORD (min 12 chars); it is never printed."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get("BIOPAY_DEMO_PASSWORD", "")
        if len(password) < 12:
            raise CommandError("Set BIOPAY_DEMO_PASSWORD to at least 12 characters.")
        call_command("seed_demo", stdout=self.stdout)
        User = get_user_model()
        for username, role in USERS.items():
            user, created = User.objects.get_or_create(username=username)
            if created:  # an existing password is never overwritten
                user.set_password(password)
                user.is_staff = user.is_superuser = role == "admin"
                user.save()
        Customer.objects.filter(code=DEMO_CUSTOMER_CODE).update(user=User.objects.get(username="demo-customer"))
        Merchant.objects.filter(code=DEMO_MERCHANT_CODE).update(user=User.objects.get(username="demo-merchant"))
        merchant = Merchant.objects.get(code=DEMO_MERCHANT_CODE)
        if not merchant.terminals.exists():
            call_command("create_terminal", merchant.code, "Demo terminal", stdout=self.stdout)
        terminal = merchant.terminals.first()
        Enrollment.objects.get_or_create(
            terminal=terminal, sensor_slot=1, status=Enrollment.Status.ACTIVE,
            defaults={"customer": Customer.objects.get(code=DEMO_CUSTOMER_CODE),
                      "consented_at": timezone.now()},
        )
        self.stdout.write("Demo logins ready. MOCK enrollment: terminal slot 1 (development simulation).")
