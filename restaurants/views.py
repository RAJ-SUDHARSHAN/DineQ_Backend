import contextlib
import json
import os
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.db.models.functions import Distance, GeometryDistance
from django.contrib.gis.geos import Point
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from square.client import Client

from .models import Category, Item, Queue, Restaurant, User, Variation, Order
from .serializers import (
    CategorySerializer,
    ItemSerializer,
    RestaurantSerializer,
    VariationSerializer,
)


@csrf_exempt
def register(request):
    if request.method == "POST":
        data = json.loads(request.body)
        email = data.get("email", None)
        password = data.get("password", None)

        if not email or not password:
            return JsonResponse({"error": "Email and Password required"}, status=400)

        try:
            user = User.objects.filter(email=email).first()
            if user:
                return JsonResponse(
                    {"error": "A user with this email already exists"}, status=400
                )

            user = User.objects.create_user(email=email, password=password)
            user.save()
            return JsonResponse({"success": "User created successfully"}, status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    else:
        return JsonResponse({"error": "Invalid request method"}, status=400)


@csrf_exempt
def login(request):
    if request.method == "POST":
        data = json.loads(request.body)
        email = data.get("email", None)
        password = data.get("password", None)

        if not email or not password:
            return JsonResponse({"error": "Email and Password required"}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return JsonResponse({"error": "Invalid email or password"}, status=400)

        if user.check_password(password):
            return JsonResponse({"success": "User logged in successfully"}, status=200)
        else:
            return JsonResponse({"error": "Invalid email or password"}, status=400)
    else:
        return JsonResponse({"error": "Invalid request method"}, status=400)


class NearbyRestaurantsAPIView(APIView):
    def get(self, request):
        lat = request.query_params.get("lat")
        long = request.query_params.get("lng")
        radius = 5000  # radius in meters
        user_location = Point(float(long), float(lat), srid=4326)
        # Make a request to the Google Places API
        url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{long}&radius={radius}&type=restaurant&key={settings.GOOGLE_MAPS_API_KEY}"
        response = requests.get(url)
        data = response.json()

        # Extract relevant restaurant data
        nearby_restaurants = []
        for result in data.get("results", []):
            with contextlib.suppress(Restaurant.DoesNotExist):
                restaurant = Restaurant.objects.get(
                    place_id=result["place_id"], verified=True
                )

                # Transform points into 3857 coordinate system (meters as unit)
                restaurant_location_meters = restaurant.location.transform(
                    3857, clone=True
                )
                user_location_meters = user_location.transform(3857, clone=True)

                # Check if user is in the geo-fence radius
                in_range = (
                    restaurant_location_meters.distance(user_location_meters)
                    <= restaurant.geo_fence_radius
                )

                restaurant_info = {
                    "name": result["name"],
                    "place_id": result["place_id"],
                    "location": result["geometry"]["location"],
                    "address": result["vicinity"],
                    "rating": result.get("rating", None),
                    "user_ratings_total": result.get("user_ratings_total", None),
                    "photo_reference": result["photos"][0]["photo_reference"]
                    if "photos" in result and len(result["photos"]) > 0
                    else None,
                    "in_range": in_range,
                }
                nearby_restaurants.append(restaurant_info)

        return Response(nearby_restaurants)


def get_square_client():
    return Client(
        access_token=settings.SQUARE_SANDBOX_ACCESS_TOKEN,
        environment="sandbox",  # Use 'production' for the production environment
    )


def upsert_catalog_object(client, object_body):
    response = client.catalog.upsert_catalog_object(object_body)
    if response.is_success():
        return {"success": response.body["catalog_object"]}
    elif response.is_error():
        return {"error": response.errors}


def upsert_category(client, category, restaurant_id):
    idempotency_key = str(uuid.uuid4())
    id_value = f"#{category['name'].replace(' ', '_')}__{restaurant_id}"
    category_body = {
        "idempotency_key": idempotency_key,
        "object": {
            "type": "CATEGORY",
            "id": id_value,
            "category_data": {"name": category["name"]},
        },
    }
    return upsert_catalog_object(client, category_body)


def upsert_item(client, item, restaurant_id):
    idempotency_key = str(uuid.uuid4())
    id_value = f"#{item['name'].replace(' ', '_')}__{restaurant_id}"

    variations = [
        {
            "type": "ITEM_VARIATION",
            "id": f"{id_value}_{v['name']}",
            "item_variation_data": {
                "item_id": id_value,
                "name": v["name"],
                "pricing_type": "FIXED_PRICING",
                "price_money": {"amount": v["price"], "currency": "USD"},
            },
        }
        for v in item.get("variations", [])
    ]
    item_body = {
        "idempotency_key": idempotency_key,
        "object": {
            "type": "ITEM",
            "id": id_value,
            "item_data": {
                "name": item["name"],
                "description": item.get("description"),
                "category_id": item["category_id"],
                "variations": variations,
            },
        },
    }

    response = upsert_catalog_object(client, item_body)

    if "success" in response:
        variation_ids = [
            v["id"] for v in response["success"]["item_data"]["variations"]
        ]
        return {
            "success": {
                "item_id": response["success"]["id"],
                "variation_ids": variation_ids,
            }
        }

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
                        "occurred_at": datetime.now(timezone.utc).isoformat(),
                    },
                }
            ],
        }
        response = client.inventory.batch_change_inventory(body)
        if response.is_success():
            print(f"Inventory set to {quantity} for variation id {variation_id}")
            responses.append({"success": response.body})
        elif response.is_error():
            print(
                f"Error setting inventory for variation id {variation_id}: {response.errors}"
            )
            responses.append({"error": response.errors})
    return responses


