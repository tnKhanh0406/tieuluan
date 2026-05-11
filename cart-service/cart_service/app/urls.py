from django.urls import path

from .views import CartAddView, CartDetailView, CartRemoveView


urlpatterns = [
    path('cart/add', CartAddView.as_view(), name='cart-add'),
    path('cart/', CartDetailView.as_view(), name='cart-detail'),
    path('cart/remove', CartRemoveView.as_view(), name='cart-remove'),
]
