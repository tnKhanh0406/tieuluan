from rest_framework import generics

from .models import Product
from .serializers import ProductSerializer


class ProductListCreateView(generics.ListCreateAPIView):
	queryset = Product.objects.select_related('category').all().order_by('id')
	serializer_class = ProductSerializer


class ProductRetrieveView(generics.RetrieveAPIView):
	queryset = Product.objects.select_related('category').all()
	serializer_class = ProductSerializer
	lookup_field = 'id'

