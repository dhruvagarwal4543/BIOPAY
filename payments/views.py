from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_errors import DemoNotReady
from .authentication import MockDemoAuthentication, TerminalKeyAuthentication
from .constants import DEMO_CUSTOMER_CODE, DEMO_MERCHANT_CODE, SIMULATION_WARNING
from .models import Payment, Wallet
from .serializers import (
    PaymentRequestSerializer, PaymentSerializer, TerminalPaymentRequestSerializer,
)
from .services import pay_at_terminal, pay_demo


def demo_payments():
    return Payment.objects.filter(
        payer__code=DEMO_CUSTOMER_CODE, merchant__code=DEMO_MERCHANT_CODE
    )


class DemoAPIView(APIView):
    authentication_classes = [MockDemoAuthentication]
    permission_classes = [IsAuthenticated]

    def finalize_response(self, request, response, *args, **kwargs):
        if isinstance(getattr(response, "data", None), dict):
            response.data = {
                "warning": SIMULATION_WARNING,
                "authentication": "MOCK — NO BIOMETRIC VERIFICATION",
                **response.data,
            }
        return super().finalize_response(request, response, *args, **kwargs)


class PaymentView(DemoAPIView):
    def post(self, request):
        serializer = PaymentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment, created = pay_demo(**serializer.validated_data)
        data = {"payment": PaymentSerializer(payment).data, "replayed": not created}
        if payment.status == Payment.Status.DECLINED:
            data["error"] = {
                "code": "insufficient_funds", "message": "Not enough simulated BioCoins."
            }
            return Response(data, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class PaymentStatusView(DemoAPIView):
    def get(self, request, payment_id):
        payment_id = serializers.UUIDField().run_validation(payment_id)
        try:
            payment = demo_payments().get(pk=payment_id)
        except Payment.DoesNotExist:
            raise NotFound("Payment not found.") from None
        return Response({"payment": PaymentSerializer(payment).data})


class WalletView(DemoAPIView):
    def get(self, request):
        # One query gives a consistent snapshot of both committed balances.
        wallets = list(Wallet.objects.filter(
            Q(customer__code=DEMO_CUSTOMER_CODE) | Q(merchant__code=DEMO_MERCHANT_CODE)
        ))
        if len(wallets) != 2:
            raise DemoNotReady
        customer = next(wallet for wallet in wallets if wallet.customer_id is not None)
        merchant = next(wallet for wallet in wallets if wallet.merchant_id is not None)
        return Response({
            "customer": {"id": customer.customer_id, "balance": customer.balance},
            "merchant": {"id": merchant.merchant_id, "balance": merchant.balance},
        })


class HistoryView(DemoAPIView):
    def get(self, request):
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(
            demo_payments().order_by("-created_at", "-id"), request, view=self
        )
        return paginator.get_paginated_response(PaymentSerializer(page, many=True).data)


class TerminalAPIView(DemoAPIView):
    authentication_classes = [TerminalKeyAuthentication]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if isinstance(getattr(response, "data", None), dict):
            response.data["authentication"] = (
                "MOCK — DEVELOPMENT SIMULATION — NOT A PHYSICAL FINGERPRINT MATCH"
            )
        return response


class TerminalPaymentView(TerminalAPIView):
    def post(self, request):
        serializer = TerminalPaymentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment, created = pay_at_terminal(terminal=request.user.terminal, **serializer.validated_data)
        data = {"payment": PaymentSerializer(payment).data, "replayed": not created}
        if payment.status == Payment.Status.DECLINED:
            data["error"] = {
                "code": "insufficient_funds", "message": "Not enough simulated BioCoins."
            }
            return Response(data, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class TerminalPaymentStatusView(TerminalAPIView):
    def get(self, request, payment_id):
        payment_id = serializers.UUIDField().run_validation(payment_id)
        try:
            payment = Payment.objects.get(pk=payment_id, terminal=request.user.terminal)
        except Payment.DoesNotExist:
            raise NotFound("Payment not found.") from None
        return Response({"payment": PaymentSerializer(payment).data})
