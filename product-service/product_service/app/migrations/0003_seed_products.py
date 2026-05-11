from django.db import migrations


BOOK_CATEGORIES = {'textbook', 'novel'}
ELECTRONICS_CATEGORIES = {'mobile', 'laptop', 'refrigerator', 'air_conditioner', 'smartwatch'}
FASHION_CATEGORIES = {'shirt', 'pants', 'shoes'}


def seed_products(apps, schema_editor):
    Category = apps.get_model('app', 'Category')
    Product = apps.get_model('app', 'Product')
    Book = apps.get_model('app', 'Book')
    Electronics = apps.get_model('app', 'Electronics')
    Fashion = apps.get_model('app', 'Fashion')

    categories = Category.objects.filter(
        name__in=list(BOOK_CATEGORIES | ELECTRONICS_CATEGORIES | FASHION_CATEGORIES)
    ).order_by('name')

    for category_index, category in enumerate(categories, start=1):
        for item_index in range(1, 11):
            product_name = f"{category.name.replace('_', ' ').title()} Product {item_index}"
            product, created = Product.objects.get_or_create(
                name=product_name,
                category=category,
                defaults={
                    'price': float(category_index * 100 + item_index * 3),
                    'stock': category_index * 10 + item_index,
                },
            )

            if not created:
                continue

            if category.name in BOOK_CATEGORIES:
                Book.objects.create(
                    product=product,
                    author=f"Author {item_index}",
                    publisher=f"Publisher {category_index}",
                    isbn=f"ISBN-{category_index:02d}-{item_index:03d}",
                )
            elif category.name in ELECTRONICS_CATEGORIES:
                Electronics.objects.create(
                    product=product,
                    brand=f"Brand {category_index}",
                    warranty=12 + item_index,
                )
            elif category.name in FASHION_CATEGORIES:
                size_cycle = ['S', 'M', 'L', 'XL']
                color_cycle = ['Black', 'White', 'Blue', 'Red', 'Gray']
                Fashion.objects.create(
                    product=product,
                    size=size_cycle[(item_index - 1) % len(size_cycle)],
                    color=color_cycle[(item_index - 1) % len(color_cycle)],
                )


def unseed_products(apps, schema_editor):
    Product = apps.get_model('app', 'Product')

    category_names = list(BOOK_CATEGORIES | ELECTRONICS_CATEGORIES | FASHION_CATEGORIES)
    products = Product.objects.filter(category__name__in=category_names)

    for product in products:
        if ' Product ' in product.name:
            product.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_seed_categories'),
    ]

    operations = [
        migrations.RunPython(seed_products, unseed_products),
    ]
