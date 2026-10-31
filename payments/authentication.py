import hashlib
from secrets import compare_digest

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed, NotFound

from .models import Terminal


class MockPrincipal:
    is_authenticated = True


class MockDemoAuthentication(BaseAuthentication):
    """Development access token only. This never verifies a fingerprint."""

    # shortcut: one shared token gates fixed demo accounts; replace before a user/device pilot.

    def authenticate(self, request):
        if not settings.DEBUG or not settings.BIOPAY_ENABLE_DEMO_API:
            raise NotFound("Development API is disabled.")
        expected = settings.BIOPAY_DEMO_TOKEN
        supplied = request.headers.get("X-BioPay-Demo-Token", "")
        if len(expected) < 32 or not compare_digest(supplied.encode(), expected.encode()):
            raise AuthenticationFailed("A valid development demo token is required.")
        return MockPrincipal(), None

    def authenticate_header(self, request):
        return "BioPayDemo"


class TerminalPrincipal:
    is_authenticated = True

    def __init__(self, terminal):
        self.terminal = terminal


class TerminalKeyAuthentication(BaseAuthentication):
    """Device credential, separate from web login. Gated like the mock fingerprint it serves."""

    def authenticate(self, request):
        if not settings.DEBUG or not settings.BIOPAY_ENABLE_DEMO_API:
            raise NotFound("Mock terminal API is disabled.")
        key = request.headers.get("X-BioPay-Terminal-Key", "")
        terminal = (
            Terminal.objects.select_related("merchant")
            .filter(key_hash=hash_terminal_key(key)).first() if key else None
        )
        if terminal is None or terminal.revoked_at is not None:
            raise AuthenticationFailed("A valid, unrevoked terminal key is required.")
        Terminal.objects.filter(pk=terminal.pk).update(last_seen=timezone.now())
        return TerminalPrincipal(terminal), None

    def authenticate_header(self, request):
        return "BioPayTerminal"


def hash_terminal_key(key):
    return hashlib.sha256(key.encode()).hexdigest()


class WebSessionAuthentication(SessionAuthentication):
    """Session login that answers 401 when there is no valid session.

    Stock SessionAuthentication answers 403 for that case, which the browser cannot tell
    apart from a signed-in user who lacks permission. Now 401 = sign in again, 403 = not allowed.
    """

    def authenticate_header(self, request):
        return "Session"
