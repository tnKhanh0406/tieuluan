from django.db import models


class Payment(models.Model):
	STATUS_PENDING = 'Pending'
	STATUS_SUCCESS = 'Success'
	STATUS_FAILED = 'Failed'

	STATUS_CHOICES = (
		(STATUS_PENDING, 'Pending'),
		(STATUS_SUCCESS, 'Success'),
		(STATUS_FAILED, 'Failed'),
	)

	order_id = models.IntegerField()
	amount = models.FloatField()
	status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_PENDING)

	def __str__(self):
		return f"Payment(order_id={self.order_id}, status={self.status})"

