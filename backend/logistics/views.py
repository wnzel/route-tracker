from datetime import date

from django.db.models import Count, Prefetch
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework_gis.pagination import GeoJsonPagination

from .models import Customer, Depot, Driver, Order, Route, RoutePlan, RouteStop, Zone
from .serializers import (
    CustomerSerializer,
    DepotSerializer,
    DriverSerializer,
    OrderSerializer,
    RoutePlanDetailSerializer,
    RoutePlanSummarySerializer,
    ZoneSerializer,
)


class FeaturePagination(GeoJsonPagination):
    page_size = 500
    page_size_query_param = "page_size"
    max_page_size = 2000


def parse_date(value, param):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError({param: "Use the YYYY-MM-DD format."})


class DepotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Depot.objects.order_by("id")
    serializer_class = DepotSerializer
    pagination_class = None


class ZoneViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Zone.objects.annotate(customer_count=Count("customers")).order_by("name")
    serializer_class = ZoneSerializer
    pagination_class = None


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CustomerSerializer
    pagination_class = FeaturePagination

    def get_queryset(self):
        queryset = Customer.objects.select_related("zone").order_by("id")
        zone = self.request.query_params.get("zone")
        if zone:
            queryset = queryset.filter(zone__name=zone)
        return queryset


class DriverViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Driver.objects.order_by("id")
    serializer_class = DriverSerializer
    pagination_class = None


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """Orders as GeoJSON. Filter with ?date=, ?status=, ?kind=, and ?zone=."""

    serializer_class = OrderSerializer
    pagination_class = FeaturePagination

    def get_queryset(self):
        params = self.request.query_params
        queryset = Order.objects.select_related("customer", "customer__zone").order_by(
            "service_date", "window_start", "id"
        )
        if "date" in params:
            queryset = queryset.filter(service_date=parse_date(params["date"], "date"))
        for field in ("status", "kind"):
            if field in params:
                queryset = queryset.filter(**{field: params[field]})
        if "zone" in params:
            queryset = queryset.filter(customer__zone__name=params["zone"])
        return queryset


class RoutePlanViewSet(viewsets.ReadOnlyModelViewSet):
    """Saved solver runs. The list is a summary; a single plan includes every route as GeoJSON."""

    def get_queryset(self):
        queryset = RoutePlan.objects.annotate(drivers_used=Count("routes"))
        if "date" in self.request.query_params:
            queryset = queryset.filter(service_date=parse_date(self.request.query_params["date"], "date"))
        if self.action == "retrieve":
            stops = RouteStop.objects.select_related("order", "order__customer")
            routes = Route.objects.select_related("driver").prefetch_related(Prefetch("stops", queryset=stops))
            queryset = queryset.prefetch_related(Prefetch("routes", queryset=routes), "unassigned_orders")
        return queryset.order_by("-created_at")

    def get_serializer_class(self):
        return RoutePlanDetailSerializer if self.action == "retrieve" else RoutePlanSummarySerializer
