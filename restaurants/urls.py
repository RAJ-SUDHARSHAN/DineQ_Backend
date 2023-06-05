from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import NearbyRestaurantsAPIView, RestaurantViewSet, login, register

router = DefaultRouter()
router.register(r"restaurants", RestaurantViewSet, basename="restaurant")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "nearby-restaurants/",
        NearbyRestaurantsAPIView.as_view(),
        name="nearby-restaurants",
    ),
    path("register/", register, name="register"),
    path("login/", login, name="login"),
]
