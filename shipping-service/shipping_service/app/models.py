from django.db import models


class Shipment(models.Model):
	STATUS_PROCESSING = 'Processing'
	STATUS_SHIPPING = 'Shipping'
	STATUS_DELIVERED = 'Delivered'

	STATUS_CHOICES = (
		(STATUS_PROCESSING, 'Processing'),
		(STATUS_SHIPPING, 'Shipping'),
		(STATUS_DELIVERED, 'Delivered'),
	)

	order_id = models.IntegerField()
	address = models.TextField()
	status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_PROCESSING)

	def __str__(self):
		return f"Shipment(order_id={self.order_id}, status={self.status})"

