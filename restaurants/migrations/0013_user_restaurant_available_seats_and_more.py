# Generated by Django 4.2.1 on 2023-06-05 08:39

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('restaurants', '0012_category_square_id_item_square_id_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('password', models.CharField(max_length=128)),
                ('phone_number', models.CharField(blank=True, max_length=20, null=True)),
                ('is_staff_user', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
            ],
        ),
        migrations.AddField(
            model_name='restaurant',
            name='available_seats',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='total_seats',
            field=models.IntegerField(default=20),
        ),
        migrations.CreateModel(
            name='Queue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('party_size', models.IntegerField()),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('restaurant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='queue', to='restaurants.restaurant')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='queue_entries', to='restaurants.user')),
            ],
            options={
                'ordering': ['joined_at'],
            },
        ),
    ]
