from django.urls import path

from .views import OrderCreateFromCartView, OrderListView


urlpatterns = [
    path('orders/create-from-cart', OrderCreateFromCartView.as_view(), name='order-create-from-cart'),
    path('orders/', OrderListView.as_view(), name='order-list'),
]
