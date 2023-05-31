from django.contrib.gis.db import models

class Restaurant(models.Model):
    name = models.CharField(max_length=255)
    place_id = models.CharField(max_length=255, unique=True)
    location = models.PointField()
    address = models.CharField(max_length=300)
    description = models.TextField(blank=True, null=True)
    verified = models.BooleanField(default=False)
    geo_fence_radius = models.IntegerField(default=5000)

    def __str__(self):
        return self.name


'''
Sample data entry to db
INSERT INTO restaurants_restaurant (name, place_id, location, address, verified, geo_fence_radius)
VALUES (
  'Club Rodeo Rio',
  'ChIJ127sjWTLj4AR_UwVXhjwYKA',
  ST_SetSRID(ST_MakePoint(-121.9083684, 37.3413231), 4326),
  '610 Coleman Avenue, San Jose',
  TRUE,
  5000
);
'''