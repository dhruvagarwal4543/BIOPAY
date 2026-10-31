from django.core.management.base import BaseCommand
from django.db import transaction

from payments.constants import (
    DEMO_CUSTOMER_CODE, DEMO_MERCHANT_CODE, DEMO_OPENING_BALANCE, SIMULATION_WARNING,
)
from payments.models import Customer, Merchant, Wallet


class Command(BaseCommand):
    help = "Create fixed demo accounts and their one-time opening balances."

    @transaction.atomic
    def handle(self, *args, **options):
        customer, _ = Customer.objects.get_or_create(
            code=DEMO_CUSTOMER_CODE, defaults={"name": "Demo Customer"}
        )
        merchant, _ = Merchant.objects.get_or_create(
            code=DEMO_MERCHANT_CODE, defaults={"name": "Demo Merchant"}
        )
        Wallet.objects.get_or_create(
            customer=customer,
            defaults={"opening_balance": DEMO_OPENING_BALANCE, "balance": DEMO_OPENING_BALANCE},
        )
        Wallet.objects.get_or_create(merchant=merchant)
        self.stdout.write(f"{SIMULATION_WARNING}\nDemo accounts ready; existing balances unchanged.")
