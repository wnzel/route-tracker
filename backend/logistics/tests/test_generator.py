from collections import Counter
from datetime import date
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from logistics.models import Customer, Depot, Driver, Order, Zone
from logistics.services.data_generator import GRID_COLS, GRID_ROWS, GeneratorConfig, generate

END = date(2026, 9, 30)


def small_config(**overrides):
    values = dict(
        customers=60,
        drivers=3,
        history_days=14,
        future_days=2,
        orders_per_day=20,
        seed=7,
        end_date=END,
    )
    values.update(overrides)
    return GeneratorConfig(**values)


def order_fingerprint():
    return list(
        Order.objects.order_by("service_date", "window_start", "customer__name", "kind", "bags").values_list(
            "customer__name", "service_date", "window_start", "kind", "bags", "status"
        )
    )


class GeneratorTests(TestCase):
    def test_creates_requested_counts(self):
        summary = generate(small_config())

        self.assertEqual(Depot.objects.count(), 1)
        self.assertEqual(Zone.objects.count(), GRID_ROWS * GRID_COLS)
        self.assertEqual(Customer.objects.count(), 60)
        self.assertEqual(Driver.objects.count(), 3)
        self.assertGreater(summary["orders"], 0)
        self.assertEqual(Order.objects.count(), summary["orders"])

    def test_same_seed_produces_same_orders(self):
        generate(small_config())
        first = order_fingerprint()

        generate(small_config(), reset=True)

        self.assertEqual(order_fingerprint(), first)

    def test_different_seed_produces_different_orders(self):
        generate(small_config())
        first = order_fingerprint()

        generate(small_config(seed=8), reset=True)

        self.assertNotEqual(order_fingerprint(), first)

    def test_customers_are_inside_their_zone(self):
        generate(small_config())

        for customer in Customer.objects.all():
            # PostGIS lookup, so this also checks the stored geometries line up.
            self.assertEqual(Zone.objects.get(boundary__contains=customer.location), customer.zone)

    def test_history_is_closed_and_future_is_pending(self):
        generate(small_config())

        self.assertFalse(Order.objects.filter(service_date__lte=END, status=Order.Status.PENDING).exists())
        self.assertFalse(
            Order.objects.filter(service_date__gt=END).exclude(status=Order.Status.PENDING).exists()
        )
        self.assertTrue(Order.objects.filter(service_date__gt=END).exists())

    def test_time_windows_are_two_hours_inside_the_service_day(self):
        generate(small_config())

        for start, end in Order.objects.values_list("window_start", "window_end"):
            self.assertEqual(end.hour - start.hour, 2)
            self.assertGreaterEqual(start.hour, 7)
            self.assertLessEqual(end.hour, 19)

    def test_mondays_are_busier_than_sundays(self):
        generate(small_config(history_days=56, orders_per_day=40))

        per_weekday = Counter(day.weekday() for day in Order.objects.values_list("service_date", flat=True))
        self.assertGreater(per_weekday[0], per_weekday[6] * 1.5)


class GenerateDataCommandTests(TestCase):
    def test_refuses_to_overwrite_without_reset(self):
        generate(small_config())

        with self.assertRaises(CommandError):
            call_command("generate_data", "--customers", "10", verbosity=0)

    def test_reset_replaces_existing_data(self):
        generate(small_config())

        call_command(
            "generate_data", "--customers", "10", "--drivers", "2", "--history-days", "3",
            "--future-days", "1", "--end-date", "2026-09-30", "--reset", stdout=StringIO(),
        )

        self.assertEqual(Customer.objects.count(), 10)
        self.assertEqual(Driver.objects.count(), 2)
        self.assertEqual(Depot.objects.count(), 1)
