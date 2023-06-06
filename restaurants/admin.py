from django.contrib import admin
from django.contrib.gis.admin import OSMGeoAdmin

from .models import Category, Item, Queue, Restaurant, Variation, User, Order


@admin.register(Restaurant)
class RestaurantAdmin(OSMGeoAdmin):
    list_display = ("name", "location", "verified", "total_seats", "available_seats")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category")


@admin.register(Variation)
class VariationAdmin(admin.ModelAdmin):
    list_display = ("name", "item", "price", "quantity")


@admin.register(Queue)
class QueueAdmin(admin.ModelAdmin):
    list_display = ("restaurant", "party_size", "user", "joined_at")

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "is_seated", "is_active", "is_staff_user")
    
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("user", "unique_order_identifier", "order_id")