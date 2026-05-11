from rest_framework import serializers

from .models import Book, Category, Electronics, Fashion, Product


BOOK_CATEGORIES = {'textbook', 'novel'}
ELECTRONICS_CATEGORIES = {'mobile', 'laptop', 'refrigerator', 'air_conditioner', 'smartwatch'}
FASHION_CATEGORIES = {'shirt', 'pants', 'shoes'}


class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ['author', 'publisher', 'isbn']


class ElectronicsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Electronics
        fields = ['brand', 'warranty']


class FashionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fashion
        fields = ['size', 'color']


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    book = BookSerializer(required=False)
    electronics = ElectronicsSerializer(required=False)
    fashion = FashionSerializer(required=False)

    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'stock', 'category', 'category_name', 'book', 'electronics', 'fashion']

    def validate(self, attrs):
        category = attrs.get('category')
        book_data = self.initial_data.get('book')
        electronics_data = self.initial_data.get('electronics')
        fashion_data = self.initial_data.get('fashion')

        if not category:
            return attrs

        category_name = category.name

        if book_data and category_name not in BOOK_CATEGORIES:
            raise serializers.ValidationError('Book detail chỉ áp dụng cho category textbook hoặc novel.')

        if electronics_data and category_name not in ELECTRONICS_CATEGORIES:
            raise serializers.ValidationError('Electronics detail chỉ áp dụng cho category electronics hợp lệ.')

        if fashion_data and category_name not in FASHION_CATEGORIES:
            raise serializers.ValidationError('Fashion detail chỉ áp dụng cho category shirt, pants, shoes.')

        return attrs

    def create(self, validated_data):
        book_data = validated_data.pop('book', None)
        electronics_data = validated_data.pop('electronics', None)
        fashion_data = validated_data.pop('fashion', None)

        product = Product.objects.create(**validated_data)

        if book_data:
            Book.objects.create(product=product, **book_data)
        if electronics_data:
            Electronics.objects.create(product=product, **electronics_data)
        if fashion_data:
            Fashion.objects.create(product=product, **fashion_data)

        return product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']
