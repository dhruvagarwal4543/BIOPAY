from django.core.management.base import BaseCommand, CommandError

from payments.services import reconcile


class Command(BaseCommand):
    help = "Check wallet balances against the ledger. Exits non-zero on any mismatch."

    def handle(self, *args, **options):
        problems = reconcile()
        if problems:
            raise CommandError("Reconciliation FAILED:\n" + "\n".join(problems))
        self.stdout.write("Reconciliation OK: every wallet and payment matches the ledger.")
