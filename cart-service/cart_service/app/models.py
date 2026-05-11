from django.db import models


class Cart(models.Model):
	user_id = models.IntegerField(unique=True)

	def __str__(self):
		return f"Cart(user_id={self.user_id})"


class CartItem(models.Model):
	cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
	product_id = models.IntegerField()
	quantity = models.IntegerField()

	class Meta:
		unique_together = ('cart', 'product_id')

	def __str__(self):
		return f"CartItem(cart={self.cart_id}, product={self.product_id}, qty={self.quantity})"

