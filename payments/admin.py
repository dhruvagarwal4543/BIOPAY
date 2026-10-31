from django.contrib import admin

from .models import Customer, Enrollment, LedgerEntry, Merchant, Payment, Terminal, Wallet


class ReadOnly(admin.ModelAdmin):
    """Money tables are written only by the transfer service, never by hand."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Wallet)
class WalletAdmin(ReadOnly):
    list_display = ["id", "customer", "merchant", "opening_balance", "balance"]


@admin.register(Payment)
class PaymentAdmin(ReadOnly):
    list_display = ["id", "payer", "merchant", "amount", "status", "auth_method", "created_at"]


@admin.register(LedgerEntry)
class LedgerEntryAdmin(ReadOnly):
    list_display = ["id", "payment", "wallet", "delta"]


@admin.register(Customer, Merchant)
class AccountAdmin(ReadOnly):
    list_display = ["code", "name", "user"]


@admin.register(Terminal)
class TerminalAdmin(admin.ModelAdmin):
    list_display = ["name", "merchant", "revoked_at", "last_seen", "replaces"]
    # Revocation is one-way: no field here can reactivate a terminal.
    readonly_fields = ["merchant", "name", "last_seen", "revoked_at", "replaces"]

    def has_add_permission(self, request):
        return False  # keys are issued by the create_terminal command, shown once

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ["customer", "terminal", "sensor_slot", "status", "source", "consented_at"]

    def get_readonly_fields(self, request, obj=None):
        # After creation only status may change, so a slot can never be re-pointed to another
        # person and the consent record stays as given. Revoke instead of editing identity.
        if obj is None:
            return ["source"]
        return ["source", "customer", "terminal", "sensor_slot", "consented_at"]

    def has_delete_permission(self, request, obj=None):
        return False  # revoke instead, so the consent trail remains
