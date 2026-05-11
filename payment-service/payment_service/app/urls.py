from django.urls import path

from .views import PaymentPayView, PaymentStatusView


urlpatterns = [
    path('payment/pay', PaymentPayView.as_view(), name='payment-pay'),
    path('payment/status', PaymentStatusView.as_view(), name='payment-status'),
]
