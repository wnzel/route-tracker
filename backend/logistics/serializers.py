from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer, GeometrySerializerMethodField

from .models import Customer, Depot, Driver, Order, Route, RoutePlan, RouteStop, Zone


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


class RouteStopSerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(source="order_id", read_only=True)
    kind = serializers.CharField(source="order.kind", read_only=True)
    bags = serializers.IntegerField(source="order.bags", read_only=True)
    customer_name = serializers.CharField(source="order.customer.name", read_only=True)
    window_start = serializers.TimeField(source="order.window_start", read_only=True)
    window_end = serializers.TimeField(source="order.window_end", read_only=True)

    class Meta:
        model = RouteStop
        fields = (
            "sequence",
            "order",
            "kind",
            "bags",
            "customer_name",
            "window_start",
            "window_end",
            "arrival",
            "load_after_bags",
        )


class RouteSerializer(GeoFeatureModelSerializer):
    driver_name = serializers.CharField(source="driver.name", read_only=True)
    capacity_bags = serializers.IntegerField(source="driver.capacity_bags", read_only=True)
    shift_start = serializers.TimeField(source="driver.shift_start", read_only=True)
    shift_end = serializers.TimeField(source="driver.shift_end", read_only=True)
    stops = RouteStopSerializer(many=True, read_only=True)

    class Meta:
        model = Route
        geo_field = "path"
        fields = (
            "id",
            "driver",
            "driver_name",
            "capacity_bags",
            "shift_start",
            "shift_end",
            "start_time",
            "end_time",
            "distance_m",
            "start_load_bags",
            "max_load_bags",
            "stops",
        )


class RoutePlanSummarySerializer(serializers.ModelSerializer):
    drivers_used = serializers.IntegerField(read_only=True)

    class Meta:
        model = RoutePlan
        fields = (
            "id",
            "service_date",
            "solver",
            "orders_total",
            "orders_assigned",
            "drivers_used",
            "total_distance_m",
            "solve_ms",
            "created_at",
        )


class RoutePlanDetailSerializer(RoutePlanSummarySerializer):
    routes = RouteSerializer(many=True, read_only=True)
    unassigned_orders = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta(RoutePlanSummarySerializer.Meta):
        fields = RoutePlanSummarySerializer.Meta.fields + ("unassigned_orders", "routes")