def adjust_inventory(client, restaurant, inventory_data, order_placed=False):
    for inventory_item in inventory_data:
        variation_reference_id = inventory_item["variation_reference_id"]
        set_quantity = int(inventory_item["quantity"])

        try:
            variation = Variation.objects.get(reference_id=variation_reference_id)
        except Variation.DoesNotExist:
            return {
                "error": f"Variation with reference_id: {variation_reference_id} does not exist",
                "status": 404,
            }

        square_id = variation.square_id

        result = client.inventory.batch_retrieve_inventory_counts(
            body={
                "catalog_object_ids": [str(square_id)],
                "location_ids": ["LS3AWJK2V4HW5"],
            }
        )

        if result.is_error():
            return {
                "error": f"Failed to retrieve current inventory for variation: {variation_reference_id}. Error: {result.errors}",
                "status": 500,
            }

        current_quantity = int(result.body["counts"][0]["quantity"])
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
                            "occurred_at": datetime.now(timezone.utc).isoformat(),
                        },
                    }
                ],
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
                            "occurred_at": datetime.now(timezone.utc).isoformat(),
                        },
                    }
                ],
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
                            "occurred_at": datetime.now(timezone.utc).isoformat(),
                        },
                    }
                ],
            }
        response = client.inventory.batch_change_inventory(body)

        if response.is_error():
            return {
                "error": f"Failed to update inventory for variation: {variation_reference_id}. Error: {response.errors}",
                "status": 500,
            }

        variation.quantity = set_quantity
        variation.save()

    return {"message": "Inventory updated successfully", "status": 200}


def create_order(client, location_id, line_items):
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "order": {"location_id": location_id, "line_items": line_items},
    }

    response = client.orders.create_order(body)

    if response.is_success():
        return {"success": response.body}
    elif response.is_error():
        return {"error": response.errors}


def retrieve_order(client, order_id):
    response = client.orders.retrieve_order(order_id)

    if response.is_success():
        return {"order": response.body["order"]}
    elif response.is_error():
        return {"error": response.errors}


def create_invoice(client, location_id, order_id):
    due_date = (datetime.now() + timedelta(days=5)).date()
    body = {
        "invoice": {
            "location_id": location_id,
            "order_id": order_id,
            "payment_requests": [{"request_type": "BALANCE", "due_date": due_date}],
            "delivery_method": "EMAIL",
            "accepted_payment_methods": {"card": True},
        },
        "idempotency_key": str(uuid.uuid4()),
    }
    return client.invoices.create_invoice(body=body)


