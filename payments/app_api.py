"""Self-service registration/enrollment, payment detail, audit log and the dev-only simulator."""
import re

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .api_errors import TerminalRevoked
from .dashboard import enrollment_row, me_payload, paged, payments_qs
from .models import AuditEvent, Customer, Enrollment, Terminal, Wallet
from .permissions import IsAdmin, IsCustomer, IsMerchant
from .serializers import (
    BioCoinField, MerchantPaymentSerializer, PaymentSerializer,
    TerminalPaymentRequestSerializer, WebPaymentSerializer,
)
from .services import pay_at_terminal

USERNAME = re.compile(r"^[a-z0-9][a-z0-9-]{2,29}$")


def _mock_enabled():
    return settings.DEBUG and settings.BIOPAY_ENABLE_DEMO_API


@method_decorator(csrf_protect, name="dispatch")
class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request):
        d = request.data if isinstance(request.data, dict) else {}
        username, password, name = d.get("username"), d.get("password"), d.get("name")
        errors = {}
        if not (isinstance(username, str) and USERNAME.match(username)):
            errors["username"] = ["3-30 chars: lowercase letters, digits, hyphen."]
        if not (isinstance(name, str) and 1 <= len(name.strip()) <= 100):
            errors["name"] = ["Enter your name (max 100 characters)."]
        if d.get("consent") is not True:
            errors["consent"] = ["You must consent to the simulated fingerprint demo."]
        if not isinstance(password, str):
            errors["password"] = ["Required."]
        else:
            try:
                validate_password(password)
            except DjangoValidationError as e:
                errors["password"] = list(e.messages)
        if errors:
            raise serializers.ValidationError(errors)
        try:
            with transaction.atomic():
                user = get_user_model().objects.create_user(username, password=password)
                customer = Customer.objects.create(code=username, name=name.strip(), user=user)
                grant = settings.BIOPAY_SIGNUP_GRANT
                Wallet.objects.create(customer=customer, opening_balance=grant, balance=grant)
                AuditEvent.log(username, "customer.registered", f"consent recorded, grant {grant}")
        except IntegrityError:
            raise serializers.ValidationError({"username": ["That username is taken."]}) from None
        login(request, user)
        return Response(me_payload(user), status=status.HTTP_201_CREATED)


class CustomerTerminals(APIView):
    permission_classes = [IsCustomer]

    def get(self, request):
        ts = Terminal.objects.filter(revoked_at__isnull=True).select_related("merchant")
        return Response({"mock_enrollment": _mock_enabled(), "real_sensor": settings.BIOPAY_TERMINAL_REAL_SENSOR,
                         "terminals": [{"id": t.pk, "name": t.name, "merchant": t.merchant.name} for t in ts]})


class CustomerEnroll(APIView):
    """Records the customer's consent and reserves a sensor slot. The finger itself is enrolled
    on the R307S in that slot (real mode) and never reaches this server. MOCK in dev mode."""

    permission_classes = [IsCustomer]

    def post(self, request):
        real = settings.BIOPAY_TERMINAL_REAL_SENSOR
        if not (real or _mock_enabled()):
            raise NotFound("Enrollment is disabled.")
        d = request.data if isinstance(request.data, dict) else {}
        if d.get("consent") is not True:
            raise serializers.ValidationError({"consent": ["Consent is required."]})
        tid = d.get("terminal_id")
        if type(tid) is not int:
            raise serializers.ValidationError({"terminal_id": ["Choose a terminal."]})
        customer = request.user.customer
        with transaction.atomic():
            try:
                terminal = Terminal.objects.select_for_update().get(pk=tid, revoked_at__isnull=True)
            except Terminal.DoesNotExist:
                raise NotFound("Terminal not found.") from None
            if customer.enrollments.filter(terminal=terminal).exclude(status="REVOKED").exists():
                raise serializers.ValidationError({"terminal_id": ["You already have an enrollment on this terminal."]})
            # Never reuse a slot number, even a revoked one: old records must not alias a new person.
            top = Enrollment.objects.filter(terminal=terminal).aggregate(m=Max("sensor_slot"))["m"]
            e = Enrollment.objects.create(customer=customer, terminal=terminal,
                                          sensor_slot=(top or 0) + 1, consented_at=timezone.now(),
                                          source="R307S" if real else "MOCK",
                                          simulator_allowed=not real and d.get("allow_simulator") is True)
            AuditEvent.log(request.user.get_username(), "enrollment.created",
                           f"enrollment {e.pk} ({e.source}, simulator {'on' if e.simulator_allowed else 'off'})")
        return Response({"enrollment": enrollment_row(e)}, status=status.HTTP_201_CREATED)


