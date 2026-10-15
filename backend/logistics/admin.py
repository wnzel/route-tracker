from django.contrib.gis import admin

from .models import Customer, Depot, Driver, Order, Zone


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
