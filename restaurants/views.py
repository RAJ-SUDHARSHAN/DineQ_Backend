import contextlib
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone

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

from .models import Category, Item, Restaurant, Variation
from .serializers import (CategorySerializer, ItemSerializer,
                          RestaurantSerializer, VariationSerializer)


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


def upsert_catalog_object(client, object_body):
    response = client.catalog.upsert_catalog_object(object_body)
    if response.is_success():
        return {'success': response.body['catalog_object']}
    elif response.is_error():
        return {'error': response.errors}


def upsert_category(client, category, restaurant_id):
    idempotency_key = str(uuid.uuid4())
    id_value = f"#{category['name'].replace(' ', '_')}__{restaurant_id}"
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
    return upsert_catalog_object(client, category_body)


def upsert_item(client, item, restaurant_id):
    idempotency_key = str(uuid.uuid4())
    id_value = f"#{item['name'].replace(' ', '_')}__{restaurant_id}"

    variations = [{
        "type": "ITEM_VARIATION",
        "id": f"{id_value}_{v['name']}",
        "item_variation_data": {
            "item_id": id_value,
            "name": v['name'],
            "pricing_type": "FIXED_PRICING",
            "price_money": {
                "amount": v['price'],
                "currency": "USD"
            }
        }
    } for v in item.get('variations', [])]
    item_body = {
        "idempotency_key": idempotency_key,
        "object": {
            "type": "ITEM",
            "id": id_value,
            "item_data": {
                "name": item['name'],
                "description": item.get('description'),
                "category_id": item['category_id'],
                "variations": variations
            }
        }
    }

    response = upsert_catalog_object(client, item_body)

    if "success" in response:
        variation_ids = [v['id']
                         for v in response['success']['item_data']['variations']]
        return {'success': {'item_id': response['success']['id'], 'variation_ids': variation_ids}}

    return response