class RestaurantViewSet(viewsets.ModelViewSet):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer

    @action(detail=False, methods=["post"], url_path="(?P<place_id>[^/.]+)/upsert-menu")
    def upsert_menu(self, request, place_id=None):
        try:
            restaurant = Restaurant.objects.get(place_id=place_id)
        except Restaurant.DoesNotExist:
            return Response(
                {"error": f"Restaurant with place_id: {place_id} does not exist"},
                status=404,
            )

        menu_data = request.data.get("menu_data")
        client = get_square_client()
        for category in menu_data:
            category_response = upsert_category(client, category, place_id)
            if "error" in category_response:
                return Response(
                    {
                        "error": f'Failed to upsert category: {category["name"]}. Error: {category_response["error"]}'
                    },
                    status=500,
                )

            category_id = category_response["success"]["id"]

            try:
                with transaction.atomic():
                    category_obj, created = Category.objects.get_or_create(
                        name=category["name"], restaurant=restaurant
                    )
                    category_obj.category_id = category_id
                    category_obj.square_id = category_response["success"]["id"]
                    category_obj.save()
            except Exception as e:
                return Response(
                    {
                        "error": f'Failed to upsert category: {category["name"]} in DB. Error: {str(e)}'
                    },
                    status=500,
                )

            for item in category.get("items", []):
                item["category_id"] = category_id
                item_response = upsert_item(client, item, place_id)
                if "error" in item_response:
                    return Response(
                        {
                            "error": f'Failed to upsert item: {item["name"]}. Error: {item_response["error"]}'
                        },
                        status=500,
                    )

                item_id = item_response["success"]["item_id"]
                variation_ids = item_response["success"]["variation_ids"]

                inventory_response = set_inventory_count(client, variation_ids, 100)
                if "error" in inventory_response:
                    return Response(
                        {
                            "error": f'Failed to set default inventory for item: {item["name"]}. Error: {inventory_response["error"]}'
                        },
                        status=500,
                    )

                try:
                    with transaction.atomic():
                        item_obj, created = Item.objects.update_or_create(
                            name=item["name"],
                            category=category_obj,
                            defaults={
                                "item_id": item_id,
                                "description": item.get("description", None),
                                "reference_id": f"#{item['name'].replace(' ', '_')}__{place_id}",
                                "square_id": item_response["success"]["item_id"],
                            },
                        )
                        for i, variation in enumerate(item.get("variations", [])):
                            variation_obj, created = Variation.objects.update_or_create(
                                name=variation["name"],
                                item=item_obj,
                                defaults={
                                    "price": variation["price"] / 100,
                                    "quantity": variation.get("quantity", 100),
                                    "variation_id": f"#{variation['name'].replace(' ', '_')}__{place_id}",
                                    "reference_id": f"#{item['name'].replace(' ', '_')}__{variation['name'].replace(' ', '_')}__{place_id}",
                                    "square_id": variation_ids[i],
                                },
                            )
                except Exception as e:
                    return Response(
                        {
                            "error": f'Failed to upsert item: {item["name"]} in DB. Error: {str(e)}'
                        },
                        status=500,
                    )

        return Response({"success": "Menu upserted successfully."}, status=200)

    @action(detail=True, methods=["get"], url_path="get-menu")
    def get_menu(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(place_id=pk)
        except Restaurant.DoesNotExist:
            return Response(
                {"error": f"Restaurant with place_id: {pk} does not exist"}, status=404
            )

        categories = restaurant.categories.all()
        serialized_categories = CategorySerializer(categories, many=True).data

        return Response(serialized_categories, status=200)

    @action(detail=True, methods=["get"], url_path="available-seats")
    def available_seats(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(place_id=pk)
        except Restaurant.DoesNotExist:
            return Response(
                {"error": f"Restaurant with place_id: {pk} does not exist"}, status=404
            )

        return Response({"available_seats": restaurant.available_seats}, status=200)

    @action(detail=True, methods=["post"], url_path="update-inventory")
    def update_inventory(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(place_id=pk)
        except Restaurant.DoesNotExist:
            return Response(
                {"error": f"Restaurant with place_id: {pk} does not exist"}, status=404
            )

        client = get_square_client()
        inventory_data = request.data.get("inventory_data", [])

        response = adjust_inventory(client, restaurant, inventory_data)

        if "error" in response:
            return Response(
                {"error": response["error"]}, status=response.get("status", 500)
            )

        return Response(response, status=response.get("status", 200))

    @action(detail=True, methods=["post"], url_path="place-order")
    def place_order(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(place_id=pk)
        except Restaurant.DoesNotExist:
            return Response(
                {"error": f"Restaurant with place_id: {pk} does not exist"}, status=404
            )

        email = request.data.get("email")
        user = get_object_or_404(User, email=email)

        catalog_to_variation_id = {}
        order_data = request.data.get("order_data", [])
        line_items = []
        for item in order_data:
            variation_reference_id = item["variation_reference_id"]
            quantity = item["quantity"]

            try:
                variation_obj = Variation.objects.get(
                    reference_id=variation_reference_id
                )
            except Variation.DoesNotExist:
                return Response(
                    {
                        "error": f"Variation with reference_id: {variation_reference_id} does not exist"
                    },
                    status=404,
                )

            line_items.append(
                {
                    "quantity": str(quantity),
                    "catalog_object_id": variation_obj.square_id,
                }
            )
            catalog_to_variation_id[variation_obj.square_id] = variation_reference_id

        client = get_square_client()
        response = create_order(client, "LS3AWJK2V4HW5", line_items)
        if "error" in response:
            return Response(
                {"error": f'Failed to place order. Error: {response["error"]}'},
                status=500,
            )

        order = retrieve_order(client, response["success"]["order"]["id"])["order"]
        order_id = response["success"]["order"]["id"]

        created_order = Order.objects.create(user=user, order_id=order_id)

        line_item_counts = defaultdict(int)

        for item in order["line_items"]:
            line_item_counts[catalog_to_variation_id[item["catalog_object_id"]]] += int(
                item["quantity"]
            )

        inventory_data = [
            {"variation_reference_id": variation_id, "quantity": str(quantity)}
            for variation_id, quantity in line_item_counts.items()
        ]

        inventory_response = adjust_inventory(client, restaurant, inventory_data, True)

        if "error" in inventory_response:
            return Response(
                {"error": inventory_response["error"]},
                status=inventory_response.get("status", 500),
            )

        invoice_result = create_invoice(client, "LS3AWJK2V4HW5", order_id)
        if invoice_result.is_error():
            return Response(
                {"error": f"Failed to create invoice. Error: {invoice_result.errors}"},
                status=500,
            )

        return Response(
            {
                "message": "Order placed and inventory updated successfully",
                "order_id": response["success"]["order"]["id"],
                "invoice_id": invoice_result.body["invoice"]["id"],
                "uoi": created_order.unique_order_identifier,
            },
            status=200,
        )

    @action(detail=True, methods=["get"], url_path="retrieve-order")
    def retrieve_order(self, request, pk=None):
        client = get_square_client()
        order_id = request.query_params.get("order_id")
        uoiObject = get_object_or_404(Order, order_id=order_id)
        if not order_id:
            return Response({"error": "order_id parameter is required"}, status=400)

        result = retrieve_order(client, order_id)
        result["uoi"] = uoiObject.unique_order_identifier
        if "error" in result:
            return Response(result, status=400)
        else:
            return Response(result, status=200)

    @action(detail=True, methods=["get"], url_path="get-invoice")
    def get_invoice(self, request, pk=None):
        client = get_square_client()
        invoice_id = request.query_params.get("invoice_id")
        if not invoice_id:
            return Response({"error": "invoice_id parameter is required"}, status=400)

        result = client.invoices.get_invoice(invoice_id)

        if result.is_success():
            return Response(result.body, status=200)
        elif result.is_error():
            return Response({"error": result.errors}, status=500)

    @action(detail=True, methods=["post"], url_path="checkout")
    def create_terminal_checkout(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(place_id=pk)
        except Restaurant.DoesNotExist:
            return Response(
                {"error": f"Restaurant with place_id: {pk} does not exist"}, status=404
            )

        uoi = request.data.get("uoi")
        if not uoi:
            return Response({"error": "uoi parameter is required"}, status=400)

        try:
            order_obj = Order.objects.get(unique_order_identifier=uoi)
        except Order.DoesNotExist:
            return Response(
                {"error": f"Order with UOI: {uoi} does not exist"}, status=404
            )

        order_id = order_obj.order_id

        client = get_square_client()
        response = retrieve_order(client, order_id)
        if "error" in response:
            return Response(response, status=400)

        order = response["order"]

        if order["state"] != "OPEN":
            return Response(
                {"error": "Cannot create a checkout for a non-OPEN order"}, status=400
            )

        total_money = order["total_money"]
        amount = total_money["amount"]
        currency = total_money["currency"]

        checkout_request_body = {
            "idempotency_key": str(uuid.uuid4()),
            "checkout": {
                "amount_money": {"amount": amount, "currency": currency},
                "order_id": order_id,
                "device_options": {"device_id": "9fa747a2-25ff-48ee-b078-04381f7c828f"},
                "payment_type": "CARD_PRESENT",
            },
        }

        result = client.terminal.create_terminal_checkout(body=checkout_request_body)

        if result.is_success():
            email = request.data.get("email")
            user = User.objects.get(email=email)
            user.is_seated = False
            user.save()
            return Response(result.body, status=200)
        elif result.is_error():
            return Response({"error": result.errors}, status=500)

    @action(detail=True, methods=["post"], url_path="join-queue")
    def join_queue(self, request, pk=None):
        email = request.data.get("email")
        user = get_object_or_404(User, email=email)

        try:
            restaurant = Restaurant.objects.get(place_id=pk)
        except Restaurant.DoesNotExist:
            return Response(
                {"error": f"Restaurant with place_id: {pk} does not exist"}, status=404
            )

        party_size = request.data.get("party_size", 1)

        if party_size <= 0:
            return Response(
                {"error": "Party size must be a positive integer"}, status=400
            )

        if Queue.objects.filter(restaurant=restaurant, user=user).exists():
            return Response(
                {"error": f"User is already in the queue for {restaurant.name}"},
                status=400,
            )

        if user.is_seated:
            return Response(
                {"error": "User is already seated at a restaurant"}, status=400
            )

        if restaurant.available_seats >= party_size:
            restaurant.available_seats -= party_size
            restaurant.save()

            user.is_seated = True
            user.save()

            return Response(
                {"success": f"You can directly go and sit at {restaurant.name}"},
                status=200,
            )
        else:
            queue_entry = Queue.objects.create(
                restaurant=restaurant, user=user, party_size=party_size
            )
            position = (
                Queue.objects.filter(
                    restaurant=restaurant, joined_at__lt=queue_entry.joined_at
                ).aggregate(sum=Sum("party_size"))["sum"]
                or 0
            )
            position += 1
            return Response(
                {
                    "success": f"You have joined the queue.",
                    "position": position,
                },
                status=200,
            )

    @action(detail=True, methods=["get"], url_path="queue-size")
    def get_queue_size(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(place_id=pk)
        except Restaurant.DoesNotExist:
            return Response(
                {"error": f"Restaurant with place_id: {pk} does not exist"}, status=404
            )

        queue_size = (
            Queue.objects.filter(restaurant=restaurant).aggregate(
                total=Sum("party_size")
            )["total"]
            or 0
        )

        return Response({"queue_size": queue_size}, status=200)

    @action(detail=True, methods=["post"], url_path="release-seats")
    def release_seats(self, request, pk=None):
        try:
            restaurant = Restaurant.objects.get(place_id=pk)
        except Restaurant.DoesNotExist:
            return Response(
                {"error": f"Restaurant with place_id: {pk} does not exist"}, status=404
            )

        seats_released = request.data.get("seats_released", 0)

        if seats_released <= 0:
            return Response(
                {"error": "Number of seats released must be a positive integer"},
                status=400,
            )

        restaurant.available_seats = min(
            restaurant.available_seats + seats_released, restaurant.total_seats
        )
        restaurant.save()

        queues = Queue.objects.filter(restaurant=restaurant).order_by("joined_at")

        seated_users = []
        for queue in queues:
            if queue.party_size <= restaurant.available_seats:
                restaurant.available_seats -= queue.party_size
                restaurant.save()

                user = get_object_or_404(User, email=queue.user.email)
                seated_users.append(user.email)

                user.is_seated = True
                user.save()

                queue.delete()
            else:
                break

        return Response(
            {
                "success": f"Released {seats_released} seats for {restaurant.name}. Checked queue for available seats.",
                "seated_users": seated_users,
            },
            status=200,
        )
