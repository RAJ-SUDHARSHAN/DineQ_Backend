from django.urls import path
from . import views
from .views import NearbyRestaurantsAPIView

urlpatterns = [
    path('nearby-restaurants/', NearbyRestaurantsAPIView.as_view(), name='nearby-restaurants'),
]
