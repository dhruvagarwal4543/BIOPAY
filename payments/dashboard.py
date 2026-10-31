"""Human web API: session login plus customer, merchant and admin dashboards."""
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .api_errors import DemoNotReady
from .constants import SIMULATION_WARNING
from .models import Customer, Enrollment, Merchant, Payment, Terminal, Wallet
from .permissions import IsAdmin, IsCustomer, IsMerchant, role_of
from .serializers import MerchantPaymentSerializer, WebPaymentSerializer
from .services import reconcile


def payments_qs():
    return Payment.objects.select_related("payer", "merchant").order_by("-created_at", "-id")


def wallet_of(**owner):
    try:
        return Wallet.objects.get(**owner)
    except Wallet.DoesNotExist:
        raise DemoNotReady from None


def paged(request, view, queryset, serializer):
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(queryset, request, view=view)
    return paginator.get_paginated_response(serializer(page, many=True).data)


def me_payload(user):
    role = role_of(user)
    if role == "customer":
        name = user.customer.name
    elif role == "merchant":
        name = user.merchant.name
    else:
        name = user.get_username()
    return {"warning": SIMULATION_WARNING, "user": {"username": user.get_username(), "role": role, "name": name}}


class CsrfView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response({"csrf_token": get_token(request)})


class MeView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if role_of(request.user) is None:
            return Response({"warning": SIMULATION_WARNING, "user": None})
        return Response(me_payload(request.user))


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        user = authenticate(request, username=data.get("username"), password=data.get("password"))
        if user is None or role_of(user) is None:
            return Response(
                {"error": {"code": "authentication_failed", "message": "Incorrect username or password."}},
                status=401)
        login(request, user)
        return Response(me_payload(user))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"ok": True})


def terminal_row(t):
    return {
        "id": t.pk, "name": t.name, "merchant": t.merchant.name,
        "status": "REVOKED" if t.revoked_at else "ACTIVE", "last_seen": t.last_seen,
    }


def enrollment_row(e):
    return {
        "id": e.pk, "customer": e.customer.name, "terminal": e.terminal.name,
        "merchant": e.terminal.merchant.name, "status": e.status, "source": e.source,
        "consented_at": e.consented_at, "deletion_requested_at": e.deletion_requested_at,
    }


class CustomerOverview(APIView):
    permission_classes = [IsCustomer]

    def get(self, request):
        customer = request.user.customer
        wallet = wallet_of(customer=customer)
        enrollments = customer.enrollments.select_related("terminal__merchant", "customer")
        return Response({
            "warning": SIMULATION_WARNING,
            "customer": {"name": customer.name},
            "balance": wallet.balance,
            "enrollments": [enrollment_row(e) for e in enrollments.order_by("-pk")],
        })


class CustomerPayments(APIView):
    permission_classes = [IsCustomer]

    def get(self, request):
        return paged(request, self, payments_qs().filter(payer=request.user.customer), WebPaymentSerializer)


class DeletionRequest(APIView):
    permission_classes = [IsCustomer]

    @transaction.atomic
    def post(self, request, pk):
        # Filtering by the caller's own customer makes another customer's id a plain 404.
        try:
            enrollment = Enrollment.objects.select_for_update().select_related(
                "terminal__merchant", "customer"
            ).get(pk=pk, customer=request.user.customer)
        except Enrollment.DoesNotExist:
            raise NotFound("Enrollment not found.") from None
        if enrollment.status == Enrollment.Status.ACTIVE:
            enrollment.status = Enrollment.Status.DELETION_REQUESTED
            enrollment.deletion_requested_at = timezone.now()
            enrollment.save(update_fields=["status", "deletion_requested_at"])
        return Response({"enrollment": enrollment_row(enrollment)})


class MerchantOverview(APIView):
    permission_classes = [IsMerchant]

    def get(self, request):
        merchant = request.user.merchant
        wallet = wallet_of(merchant=merchant)
        return Response({
            "warning": SIMULATION_WARNING,
            "merchant": {"name": merchant.name},
            "balance": wallet.balance,
            "terminals": [terminal_row(t) for t in merchant.terminals.select_related("merchant")],
        })


class MerchantPayments(APIView):
    permission_classes = [IsMerchant]

    def get(self, request):
        return paged(request, self, payments_qs().filter(merchant=request.user.merchant), MerchantPaymentSerializer)


class AdminOverview(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        problems = reconcile()
        wallets = Wallet.objects.select_related("customer", "merchant").order_by("pk")
        return Response({
            "warning": SIMULATION_WARNING,
            "customers": [{"id": w.customer_id, "name": w.customer.name, "balance": w.balance}
                          for w in wallets if w.customer_id],
            "merchants": [{"id": w.merchant_id, "name": w.merchant.name, "balance": w.balance}
                          for w in wallets if w.merchant_id],
            "terminals": [terminal_row(t) for t in Terminal.objects.select_related("merchant")],
            "enrollments": [enrollment_row(e) for e in Enrollment.objects.select_related(
                "customer", "terminal__merchant").order_by("-pk")],
            "reconciliation": {"ok": not problems, "problems": problems},
        })


class AdminPayments(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return paged(request, self, payments_qs(), WebPaymentSerializer)


class RevokeTerminal(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        updated = Terminal.objects.filter(pk=pk, revoked_at__isnull=True).update(revoked_at=timezone.now())
        if not updated and not Terminal.objects.filter(pk=pk).exists():
            raise NotFound("Terminal not found.")
        return Response({"terminal": terminal_row(Terminal.objects.select_related("merchant").get(pk=pk))})


class RevokeEnrollment(APIView):
    """Completes a deletion request or ends an enrollment. Payments stop immediately."""

    permission_classes = [IsAdmin]

    def post(self, request, pk):
        Enrollment.objects.filter(pk=pk).exclude(status=Enrollment.Status.REVOKED).update(
            status=Enrollment.Status.REVOKED, revoked_at=timezone.now())
        try:
            enrollment = Enrollment.objects.select_related("customer", "terminal__merchant").get(pk=pk)
        except Enrollment.DoesNotExist:
            raise NotFound("Enrollment not found.") from None
        return Response({"enrollment": enrollment_row(enrollment)})
