import contextlib
import os
import uuid

import requests
from django.conf import settings
from django.contrib.gis.db.models.functions import Distance, GeometryDistance
from django.contrib.gis.geos import Point
from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from square.client import Client

from .models import Category, Item, Restaurant
from .serializers import RestaurantSerializer


class NearbyRestaurantsAPIView(APIView):
    def get(self, request):
        lat = request.query_params.get('lat')
        long = request.query_params.get('lng')
        radius = 5000  # radius in meters
        user_location = Point(float(long), float(lat), srid=4326)
        # Make a request to the Google Places API
        url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{long}&radius={radius}&type=restaurant&key={settings.GOOGLE_MAPS_API_KEY}"
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
                    'photo_reference': result['photos'][0]['photo_reference'] if 'photos' in result and len(result['photos']) > 0 else None,
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


def upsert_category(client, category, restaurant_id):
    idempotency_key = str(uuid.uuid4())
    id_value = f"#{category['name'].replace(' ', '_')}_{restaurant_id}"
    category_body = {
        "idempotency_key": idempotency_key,
        "object": {
            "type": "CATEGORY",
            "id": id_value,
            "category_data": {
                "name": category["name"]
            }
        }
    }

    response = client.catalog.upsert_catalog_object(category_body)
    if response.is_success():
        print(f'Successfully upserted category: {category["name"]}')
        # Return the id from the response
        return response.body['catalog_object']['id']
    elif response.is_error():
        print(f'Error upserting category: {response.errors}')
        return None


def upsert_item(client, item, restaurant_id):
    idempotency_key = str(uuid.uuid4())
    id_value = f"#{item['name'].replace(' ', '_')}_{item['category_id']}"
    item_body = {
        "idempotency_key": idempotency_key,
        "object": {
            "type": "ITEM",
            "id": id_value,
            "item_data": {
                "name": item["name"],
                "description": item["description"],
                "category_id": item["category_id"],
                "variations": [
                    {
                        "type": "ITEM_VARIATION",
                        "id": f"#{item['variations'][0]['name'].replace(' ', '_')}_{id_value}",
                        "item_variation_data": {
                            "item_id": id_value,
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
        # Return the id from the response
        return response.body['catalog_object']['id']
    elif response.is_error():
        print(f'Error upserting item: {response.errors}')
        return None


def update_item_in_category(client, restaurant, category_name, item_name, new_data):
    try:
        category = Category.objects.get(
            name=category_name, restaurant=restaurant)
    except Category.DoesNotExist:
        print(
            f'Error: Category "{category_name}" not found in restaurant "{restaurant.name}"')
        return

    category_id = category.category_id

    response = client.catalog.search_catalog_objects({
        'object_types': ['ITEM'],
        'query': {
            'prefix_query': {
                'attribute_name': 'category_id',
                'attribute_prefix': category_id
            }
        }
    })

    if response.is_success():
        items = response.body['objects']
        # Find the desired item
        for item in items:
            if item['item_data']['name'] == item_name:
                item_id = item['id']

                item_body = {
                    "idempotency_key": str(uuid.uuid4()),
                    "object": {
                        "type": "ITEM",
                        "id": item_id,
                        "item_data": new_data
                    }
                }

                # Update the item
                update_response = client.catalog.upsert_catalog_object(
                    item_body)

                if update_response.is_success():
                    print(f'Successfully updated item: {item_name}')
                elif update_response.is_error():
                    print(f'Error updating item: {update_response.errors}')
    elif response.is_error():
        print(f'Error fetching items: {response.errors}')


class RestaurantViewSet(viewsets.ModelViewSet):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer

    @action(detail=False, methods=['post'], url_path='menu/(?P<place_id>[^/.]+)/upsert-menu')
    def upsert_menu(self, request, place_id=None):
        try:
            restaurant = Restaurant.objects.get(place_id=place_id)
        except Restaurant.DoesNotExist:
            return Response({'status': 'Restaurant does not exist'}, status=400)

        menu_data = request.data.get('menu_data')
        client = get_square_client()
        for category in menu_data:
            category_id = upsert_category(client, category, place_id)
            if category_id:
                try:
                    with transaction.atomic():
                        category_obj, created = Category.objects.get_or_create(
                            name=category['name'], restaurant=restaurant)
                        category_obj.category_id = category_id
                        category_obj.save()
                except Exception as e:
                    return Response({'status': 'Category create/update not successful', 'message': f"Exception occurred while saving item: {e}"})

                for item in category.get('items', []):
                    item['category_id'] = category_id
                    item_id = upsert_item(client, item, place_id)
                    if item_id:
                        try:
                            with transaction.atomic():
                                item_obj, created = Item.objects.update_or_create(
                                    name=item['name'],
                                    category=category_obj,
                                    defaults={'item_id': item_id,
                                              'quantity': item.get('quantity', 10),
                                              'price': item['variations'][0]['price']
                                              }
                                )
                                item_obj.save()
                        except Exception as e:
                            return Response({'status': 'Menu create/update not successful', 'message': f"Exception occurred while saving item: {e}"})

        return Response({'status': 'Menu updated successfully'})