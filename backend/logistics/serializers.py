from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer, GeometrySerializerMethodField

from .models import Customer, Depot, Driver, Order, Zone


class DepotSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Depot
        geo_field = "location"
        fields = ("id", "name")


class ZoneSerializer(GeoFeatureModelSerializer):
    customer_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Zone
        geo_field = "boundary"
        fields = ("id", "name", "customer_count")


class CustomerSerializer(GeoFeatureModelSerializer):
    zone = serializers.SlugRelatedField(slug_field="name", read_only=True)

    class Meta:
        model = Customer
        geo_field = "location"
        fields = ("id", "name", "address", "zone")


class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = ("id", "name", "depot", "capacity_bags", "shift_start", "shift_end", "active")


class OrderSerializer(GeoFeatureModelSerializer):
    # Orders are drawn on the map at the customer's location.
    location = GeometrySerializerMethodField()
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    zone = serializers.CharField(source="customer.zone.name", read_only=True, allow_null=True)

    class Meta:
        model = Order
        geo_field = "location"
        fields = (
            "id",
            "customer",
            "customer_name",
            "zone",
            "kind",
            "status",
            "service_date",
            "window_start",
            "window_end",
            "bags",
        )

    def get_location(self, obj):
        return obj.customer.location
