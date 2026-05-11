from django.db import models


class Category(models.Model):
	name = models.CharField(max_length=100, unique=True)

	def __str__(self):
		return self.name


class Product(models.Model):
	name = models.CharField(max_length=255)
	price = models.FloatField()
	stock = models.IntegerField()
	category = models.ForeignKey(Category, on_delete=models.CASCADE)

	def __str__(self):
		return self.name


class Book(models.Model):
	product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='book')
	author = models.CharField(max_length=255)
	publisher = models.CharField(max_length=255)
	isbn = models.CharField(max_length=20)

	def __str__(self):
		return f"Book detail: {self.product.name}"


class Electronics(models.Model):
	product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='electronics')
	brand = models.CharField(max_length=100)
	warranty = models.IntegerField()

	def __str__(self):
		return f"Electronics detail: {self.product.name}"


class Fashion(models.Model):
	product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='fashion')
	size = models.CharField(max_length=10)
	color = models.CharField(max_length=50)

	def __str__(self):
		return f"Fashion detail: {self.product.name}"

