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
