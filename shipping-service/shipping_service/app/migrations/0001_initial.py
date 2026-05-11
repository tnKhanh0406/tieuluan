from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Shipment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_id', models.IntegerField()),
                ('address', models.TextField()),
                ('status', models.CharField(choices=[('Processing', 'Processing'), ('Shipping', 'Shipping'), ('Delivered', 'Delivered')], default='Processing', max_length=50)),
            ],
        ),
    ]
