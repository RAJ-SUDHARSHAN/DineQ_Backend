from rest_framework import serializers

from .models import Menu, MenuItem, Queue, Restaurant, Seating


class RestaurantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at',)


class MenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItem
        fields = '__all__'


class MenuSerializer(serializers.ModelSerializer):
    menu_items = MenuItemSerializer(many=True, read_only=True)

    class Meta:
        model = Menu
        fields = '__all__'


class SeatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seating
        fields = '__all__'


class QueueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Queue
        fields = '__all__'
