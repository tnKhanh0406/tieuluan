from django.urls import path

from .views import ShipmentCreateView, ShipmentStatusView


urlpatterns = [
    path('shipping/create', ShipmentCreateView.as_view(), name='shipping-create'),
    path('shipping/status', ShipmentStatusView.as_view(), name='shipping-status'),
]