class SimulatorConsent(APIView):
    """The customer turns merchant-simulator payments on or off for one of their own enrollments."""

    permission_classes = [IsCustomer]

    def post(self, request, pk):
        if not _mock_enabled():
            raise NotFound("Simulator is disabled.")
        allowed = (request.data if isinstance(request.data, dict) else {}).get("allowed")
        if type(allowed) is not bool:
            raise serializers.ValidationError({"allowed": ["true or false."]})
        with transaction.atomic():
            try:  # the row lock orders this against an in-flight simulator payment
                e = Enrollment.objects.select_for_update().select_related("terminal__merchant", "customer").get(
                    pk=pk, customer=request.user.customer, status=Enrollment.Status.ACTIVE)
            except Enrollment.DoesNotExist:
                raise NotFound("Enrollment not found.") from None
            e.simulator_allowed = allowed
            e.save(update_fields=["simulator_allowed"])
            AuditEvent.log(request.user.get_username(), "enrollment.simulator_" + ("on" if allowed else "off"), f"enrollment {pk}")
        return Response({"enrollment": enrollment_row(e)})


def _detail(request, qs, serializer, pk):
    try:
        return Response({"payment": serializer(qs.get(pk=serializers.UUIDField().run_validation(pk))).data})
    except qs.model.DoesNotExist:
        raise NotFound("Payment not found.") from None


class CustomerPaymentDetail(APIView):
    permission_classes = [IsCustomer]

    def get(self, request, pk):
        return _detail(request, payments_qs().filter(payer=request.user.customer), WebPaymentSerializer, pk)


class MerchantPaymentDetail(APIView):
    permission_classes = [IsMerchant]

    def get(self, request, pk):
        return _detail(request, payments_qs().filter(merchant=request.user.merchant), MerchantPaymentSerializer, pk)


class AdminAudit(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        class S(serializers.ModelSerializer):
            class Meta:
                model = AuditEvent
                fields = ["id", "actor", "action", "detail", "created_at"]
        return paged(request, self, AuditEvent.objects.order_by("-created_at", "-id"), S)


class SimulatorRequest(TerminalPaymentRequestSerializer):
    terminal_id = BioCoinField(min_value=1)


class MerchantSimulate(APIView):
    """Dev-only: lets a signed-in merchant drive its OWN terminal with a mock slot, using the same
    payment service as the real terminal API. Off unless DEBUG and the demo API are both on."""

    permission_classes = [IsMerchant]

    def post(self, request):
        if not _mock_enabled():
            raise NotFound("Simulator is disabled.")
        s = SimulatorRequest(data=request.data)
        s.is_valid(raise_exception=True)
        v = dict(s.validated_data)
        try:
            terminal = request.user.merchant.terminals.get(pk=v.pop("terminal_id"))
        except Terminal.DoesNotExist:
            raise NotFound("Terminal not found.") from None
        try:
            payment, created = pay_at_terminal(terminal=terminal, require_simulator_consent=True, **v)
        except TerminalRevoked:  # 401 would sign the browser out; this is a 403 for a human session
            raise PermissionDenied("This terminal has been revoked.", code="terminal_revoked") from None
        data = {"payment": PaymentSerializer(payment).data, "replayed": not created,
                "authentication": "MOCK — DEVELOPMENT SIMULATION — NOT A PHYSICAL FINGERPRINT MATCH"}
        if payment.status == payment.Status.DECLINED:
            data["error"] = {"code": "insufficient_funds", "message": "Not enough simulated BioCoins."}
            return Response(data, status=422)
        return Response(data, status=201 if created else 200)
