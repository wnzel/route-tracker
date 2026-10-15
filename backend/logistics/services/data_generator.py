"""Synthetic pickup and delivery data for a laundry service in metro Phoenix.

Everything is driven by one seeded RNG, so the same config always produces the
same customers, drivers, and order history. The history has a weekly pattern
and slow growth so the forecasting step has something real to learn from.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date, time, timedelta

from django.contrib.gis.geos import Point, Polygon
from django.db import transaction
from django.utils import timezone

from logistics.models import Customer, Depot, Driver, Order, Zone

# Rough Phoenix metro bounding box in WGS84 (lon/lat).
WEST, EAST, SOUTH, NORTH = -112.30, -111.80, 33.35, 33.65
GRID_ROWS, GRID_COLS = 3, 4
DEPOT_NAME, DEPOT_LON, DEPOT_LAT = "Central Depot", -112.0740, 33.4484  # downtown Phoenix

# Laundry pickups peak at the start of the week and dip on weekends (Mon..Sun).
WEEKDAY_FACTOR = (1.35, 1.0, 1.0, 1.1, 1.2, 0.7, 0.5)
WINDOW_START_HOURS = (7, 9, 11, 13, 15, 17)  # two-hour windows, 7am to 7pm
WINDOW_HOURS = 2
DAILY_GROWTH = 0.001  # about 0.1% more orders each day
PICKUP_SHARE = 0.6
CANCEL_RATE = 0.03
SHIFTS = ((time(7), time(15)), (time(11), time(19)))
CAPACITIES = (30, 35, 40)

FIRST_NAMES = (
    "Alex", "Brianna", "Carlos", "Dana", "Elena", "Faith", "Gabriel", "Hannah", "Isaac", "Jasmine",
    "Kevin", "Leah", "Marcus", "Nina", "Omar", "Priya", "Quinn", "Rosa", "Sam", "Tyler",
)
LAST_NAMES = (
    "Nguyen", "Garcia", "Smith", "Patel", "Johnson", "Lopez", "Kim", "Brown", "Martinez", "Davis",
    "Wilson", "Reyes", "Chen", "Hernandez", "Clark", "Lewis", "Torres", "Walker", "Young", "Ali",
)
STREETS = (
    "Camelback Rd", "Indian School Rd", "McDowell Rd", "Thomas Rd", "Osborn Rd", "Bethany Home Rd",
    "Glendale Ave", "Northern Ave", "Dunlap Ave", "Central Ave", "7th St", "16th St", "24th St",
    "44th St", "Scottsdale Rd",
)


@dataclass
class GeneratorConfig:
    customers: int = 400
    drivers: int = 8
    history_days: int = 120
    future_days: int = 7
    orders_per_day: float = 60.0  # average city-wide volume on a typical weekday
    seed: int = 42
    end_date: date | None = None  # last day of history; defaults to yesterday

    def last_history_day(self) -> date:
        # localdate() uses the Phoenix TIME_ZONE; the container clock itself is UTC.
        return self.end_date or timezone.localdate() - timedelta(days=1)


def poisson(rng: random.Random, lam: float) -> int:
    """Sample a Poisson count. Knuth's method for small rates, normal approximation above."""
    if lam <= 0:
        return 0
    if lam > 30:
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    limit, count, product = math.exp(-lam), 0, 1.0
    while True:
        product *= rng.random()
        if product <= limit:
            return count
        count += 1


def build_zones() -> list[Zone]:
    """Split the bounding box into a grid. Rows are lettered north to south, columns numbered west to east."""
    width = (EAST - WEST) / GRID_COLS
    height = (NORTH - SOUTH) / GRID_ROWS
    zones = []
    for row in range(GRID_ROWS):
        top = NORTH - row * height
        bottom = top - height
        for col in range(GRID_COLS):
            left = WEST + col * width
            right = left + width
            ring = ((left, bottom), (right, bottom), (right, top), (left, top), (left, bottom))
            zones.append(Zone(name=f"{'ABCDEFGH'[row]}{col + 1}", boundary=Polygon(ring, srid=4326)))
    return zones


def random_point_in(zone: Zone, rng: random.Random) -> Point:
    xmin, ymin, xmax, ymax = zone.boundary.extent
    # Stay a little inside the edges so every point is strictly within one zone.
    margin_x, margin_y = (xmax - xmin) * 0.01, (ymax - ymin) * 0.01
    lon = rng.uniform(xmin + margin_x, xmax - margin_x)
    lat = rng.uniform(ymin + margin_y, ymax - margin_y)
    return Point(round(lon, 6), round(lat, 6), srid=4326)


def clear_data() -> None:
    Order.objects.all().delete()
    Driver.objects.all().delete()
    Customer.objects.all().delete()
    Zone.objects.all().delete()
    Depot.objects.all().delete()


@transaction.atomic
def generate(config: GeneratorConfig, reset: bool = False) -> dict:
    if reset:
        clear_data()

    rng = random.Random(config.seed)

    depot = Depot.objects.create(name=DEPOT_NAME, location=Point(DEPOT_LON, DEPOT_LAT, srid=4326))
    zones = Zone.objects.bulk_create(build_zones())

    # Some neighborhoods are denser than others, so weight zones unevenly.
    zone_weights = [rng.uniform(0.4, 1.6) for _ in zones]
    customers = []
    for zone in rng.choices(zones, weights=zone_weights, k=config.customers):
        name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        address = f"{rng.randint(100, 9999)} {rng.choice(STREETS)}, Phoenix, AZ"
        customers.append(Customer(name=name, address=address, location=random_point_in(zone, rng), zone=zone))
    customers = Customer.objects.bulk_create(customers)

    drivers = []
    for i in range(config.drivers):
        shift_start, shift_end = SHIFTS[i % len(SHIFTS)]
        drivers.append(
            Driver(
                name=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                depot=depot,
                capacity_bags=rng.choice(CAPACITIES),
                shift_start=shift_start,
                shift_end=shift_end,
            )
        )
    Driver.objects.bulk_create(drivers)

    by_zone: dict[int, list[Customer]] = {zone.pk: [] for zone in zones}
    for customer in customers:
        by_zone[customer.zone_id].append(customer)

    end = config.last_history_day()
    start = end - timedelta(days=config.history_days - 1)
    total_days = config.history_days + config.future_days
    orders = []
    for offset in range(total_days):
        day = start + timedelta(days=offset)
        is_future = day > end
        daily_factor = WEEKDAY_FACTOR[day.weekday()] * (1 + DAILY_GROWTH) ** offset
        for members in by_zone.values():
            if not members:
                continue
            rate = config.orders_per_day * len(members) / len(customers) * daily_factor
            for _ in range(poisson(rng, rate)):
                start_hour = rng.choice(WINDOW_START_HOURS)
                if is_future:
                    status = Order.Status.PENDING
                elif rng.random() < CANCEL_RATE:
                    status = Order.Status.CANCELLED
                else:
                    status = Order.Status.COMPLETED
                orders.append(
                    Order(
                        customer=rng.choice(members),
                        kind=Order.Kind.PICKUP if rng.random() < PICKUP_SHARE else Order.Kind.DELIVERY,
                        status=status,
                        service_date=day,
                        window_start=time(start_hour),
                        window_end=time(start_hour + WINDOW_HOURS),
                        bags=rng.randint(1, 4),
                    )
                )
    Order.objects.bulk_create(orders, batch_size=2000)

    return {
        "zones": len(zones),
        "customers": len(customers),
        "drivers": len(drivers),
        "orders": len(orders),
        "history": (start, end),
        "future": (end + timedelta(days=1), end + timedelta(days=config.future_days)),
    }
