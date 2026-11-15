"""Live terminal display: the device publishes UI states, the website polls them.

Polling, not SSE/WebSocket: the app runs on plain WSGI where each open stream pins a worker, and a
1s poll already recovers by itself after any disconnect. Upgrade only if ASGI is adopted.
"""
import re
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import TerminalKeyAuthentication
from .models import Terminal, TerminalStatus
from .permissions import IsAdmin, IsMerchant

ONLINE_WINDOW = timedelta(seconds=15)  # the device heartbeats every ~5s
FINAL = {"success", "declined", "error"}
DEVICE_SCREENS = ["idle", "amount", "confirm", "finger", "matched", "no_match", "processing", "unconfirmed", "error"]
ERROR_CODES = ["timeout", "no_match", "no_enrollment", "conflict", "server_error", "wifi", "bad_amount"]


def set_status(terminal, screen, **data):
    """Server-side writes use this too, so the final payment result comes from the payment service."""
    data["mock"] = not settings.BIOPAY_TERMINAL_REAL_SENSOR
    with transaction.atomic():
        row, _ = TerminalStatus.objects.select_for_update().get_or_create(
            terminal=terminal, defaults={"screen": screen})
        if (screen == "processing" and row.screen in FINAL
                and timezone.now() - row.updated_at < timedelta(seconds=5)):
            return  # a late "processing" must not overwrite the server's result
        TerminalStatus.objects.filter(pk=row.pk).update(
            screen=screen, data=data, seq=F("seq") + 1, updated_at=timezone.now())


class DeviceStatus(serializers.Serializer):
    screen = serializers.ChoiceField(DEVICE_SCREENS)
    amount = serializers.IntegerField(min_value=0, required=False)
    entry = serializers.RegexField(re.compile(r"^[0-9]{0,6}$"), required=False, allow_blank=True)
    code = serializers.ChoiceField(ERROR_CODES, required=False)


class TerminalStatusPublish(APIView):
    """Terminal key auth, same as payments. Also the heartbeat: the device re-posts every ~5s."""

    authentication_classes = [TerminalKeyAuthentication]

    def post(self, request):
        s = DeviceStatus(data=request.data)
        s.is_valid(raise_exception=True)
        v = dict(s.validated_data)
        set_status(request.user.terminal, v.pop("screen"), **v)
        return Response({"ok": True})


class LiveTerminals(APIView):
    """A merchant sees only its own terminals; an admin sees all. Offline terminals show no screen."""

    permission_classes = [IsMerchant | IsAdmin]

    def get(self, request):
        qs = Terminal.objects.filter(revoked_at__isnull=True).select_related("merchant", "status").order_by("pk")
        if not request.user.is_staff:
            qs = qs.filter(merchant=request.user.merchant)
        now, out = timezone.now(), []
        for t in qs:
            st = getattr(t, "status", None)
            online = st is not None and now - st.updated_at < ONLINE_WINDOW
            out.append({
                "id": t.pk, "name": t.name, "merchant": t.merchant.name, "online": online,
                "screen": st.screen if online else None, "data": st.data if online else {},
                "seq": st.seq if st else 0, "last_seen": t.last_seen,
            })
        return Response({"terminals": out})
