from django.db import migrations


def seed_categories(apps, schema_editor):
    Category = apps.get_model('app', 'Category')
    categories = [
        'textbook',
        'novel',
        'mobile',
        'laptop',
        'refrigerator',
        'air_conditioner',
        'shirt',
        'pants',
        'shoes',
        'smartwatch',
    ]
    for category_name in categories:
        Category.objects.get_or_create(name=category_name)


def unseed_categories(apps, schema_editor):
    Category = apps.get_model('app', 'Category')
    Category.objects.filter(
        name__in=[
            'textbook',
            'novel',
            'mobile',
            'laptop',
            'refrigerator',
            'air_conditioner',
            'shirt',
            'pants',
            'shoes',
            'smartwatch',
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
