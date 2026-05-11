from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Cart, CartItem
from .serializers import AddToCartSerializer, CartSerializer, RemoveCartItemSerializer


class CartAddView(APIView):
	def post(self, request):
		serializer = AddToCartSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		user_id = serializer.validated_data['user_id']
		product_id = serializer.validated_data['product_id']
		quantity = serializer.validated_data['quantity']

		cart, _ = Cart.objects.get_or_create(user_id=user_id)
		item, created = CartItem.objects.get_or_create(
			cart=cart,
			product_id=product_id,
			defaults={'quantity': quantity},
		)

		if not created:
			item.quantity = quantity
			item.save(update_fields=['quantity'])

		return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


class CartDetailView(generics.RetrieveAPIView):
	serializer_class = CartSerializer
	lookup_field = 'user_id'
	queryset = Cart.objects.prefetch_related('items').all()

	def get(self, request, *args, **kwargs):
		user_id = request.query_params.get('user_id')
		if not user_id:
			return Response({'detail': 'user_id là bắt buộc.'}, status=status.HTTP_400_BAD_REQUEST)

		try:
			cart = self.queryset.get(user_id=int(user_id))
		except (Cart.DoesNotExist, ValueError):
			return Response({'detail': 'Không tìm thấy cart.'}, status=status.HTTP_404_NOT_FOUND)

		return Response(self.get_serializer(cart).data, status=status.HTTP_200_OK)


class CartRemoveView(APIView):
	def delete(self, request):
		serializer = RemoveCartItemSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		user_id = serializer.validated_data['user_id']
		product_id = serializer.validated_data['product_id']

		try:
			cart = Cart.objects.get(user_id=user_id)
		except Cart.DoesNotExist:
			return Response({'detail': 'Không tìm thấy cart.'}, status=status.HTTP_404_NOT_FOUND)

		deleted_count, _ = CartItem.objects.filter(cart=cart, product_id=product_id).delete()
		if deleted_count == 0:
			return Response({'detail': 'Không tìm thấy item trong cart.'}, status=status.HTTP_404_NOT_FOUND)

		return Response({'detail': 'Đã xóa item khỏi cart.'}, status=status.HTTP_200_OK)

