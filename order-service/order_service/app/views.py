import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order, OrderItem
from .serializers import CreateOrderFromCartSerializer, OrderSerializer


def _http_get_json(url):
	with urlopen(url) as response:
		return json.loads(response.read().decode('utf-8'))


def _http_post_json(url, payload):
	data = json.dumps(payload).encode('utf-8')
	request = Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
	with urlopen(request) as response:
		return json.loads(response.read().decode('utf-8'))


class OrderCreateFromCartView(APIView):
	def post(self, request):
		serializer = CreateOrderFromCartSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		user_id = serializer.validated_data['user_id']
		address = serializer.validated_data['address']
		selected_product_ids = serializer.validated_data.get('selected_product_ids') or []

		cart_url = f"{settings.CART_SERVICE_URL}/cart/?user_id={user_id}"
		try:
			cart_data = _http_get_json(cart_url)
		except (HTTPError, URLError, json.JSONDecodeError):
			return Response({'detail': 'Không lấy được cart từ cart-service.'}, status=status.HTTP_502_BAD_GATEWAY)

		items = cart_data.get('items', [])
		if selected_product_ids:
			selected_set = {int(product_id) for product_id in selected_product_ids}
			items = [item for item in items if int(item.get('product_id', 0)) in selected_set]
		if not items:
			return Response({'detail': 'Không có cart item phù hợp để tạo order.'}, status=status.HTTP_400_BAD_REQUEST)

		# compute total_price by fetching product prices from product-service
		total_price = 0.0
		try:
			product_prices = {}
			for item in items:
				pid = int(item.get('product_id', 0) or 0)
				if pid <= 0:
					continue
				if pid not in product_prices:
					prod = _http_get_json(f"{settings.PRODUCT_SERVICE_URL}/products/{pid}/")
					product_prices[pid] = float(prod.get('price', 0) or 0)
				price = product_prices.get(pid, 0.0)
				qty = int(item.get('quantity', 1) or 1)
				total_price += price * qty
		except (HTTPError, URLError, json.JSONDecodeError):
			return Response({'detail': 'Không lấy được thông tin sản phẩm từ product-service.'}, status=status.HTTP_502_BAD_GATEWAY)

		order = Order.objects.create(user_id=user_id, total_price=float(total_price), status=Order.STATUS_PENDING)

		for item in items:
			OrderItem.objects.create(
				order=order,
				product_id=item.get('product_id'),
				quantity=item.get('quantity', 1),
			)

		payment_url = f"{settings.PAYMENT_SERVICE_URL}/payment/pay"
		try:
			payment_response = _http_post_json(
				payment_url,
				{
					'order_id': order.id,
					'amount': order.total_price,
				},
			)
		except (HTTPError, URLError, json.JSONDecodeError):
			order.status = Order.STATUS_FAILED
			order.save(update_fields=['status'])
			return Response({'detail': 'Gọi payment-service thất bại.'}, status=status.HTTP_502_BAD_GATEWAY)

		if payment_response.get('status') != 'Success':
			order.status = Order.STATUS_FAILED
			order.save(update_fields=['status'])
			return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)

		order.status = Order.STATUS_PAID
		order.save(update_fields=['status'])

		shipping_url = f"{settings.SHIPPING_SERVICE_URL}/shipping/create"
		try:
			_http_post_json(
				shipping_url,
				{
					'order_id': order.id,
					'address': address,
				},
			)
			order.status = Order.STATUS_SHIPPING
			order.save(update_fields=['status'])
		except (HTTPError, URLError, json.JSONDecodeError):
			pass

		return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderListView(generics.ListAPIView):
	queryset = Order.objects.prefetch_related('items').all().order_by('-id')
	serializer_class = OrderSerializer

