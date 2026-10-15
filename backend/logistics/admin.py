from django.contrib.gis import admin

from .models import Customer, Depot, Driver, Order, Route, RoutePlan, RouteStop, Zone


@admin.register(Depot)
class DepotAdmin(admin.GISModelAdmin):
    list_display = ("name",)


@admin.register(Zone)
class ZoneAdmin(admin.GISModelAdmin):
    list_display = ("name",)


@admin.register(Customer)
class CustomerAdmin(admin.GISModelAdmin):
    list_display = ("name", "address", "zone")
    list_filter = ("zone",)
    search_fields = ("name", "address")


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("name", "depot", "capacity_bags", "shift_start", "shift_end", "active")
    list_filter = ("active", "depot")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "kind", "status", "service_date", "window_start", "window_end", "bags")
    list_filter = ("status", "kind", "service_date", "customer__zone")
    date_hierarchy = "service_date"
    list_select_related = ("customer",)


class RouteInline(admin.TabularInline):
    model = Route
    fields = ("driver", "start_time", "end_time", "distance_m", "start_load_bags", "max_load_bags")
    readonly_fields = fields
    extra = 0
    can_delete = False


@admin.register(RoutePlan)
class RoutePlanAdmin(admin.ModelAdmin):
    list_display = ("id", "service_date", "solver", "orders_assigned", "orders_total", "total_distance_m", "solve_ms")
    list_filter = ("solver", "service_date")
    inlines = (RouteInline,)


class RouteStopInline(admin.TabularInline):
    model = RouteStop
    fields = ("sequence", "order", "arrival", "load_after_bags")
    readonly_fields = fields
    extra = 0
    can_delete = False


@admin.register(Route)
class RouteAdmin(admin.GISModelAdmin):
    list_display = ("id", "plan", "driver", "distance_m", "start_time", "end_time")
    list_filter = ("plan__solver",)
    inlines = (RouteStopInline,)
