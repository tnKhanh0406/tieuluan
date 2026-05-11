from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Shipment
from .serializers import ShipmentCreateSerializer, ShipmentSerializer


class ShipmentCreateView(APIView):
	def post(self, request):
		serializer = ShipmentCreateSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		shipment = Shipment.objects.create(
			order_id=serializer.validated_data['order_id'],
			address=serializer.validated_data['address'],
			status=Shipment.STATUS_PROCESSING,
		)
		return Response(ShipmentSerializer(shipment).data, status=status.HTTP_201_CREATED)


class ShipmentStatusView(generics.ListAPIView):
	serializer_class = ShipmentSerializer

	def get_queryset(self):
		order_id = self.request.query_params.get('order_id')
		queryset = Shipment.objects.all().order_by('-id')
		if order_id:
			queryset = queryset.filter(order_id=order_id)
		return queryset

