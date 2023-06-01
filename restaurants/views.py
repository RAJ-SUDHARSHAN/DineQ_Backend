import contextlib
import os
import uuid

import requests
from django.conf import settings
from django.contrib.gis.db.models.functions import Distance, GeometryDistance
from django.contrib.gis.geos import Point
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from square.client import Client

from .models import Menu, MenuItem, Queue, Restaurant, Seating
from .serializers import (MenuItemSerializer, MenuSerializer, QueueSerializer,
                          RestaurantSerializer, SeatingSerializer)


class NearbyRestaurantsAPIView(APIView):
    def get(self, request):
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        radius = 5000  # radius in meters
        user_location = Point(float(lng), float(lat), srid=4326)
        # Make a request to the Google Places API
        url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius={radius}&type=restaurant&key={settings.GOOGLE_MAPS_API_KEY}"
        response = requests.get(url)
        data = response.json()

        # Extract relevant restaurant data
        nearby_restaurants = []
        for result in data.get('results', []):
            with contextlib.suppress(Restaurant.DoesNotExist):
                restaurant = Restaurant.objects.get(
                    place_id=result['place_id'], verified=True)

                # Transform points into 3857 coordinate system (meters as unit)
                restaurant_location_meters = restaurant.location.transform(
                    3857, clone=True)
                user_location_meters = user_location.transform(
                    3857, clone=True)

                # Check if user is in the geo-fence radius
                in_range = restaurant_location_meters.distance(
                    user_location_meters) <= restaurant.geo_fence_radius

                restaurant_info = {
                    'name': result['name'],
                    'place_id': result['place_id'],
                    'location': result['geometry']['location'],
                    'address': result['vicinity'],
                    'rating': result.get('rating', None),
                    'user_ratings_total': result.get('user_ratings_total', None),
                    'in_range': in_range,
                }
                nearby_restaurants.append(restaurant_info)

        return Response(nearby_restaurants)


def get_square_client():
    return Client(
        access_token=settings.SQUARE_SANDBOX_ACCESS_TOKEN,
        environment='sandbox',  # Use 'production' for the production environment
    )


def list_menu_items():
    client = get_square_client()
    result = client.catalog.list_catalog(types='ITEM')
    if result.is_success():
        return result.body
    elif result.is_error():
        print(f'Error calling the API: {result.errors}')
        return None


def create_restaurant_id_custom_attribute_definition(client):
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "custom_attribute_definition": {
            "name": "restaurant_id",
            "type": "STRING",
            "allowed_object_types": ["ITEM"]
        }
    }
    response = client.catalog.create_catalog_custom_attribute_definition(body)

    if response.is_success():
        return response.body['custom_attribute_definition']['id']
    elif response.is_error():
        print(f'Error creating custom attribute definition: {response.errors}')
        return None


def upsert_category(client, category, restaurant_id):
    category_body = {
        "idempotency_key": str(uuid.uuid4()),
        "object": {
            "type": "CATEGORY",
            "id": f"#{restaurant_id}_{category['name'].replace(' ', '')}",
            "category_data": {
                "name": category["name"]
            }
        }
    }

    response = client.catalog.upsert_catalog_object(category_body)
    if response.is_success():
        print(f'Successfully upserted category: {category["name"]}')
        return response.body['catalog_object']['id']
    elif response.is_error():
        print(f'Error upserting category: {response.errors}')
        return None


def upsert_item(client, item, restaurant_id):
    item_body = {
        "idempotency_key": str(uuid.uuid4()),
        "object": {
            "type": "ITEM",
            "id": f"#{item['category_id']}_{item['name'].replace(' ', '')}",
            "item_data": {
                "name": item["name"],
                "description": item["description"],
                "category_id": item["category_id"],
                "variations": [
                    {
                        "type": "ITEM_VARIATION",
                        "id": f"#{item['category_id']}_{item['variations'][0]['name'].replace(' ', '')}",
                        "item_variation_data": {
                            "item_id": f"#{item['category_id']}_{item['name'].replace(' ', '')}",
                            "name": item["variations"][0]["name"],
                            "pricing_type": "FIXED_PRICING",
                            "price_money": {
                                "amount": item["variations"][0]["price"],
                                "currency": "USD"
                            }
                        }
                    }
                ]
            },
        }
    }
    response = client.catalog.upsert_catalog_object(item_body)
    if response.is_success():
        print(f'Successfully upserted item: {item["name"]}')
    elif response.is_error():
        print(f'Error upserting item: {response.errors}')


class RestaurantViewSet(viewsets.ModelViewSet):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer

    @action(detail=False, methods=['post'], url_path='menu/(?P<place_id>[^/.]+)')
    def update_menu(self, request, place_id=None):
        try:
            restaurant = Restaurant.objects.get(place_id=place_id)
        except Restaurant.DoesNotExist:
            return Response({"detail": "Restaurant not found."}, status=404)

        # Assuming the menu data is sent in the 'menu_data' key of the request
        menu_data = request.data.get('menu_data')
        client = get_square_client()
        for category in menu_data:
            category_id = upsert_category(client, category, place_id)
            if category_id:
                for item in category.get('items', []):
                    item['category_id'] = category_id
                    upsert_item(client, item, place_id)
        return Response({'status': 'Menu updated successfully'})


class MenuViewSet(viewsets.ModelViewSet):
    queryset = Menu.objects.all()
    serializer_class = MenuSerializer


class MenuItemViewSet(viewsets.ModelViewSet):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer


class SeatingViewSet(viewsets.ModelViewSet):
    queryset = Seating.objects.all()
    serializer_class = SeatingSerializer


class QueueViewSet(viewsets.ModelViewSet):
    queryset = Queue.objects.all()
    serializer_class = QueueSerializer
