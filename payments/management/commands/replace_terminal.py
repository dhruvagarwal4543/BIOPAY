from secrets import token_urlsafe

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from payments.authentication import hash_terminal_key
from payments.models import Terminal


class Command(BaseCommand):
    help = (
        "Revoke a terminal and issue a NEW terminal (new key) that records which one it replaces. "
        "The old key is never restored. Enrollments belong to the old terminal and are not copied: "
        "re-enroll customers on the new one under supervision."
    )

    def add_arguments(self, parser):
        parser.add_argument("terminal_id", type=int)

    @transaction.atomic
    def handle(self, *args, terminal_id, **options):
        try:
            old = Terminal.objects.select_for_update().get(pk=terminal_id)
        except Terminal.DoesNotExist:
            raise CommandError("Unknown terminal id.") from None
        if old.revoked_at is None:
            old.revoked_at = timezone.now()
            old.save(update_fields=["revoked_at"])
        # Re-running (e.g. the one-time key was lost) must not leave an earlier replacement live.
        old.replacements.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
        key = token_urlsafe(32)
        new = Terminal.objects.create(
            merchant=old.merchant, name=f"{old.name} (replacement)",
            key_hash=hash_terminal_key(key), replaces=old,
        )
        self.stdout.write(f"Terminal {old.pk} revoked. New terminal id {new.pk}. Key (shown once): {key}")
