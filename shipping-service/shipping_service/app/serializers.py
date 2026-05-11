from rest_framework import serializers

from .models import Shipment


class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = ['id', 'order_id', 'address', 'status']


class ShipmentCreateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    address = serializers.CharField()
