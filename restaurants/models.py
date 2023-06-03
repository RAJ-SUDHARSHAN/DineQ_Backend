from django.contrib.gis.db import models


class Restaurant(models.Model):
    name = models.CharField(max_length=255)
    place_id = models.CharField(max_length=255, unique=True)
    location = models.PointField()
    address = models.CharField(max_length=300)
    description = models.TextField(blank=True, null=True)
    verified = models.BooleanField(default=False)
    geo_fence_radius = models.IntegerField(default=5000)
    category_ids = models.JSONField(blank=True, null=True, default=dict)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=255)
    category_id = models.CharField(max_length=255)
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name='categories')


class Item(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    item_id = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name='items')

    def __str__(self):
        return self.name


class Variation(models.Model):
    name = models.CharField(max_length=255)
    item = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name='variations')
    price = models.DecimalField(max_digits=7, decimal_places=2)
    quantity = models.IntegerField(default=0)

    def __str__(self):
        return self.name
