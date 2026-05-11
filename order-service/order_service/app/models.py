from django.db import models


class Order(models.Model):
	STATUS_PENDING = 'PENDING'
	STATUS_PAID = 'PAID'
	STATUS_FAILED = 'FAILED'
	STATUS_SHIPPING = 'SHIPPING'

	STATUS_CHOICES = (
		(STATUS_PENDING, 'Pending'),
		(STATUS_PAID, 'Paid'),
		(STATUS_FAILED, 'Failed'),
		(STATUS_SHIPPING, 'Shipping'),
	)

	user_id = models.IntegerField()
	total_price = models.FloatField()
	status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_PENDING)

	def __str__(self):
		return f"Order(id={self.id}, user_id={self.user_id}, status={self.status})"


class OrderItem(models.Model):
	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
	product_id = models.IntegerField()
	quantity = models.IntegerField()

	def __str__(self):
		return f"OrderItem(order={self.order_id}, product={self.product_id}, qty={self.quantity})"

