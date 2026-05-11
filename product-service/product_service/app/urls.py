from django.urls import path

from .views import ProductListCreateView, ProductRetrieveView


urlpatterns = [
    path('products/', ProductListCreateView.as_view(), name='product-list-create'),
    path('products/<int:id>/', ProductRetrieveView.as_view(), name='product-detail'),
]
