from django.contrib.gis.db import models


class Depot(models.Model):
    """Where drivers start and end their shifts."""

    name = models.CharField(max_length=100)
    location = models.PointField(srid=4326)

    def __str__(self):
        return self.name


class Zone(models.Model):
    """A service area used for grouping orders and forecasting volume."""

    name = models.CharField(max_length=50, unique=True)
    boundary = models.PolygonField(srid=4326)

    def __str__(self):
        return self.name


class Customer(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    location = models.PointField(srid=4326)
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, related_name="customers")

    def __str__(self):
        return self.name


class Driver(models.Model):
    """A delivery valet with a vehicle capacity and a shift."""

    name = models.CharField(max_length=100)
    depot = models.ForeignKey(Depot, on_delete=models.CASCADE, related_name="drivers")
    capacity_bags = models.PositiveSmallIntegerField()
    shift_start = models.TimeField()
    shift_end = models.TimeField()
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(shift_end__gt=models.F("shift_start")),
                name="driver_shift_end_after_start",
            ),
        ]

    def __str__(self):
        return self.name


class Order(models.Model):
    class Kind(models.TextChoices):
        PICKUP = "pickup", "Pickup"
        DELIVERY = "delivery", "Delivery"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="orders")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    service_date = models.DateField()
    window_start = models.TimeField()
    window_end = models.TimeField()
    bags = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["service_date", "status"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(window_end__gt=models.F("window_start")),
                name="order_window_end_after_start",
            ),
            models.CheckConstraint(condition=models.Q(bags__gte=1), name="order_bags_positive"),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} for {self.customer} on {self.service_date}"


class RoutePlan(models.Model):
    """One solver run for one service day."""

    class Solver(models.TextChoices):
        ORTOOLS = "ortools", "OR-tools"
        GREEDY = "greedy", "Greedy dispatch"

    service_date = models.DateField(db_index=True)
    solver = models.CharField(max_length=10, choices=Solver.choices)
    orders_total = models.PositiveIntegerField()
    orders_assigned = models.PositiveIntegerField()
    total_distance_m = models.PositiveIntegerField()
    solve_ms = models.PositiveIntegerField()
    unassigned_orders = models.ManyToManyField(Order, related_name="+", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_solver_display()} plan for {self.service_date}"


class Route(models.Model):
    plan = models.ForeignKey(RoutePlan, on_delete=models.CASCADE, related_name="routes")
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name="routes")
    start_time = models.TimeField()
    end_time = models.TimeField()
    distance_m = models.PositiveIntegerField()
    start_load_bags = models.PositiveSmallIntegerField()
    max_load_bags = models.PositiveSmallIntegerField()
    path = models.LineStringField(srid=4326)  # depot, each stop in order, depot

    class Meta:
        ordering = ["driver_id"]
        constraints = [models.UniqueConstraint(fields=["plan", "driver"], name="one_route_per_driver_per_plan")]


class RouteStop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="stops")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="route_stops")
    sequence = models.PositiveSmallIntegerField()
    arrival = models.TimeField()
    load_after_bags = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["sequence"]
        constraints = [models.UniqueConstraint(fields=["route", "sequence"], name="unique_stop_sequence")]
