from datetime import date, time

from django.contrib.gis.geos import Point
from django.db import IntegrityError
from django.test import TestCase

from logistics.models import Customer, Depot, Driver, Order


class ConstraintTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="Test Customer", address="1 Central Ave", location=Point(-112.07, 33.45, srid=4326)
        )

    def make_order(self, **overrides):
        values = dict(
            customer=self.customer,
            kind=Order.Kind.PICKUP,
            service_date=date(2026, 10, 1),
            window_start=time(9),
            window_end=time(11),
            bags=2,
        )
        values.update(overrides)
        return Order.objects.create(**values)

    def test_valid_order_saves(self):
        self.assertEqual(self.make_order().status, Order.Status.PENDING)

    def test_window_must_end_after_it_starts(self):
        with self.assertRaises(IntegrityError):
            self.make_order(window_start=time(11), window_end=time(9))

    def test_order_needs_at_least_one_bag(self):
        with self.assertRaises(IntegrityError):
            self.make_order(bags=0)

    def test_driver_shift_must_end_after_it_starts(self):
        depot = Depot.objects.create(name="Depot", location=Point(-112.07, 33.45, srid=4326))
        with self.assertRaises(IntegrityError):
            Driver.objects.create(
                name="Driver", depot=depot, capacity_bags=30, shift_start=time(15), shift_end=time(7)
            )
