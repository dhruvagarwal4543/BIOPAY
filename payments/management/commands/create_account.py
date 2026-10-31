import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from payments.models import Customer, Merchant, Wallet


class Command(BaseCommand):
    help = (
        "Create a customer or merchant login and wallet (opening balance 0; no funding path exists). "
        "Password comes from BIOPAY_NEW_PASSWORD (min 12 chars)."
    )

    def add_arguments(self, parser):
        parser.add_argument("role", choices=["customer", "merchant"])
        parser.add_argument("code")
        parser.add_argument("name")

    @transaction.atomic
    def handle(self, *args, role, code, name, **options):
        password = os.environ.get("BIOPAY_NEW_PASSWORD", "")
        if len(password) < 12:
            raise CommandError("Set BIOPAY_NEW_PASSWORD to at least 12 characters.")
        model = Customer if role == "customer" else Merchant
        if model.objects.filter(code=code).exists():
            raise CommandError("That code already exists.")
        user = get_user_model().objects.create_user(code, password=password)
        account = model.objects.create(code=code, name=name, user=user)
        Wallet.objects.create(**{role: account})
        self.stdout.write(f"Created {role} '{code}' with a 0-BioCoin wallet. Login username: {code}")
