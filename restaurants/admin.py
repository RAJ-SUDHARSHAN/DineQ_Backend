from django.contrib import admin
from django.contrib.gis.admin import OSMGeoAdmin

from .models import Category, Item, Restaurant, Variation, Queue


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
