from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler as drf_exception_handler


class PaymentConflict(APIException):
    status_code = 409
    default_code = "payment_conflict"
    default_detail = "This payment UUID is already bound to a different request."


class DemoNotReady(APIException):
    status_code = 503
    default_code = "demo_not_ready"
    default_detail = "Demo accounts are not ready. Run seed_demo first."


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, ValidationError):
        error = {
            "code": "invalid_request",
            "message": "Check the request fields.",
            "fields": response.data,
        }
    else:
        error = {
            "code": exc.get_codes() if isinstance(exc.get_codes(), str) else exc.default_code,
            "message": str(response.data.get("detail", "Request failed.")),
        }
    response.data = {"error": error}
    return response


class TerminalRevoked(APIException):
    status_code = 401
    default_code = "terminal_revoked"
    default_detail = "This terminal has been revoked."


class EnrollmentInactive(APIException):
    status_code = 403
    default_code = "enrollment_inactive"
    default_detail = "No active enrollment for this fingerprint slot."
