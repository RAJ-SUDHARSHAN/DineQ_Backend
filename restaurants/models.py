from django.contrib.gis.db import models


class Restaurant(models.Model):
    name = models.CharField(max_length=255)
    place_id = models.CharField(max_length=255, unique=True)
    location = models.PointField()
    address = models.CharField(max_length=300)
    description = models.TextField(blank=True, null=True)
    verified = models.BooleanField(default=False)
    geo_fence_radius = models.IntegerField(default=5000)

    def __str__(self):
        return self.name


class Menu(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField()


class MenuItem(models.Model):
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=6, decimal_places=2)


class Seating(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    total_capacity = models.IntegerField()
    current_occupancy = models.IntegerField()


class Queue(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    total_in_queue = models.IntegerField()
