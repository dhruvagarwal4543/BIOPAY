from secrets import token_urlsafe

from django.core.management.base import BaseCommand, CommandError

from payments.authentication import hash_terminal_key
from payments.models import Merchant, Terminal


class Command(BaseCommand):
    help = "Issue a terminal key for a merchant. The key is printed once and only its hash is stored."

    def add_arguments(self, parser):
        parser.add_argument("merchant_code")
        parser.add_argument("name")

    def handle(self, *args, merchant_code, name, **options):
        try:
            merchant = Merchant.objects.get(code=merchant_code)
        except Merchant.DoesNotExist:
            raise CommandError("Unknown merchant code.") from None
        key = token_urlsafe(32)
        Terminal.objects.create(merchant=merchant, name=name, key_hash=hash_terminal_key(key))
        self.stdout.write(f"Terminal key (shown once): {key}")
