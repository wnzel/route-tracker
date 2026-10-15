from datetime import date

from rest_framework.test import APITestCase

from logistics.models import Customer, Order, Zone
from logistics.services.data_generator import GeneratorConfig, generate

END = date(2026, 9, 30)
TOMORROW = date(2026, 10, 1)


class ApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        generate(
            GeneratorConfig(
                customers=50, drivers=2, history_days=7, future_days=2, orders_per_day=25, seed=3, end_date=END
            )
        )

    def test_zones_are_geojson_polygons_with_customer_counts(self):
        response = self.client.get("/api/zones/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["type"], "FeatureCollection")
        self.assertEqual(len(body["features"]), Zone.objects.count())
        self.assertEqual(body["features"][0]["geometry"]["type"], "Polygon")
        total = sum(feature["properties"]["customer_count"] for feature in body["features"])
        self.assertEqual(total, Customer.objects.count())

    def test_orders_filter_by_date(self):
        response = self.client.get("/api/orders/", {"date": TOMORROW.isoformat(), "page_size": 2000})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], Order.objects.filter(service_date=TOMORROW).count())
        self.assertTrue(body["features"])
        for feature in body["features"]:
            self.assertEqual(feature["properties"]["service_date"], TOMORROW.isoformat())
            self.assertEqual(feature["properties"]["status"], "pending")
            self.assertEqual(feature["geometry"]["type"], "Point")

    def test_orders_filter_by_zone_and_kind(self):
        zone = Zone.objects.order_by("name").first()

        response = self.client.get("/api/orders/", {"zone": zone.name, "kind": "pickup", "page_size": 2000})

        expected = Order.objects.filter(customer__zone=zone, kind=Order.Kind.PICKUP).count()
        self.assertEqual(response.json()["count"], expected)
        for feature in response.json()["features"]:
            self.assertEqual(feature["properties"]["zone"], zone.name)
            self.assertEqual(feature["properties"]["kind"], "pickup")

    def test_bad_date_is_a_400(self):
        response = self.client.get("/api/orders/", {"date": "10/01/2026"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("date", response.json())

    def test_drivers_and_depots_are_listed(self):
        self.assertEqual(len(self.client.get("/api/drivers/").json()), 2)
        depots = self.client.get("/api/depots/").json()
        self.assertEqual(len(depots["features"]), 1)
