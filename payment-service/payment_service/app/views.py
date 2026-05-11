from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Payment
from .serializers import PaymentPaySerializer, PaymentSerializer


class PaymentPayView(APIView):
	def post(self, request):
		serializer = PaymentPaySerializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		order_id = serializer.validated_data['order_id']
		amount = serializer.validated_data['amount']

		payment = Payment.objects.create(
			order_id=order_id,
			amount=amount,
			status=Payment.STATUS_SUCCESS if amount > 0 else Payment.STATUS_FAILED,
		)

		return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class PaymentStatusView(generics.ListAPIView):
	serializer_class = PaymentSerializer

	def get_queryset(self):
		order_id = self.request.query_params.get('order_id')
		queryset = Payment.objects.all().order_by('-id')
		if order_id:
			queryset = queryset.filter(order_id=order_id)
		return queryset

