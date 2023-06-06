from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import BaseUserManager
from django.contrib.gis.db import models
from django.utils.crypto import get_random_string


class Restaurant(models.Model):
    name = models.CharField(max_length=255)
    place_id = models.CharField(max_length=255, unique=True)
    location = models.PointField()
    address = models.CharField(max_length=300)
    description = models.TextField(blank=True, null=True)
    verified = models.BooleanField(default=False)
    geo_fence_radius = models.IntegerField(default=5000)
    total_seats = models.IntegerField(default=20)
    available_seats = models.IntegerField(default=20)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=255)
    category_id = models.CharField(max_length=255)
    reference_id = models.CharField(max_length=255, blank=True, null=True)
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="categories"
    )
    square_id = models.CharField(max_length=255, blank=True, null=True)


class Item(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    item_id = models.CharField(max_length=255)
    reference_id = models.CharField(max_length=255, blank=True, null=True)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="items"
    )
    square_id = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name


class Variation(models.Model):
    name = models.CharField(max_length=255)
    variation_id = models.CharField(max_length=255, blank=True, null=True)
    reference_id = models.CharField(max_length=255, blank=True, null=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="variations")
    price = models.DecimalField(max_digits=7, decimal_places=2)
    quantity = models.IntegerField(default=0)
    square_id = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(models.Model):
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    is_staff_user = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_seated = models.BooleanField(default=False)
    USERNAME_FIELD = "email"

    objects = UserManager()

    def set_password(self, password):
        self.password = make_password(password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.email


class Queue(models.Model):
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="queue"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="queue_entries"
    )
    party_size = models.IntegerField()
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at"]

def generate_uoi():
    return get_random_string(length=6)


class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    unique_order_identifier = models.CharField(
        max_length=6, unique=True, default=generate_uoi
    )
    order_id = models.CharField(max_length=255)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"Order {self.unique_order_identifier} by {self.user.email}"