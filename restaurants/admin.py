from django.contrib import admin
from django.contrib.gis.admin import OSMGeoAdmin

from .models import Category, Item, Restaurant


@admin.register(Restaurant)
class RestaurantAdmin(OSMGeoAdmin):
    list_display = ('name', 'location')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'restaurant')

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'quantity', 'price')