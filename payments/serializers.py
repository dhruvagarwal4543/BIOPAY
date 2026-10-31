from django.conf import settings
from rest_framework import serializers

from .models import Payment


class BioCoinField(serializers.IntegerField):
    def to_internal_value(self, data):
        # DRF's IntegerField also accepts 40.0 and strings; JSON integers only here.
        if type(data) is not int:
            self.fail("invalid")
        return super().to_internal_value(data)


class PaymentIDField(serializers.UUIDField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class PaymentRequestSerializer(serializers.Serializer):
    payment_id = PaymentIDField()
    amount = BioCoinField(min_value=1, max_value=2**63 - 1)

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - self.fields.keys():
            raise serializers.ValidationError({
                "non_field_errors": [f"Only {', '.join(self.fields)} are accepted."]
            })
        return super().to_internal_value(data)

    def validate_amount(self, value):
        if value > settings.BIOPAY_MAX_PAYMENT:
            raise serializers.ValidationError(
                f"The development limit is {settings.BIOPAY_MAX_PAYMENT} BioCoins."
            )
        return value


class TerminalPaymentRequestSerializer(PaymentRequestSerializer):
    # The terminal names only its sensor slot; the server resolves the customer from it.
    sensor_slot = BioCoinField(min_value=0, max_value=2**31 - 1)


class PaymentSerializer(serializers.ModelSerializer):
    payment_id = serializers.UUIDField(source="id")

    class Meta:
        model = Payment
        fields = [
            "payment_id", "payer_id", "merchant_id", "amount", "status",
            "decline_reason", "created_at",
        ]
        read_only_fields = fields


class WebPaymentSerializer(PaymentSerializer):
    payer = serializers.CharField(source="payer.name")
    merchant = serializers.CharField(source="merchant.name")

    class Meta(PaymentSerializer.Meta):
        fields = [
            "payment_id", "payer", "merchant", "amount", "status", "decline_reason",
            "auth_method", "created_at",
        ]
        read_only_fields = fields


class MerchantPaymentSerializer(WebPaymentSerializer):
    # Merchants see an opaque customer label, not the customer's name.
    payer = serializers.SerializerMethodField()

    def get_payer(self, payment):
        return f"Customer #{payment.payer_id}"
