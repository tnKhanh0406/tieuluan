from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'order_id', 'amount', 'status']


class PaymentPaySerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    amount = serializers.FloatField()
