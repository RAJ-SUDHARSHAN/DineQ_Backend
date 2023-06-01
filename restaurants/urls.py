from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import RestaurantViewSet, NearbyRestaurantsAPIView

router = DefaultRouter()
router.register(r'restaurants', RestaurantViewSet, basename='restaurant')

urlpatterns = [
    path('', include(router.urls)),
    path('nearby-restaurants/', NearbyRestaurantsAPIView.as_view(), name='nearby-restaurants'),
]
