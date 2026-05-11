from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
	ROLE_ADMIN = 'admin'
	ROLE_STAFF = 'staff'
	ROLE_CUSTOMER = 'customer'

	ROLE_CHOICES = (
		(ROLE_ADMIN, 'Admin'),
		(ROLE_STAFF, 'Staff'),
		(ROLE_CUSTOMER, 'Customer'),
	)

	role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CUSTOMER)

	def __str__(self):
		return f"{self.username} ({self.role})"