def set_inventory_count(client, catalog_object_id, quantity):
    responses = []
    for variation_id in catalog_object_id:
        body = {
            "idempotency_key": str(uuid.uuid4()),
            "changes": [
                {
                    "type": "ADJUSTMENT",
                    "adjustment": {
                        "location_id": "LS3AWJK2V4HW5",
                        "catalog_object_id": str(variation_id),
                        "from_state": "NONE",
                        "to_state": "IN_STOCK",
                        "quantity": str(quantity),
                        "occurred_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            ]
        }
        response = client.inventory.batch_change_inventory(body)
        if response.is_success():
            print(
                f"Inventory set to {quantity} for variation id {variation_id}")
            responses.append({'success': response.body})
        elif response.is_error():
            print(
                f"Error setting inventory for variation id {variation_id}: {response.errors}")
            responses.append({'error': response.errors})
    return responses


def adjust_inventory(client, restaurant, inventory_data, order_placed=False):
    for inventory_item in inventory_data:
        variation_reference_id = inventory_item['variation_reference_id']
        set_quantity = int(inventory_item['quantity'])

        try:
            variation = Variation.objects.get(
                reference_id=variation_reference_id)
        except Variation.DoesNotExist:
            return {'error': f'Variation with reference_id: {variation_reference_id} does not exist', 'status': 404}

        square_id = variation.square_id

        result = client.inventory.batch_retrieve_inventory_counts(
            body={
                "catalog_object_ids": [str(square_id)],
                "location_ids": ["LS3AWJK2V4HW5"]
            }
        )

        if result.is_error():
            return {'error': f'Failed to retrieve current inventory for variation: {variation_reference_id}. Error: {result.errors}', 'status': 500}

        current_quantity = int(result.body['counts'][0]['quantity'])
        adjustment = set_quantity - current_quantity
        body = {}
        if order_placed:
            body = {
                "idempotency_key": str(uuid.uuid4()),
                "changes": [
                    {
                        "type": "ADJUSTMENT",
                        "adjustment": {
                            "location_id": "LS3AWJK2V4HW5",
                            "catalog_object_id": str(square_id),
                            "from_state": "IN_STOCK",
                            "to_state": "SOLD",
                            "quantity": str(set_quantity),
                            "occurred_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                ]
            }
        elif adjustment <= 0:
            body = {
                "idempotency_key": str(uuid.uuid4()),
                "changes": [
                    {
                        "type": "ADJUSTMENT",
                        "adjustment": {
                            "location_id": "LS3AWJK2V4HW5",
                            "catalog_object_id": str(square_id),
                            "from_state": "IN_STOCK",
                            "to_state": "WASTE",
                            "quantity": str(abs(adjustment)),
                            "occurred_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                ]
            }
        else:
            body = {
                "idempotency_key": str(uuid.uuid4()),
                "changes": [
                    {
                        "type": "ADJUSTMENT",
                        "adjustment": {
                            "location_id": "LS3AWJK2V4HW5",
                            "catalog_object_id": str(square_id),
                            "from_state": "NONE",
                            "to_state": "IN_STOCK",
                            "quantity": str(adjustment),
                            "occurred_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                ]
            }
        response = client.inventory.batch_change_inventory(body)

        if response.is_error():
            return {'error': f'Failed to update inventory for variation: {variation_reference_id}. Error: {response.errors}', 'status': 500}

        variation.quantity = set_quantity
        variation.save()

    return {'message': 'Inventory updated successfully', 'status': 200}



def create_order(client, location_id, line_items):
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "order": {
            "location_id": location_id,
            "line_items": line_items
        }
    }

    response = client.orders.create_order(body)

    if response.is_success():
        return {'success': response.body}
    elif response.is_error():
        return {'error': response.errors}


def retrieve_order(client, location_id, order_id):
    response = client.orders.retrieve_order(order_id)

    if response.is_success():
        return response.body['order']
    elif response.is_error():
        return None


class RestaurantViewSet(viewsets.ModelViewSet):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer

    @action(detail=False, methods=['post'], url_path='(?P<place_id>[^/.]+)/upsert-menu')
    def upsert_menu(self, request, place_id=None):
        try:
            restaurant = Restaurant.objects.get(place_id=place_id)
        except Restaurant.DoesNotExist:
            return Response({'error': f'Restaurant with place_id: {place_id} does not exist'}, status=404)

        menu_data = request.data.get('menu_data')
        client = get_square_client()
        for category in menu_data:
            category_response = upsert_category(client, category, place_id)
            if 'error' in category_response:
                return Response({'error': f'Failed to upsert category: {category["name"]}. Error: {category_response["error"]}'}, status=500)

            category_id = category_response['success']['id']

            try:
                with transaction.atomic():
                    category_obj, created = Category.objects.get_or_create(
                        name=category['name'], restaurant=restaurant)
                    category_obj.category_id = category_id
                    category_obj.square_id = category_response['success']['id']
                    category_obj.save()
            except Exception as e:
                return Response({'error': f'Failed to upsert category: {category["name"]} in DB. Error: {str(e)}'}, status=500)

            for item in category.get('items', []):
                item['category_id'] = category_id
                item_response = upsert_item(client, item, place_id)
                if 'error' in item_response:
                    return Response({'error': f'Failed to upsert item: {item["name"]}. Error: {item_response["error"]}'}, status=500)

                item_id = item_response['success']['item_id']
                variation_ids = item_response['success']['variation_ids']

                inventory_response = set_inventory_count(
                    client, variation_ids, 100)
                if 'error' in inventory_response:
                    return Response({'error': f'Failed to set default inventory for item: {item["name"]}. Error: {inventory_response["error"]}'}, status=500)

                try:
                    with transaction.atomic():
                        item_obj, created = Item.objects.update_or_create(
                            name=item['name'],
                            category=category_obj,
                            defaults={
                                'item_id': item_id,
                                'description': item.get('description', None),
                                'reference_id': f"#{item['name'].replace(' ', '_')}__{place_id}",
                                'square_id': item_response['success']['item_id']
                            }
                        )
                        for i, variation in enumerate(item.get('variations', [])):
                            variation_obj, created = Variation.objects.update_or_create(
                                name=variation['name'],
                                item=item_obj,
                                defaults={
                                    'price': variation['price'],
                                    'quantity': variation.get('quantity', 100),
                                    'variation_id': f"#{variation['name'].replace(' ', '_')}__{place_id}",
                                    'reference_id': f"#{item['name'].replace(' ', '_')}__{variation['name'].replace(' ', '_')}__{place_id}",
                                    'square_id': variation_ids[i]
                                }
                            )
                except Exception as e:
                    return Response({'error': f'Failed to upsert item: {item["name"]} in DB. Error: {str(e)}'}, status=500)

        return Response({'success': 'Menu upserted successfully.'}, status=200)

    @action(detail=True, methods=['get'], url_path='get-menu')
    def get_menu(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(place_id=pk)
        except Restaurant.DoesNotExist:
            return Response({'error': f'Restaurant with place_id: {pk} does not exist'}, status=404)

        categories = restaurant.categories.all()
        serialized_categories = CategorySerializer(categories, many=True).data

        return Response(serialized_categories, status=200)

    @action(detail=True, methods=['post'], url_path='update-inventory')
    def update_inventory(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(place_id=pk)
        except Restaurant.DoesNotExist:
            return Response({'error': f'Restaurant with place_id: {pk} does not exist'}, status=404)

        client = get_square_client()
        inventory_data = request.data.get('inventory_data', [])

        response = adjust_inventory(client, restaurant, inventory_data)

        if 'error' in response:
            return Response({'error': response['error']}, status=response.get('status', 500))

        return Response(response, status=response.get('status', 200))

    @action(detail=True, methods=['post'], url_path='place-order')
    def place_order(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(place_id=pk)
        except Restaurant.DoesNotExist:
            return Response({'error': f'Restaurant with place_id: {pk} does not exist'}, status=404)

        catalog_to_variation_id = {}
        order_data = request.data.get('order_data', [])

        line_items = []
        for item in order_data:
            variation_reference_id = item['variation_reference_id']
            quantity = item['quantity']

            try:
                variation_obj = Variation.objects.get(
                    reference_id=variation_reference_id)
            except Variation.DoesNotExist:
                return Response({'error': f'Variation with reference_id: {variation_reference_id} does not exist'}, status=404)

            line_items.append({
                "quantity": str(quantity),
                "catalog_object_id": variation_obj.square_id
            })
            catalog_to_variation_id[variation_obj.square_id] = variation_reference_id

        client = get_square_client()
        response = create_order(client, "LS3AWJK2V4HW5", line_items)

        if 'error' in response:
            return Response({'error': f'Failed to place order. Error: {response["error"]}'}, status=500)

        order = retrieve_order(client, "LS3AWJK2V4HW5",
                               response['success']['order']['id'])

        line_item_counts = defaultdict(int)

        for item in order['line_items']:
            line_item_counts[catalog_to_variation_id[item['catalog_object_id']]] += int(item['quantity'])

        inventory_data = [{'variation_reference_id': variation_id, 'quantity': str(quantity)} for variation_id, quantity in line_item_counts.items()]


        inventory_response = adjust_inventory(
            client, restaurant, inventory_data, True)

        if 'error' in inventory_response:
            return Response({'error': inventory_response['error']}, status=inventory_response.get('status', 500))

        return Response({'message': 'Order placed and inventory updated successfully', 'order_id': response['success']['order']['id']}, status=200)