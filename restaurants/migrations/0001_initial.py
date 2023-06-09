# Generated by Django 4.2.1 on 2023-05-31 01:39

import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Restaurant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('place_id', models.CharField(max_length=255)),
                ('location', django.contrib.gis.db.models.fields.PointField(srid=4326)),
                ('address', models.CharField(max_length=300)),
                ('description', models.TextField(blank=True)),
                ('verified', models.BooleanField(default=False)),
                ('geo_fence_radius', models.IntegerField(default=5000)),
            ],
        ),
    ]
