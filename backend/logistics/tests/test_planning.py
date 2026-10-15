from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APITestCase

from logistics.models import Depot, Order, RoutePlan, RouteStop
from logistics.services.data_generator import GeneratorConfig, generate
from logistics.services.planning import plan_routes

END = date(2026, 9, 30)
SERVICE_DAY = date(2026, 10, 1)


def make_world():
    generate(
        GeneratorConfig(
            customers=80, drivers=4, history_days=3, future_days=1, orders_per_day=30, seed=11, end_date=END
        )
    )


class PlanRoutesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_world()

    def test_saved_plans_account_for_every_pending_order(self):
        pending = Order.objects.filter(service_date=SERVICE_DAY, status=Order.Status.PENDING)
        depot = Depot.objects.get()

        for solver in RoutePlan.Solver.values:
            with self.subTest(solver=solver):
                plan = plan_routes(SERVICE_DAY, solver, time_limit_s=1)
                stops = RouteStop.objects.filter(route__plan=plan)

                self.assertEqual(plan.orders_total, pending.count())
                self.assertEqual(stops.count(), plan.orders_assigned)
                self.assertEqual(plan.unassigned_orders.count(), plan.orders_total - plan.orders_assigned)
                routed = set(stops.values_list("order_id", flat=True))
                self.assertEqual(len(routed), stops.count(), "an order was routed twice")
                self.assertEqual(routed | set(plan.unassigned_orders.values_list("id", flat=True)),
                                 set(pending.values_list("id", flat=True)))
                for route in plan.routes.all():
                    self.assertEqual(route.path.num_points, route.stops.count() + 2)
                    self.assertEqual(route.path[0], route.path[-1])
                    self.assertAlmostEqual(route.path[0][0], depot.location.x)
                    self.assertLessEqual(route.max_load_bags, route.driver.capacity_bags)
                    self.assertEqual(sum(route.distance_m for route in plan.routes.all()), plan.total_distance_m)

    def test_ortools_beats_the_greedy_baseline(self):
        optimized = plan_routes(SERVICE_DAY, RoutePlan.Solver.ORTOOLS, time_limit_s=1)
        greedy = plan_routes(SERVICE_DAY, RoutePlan.Solver.GREEDY)

        self.assertGreaterEqual(optimized.orders_assigned, greedy.orders_assigned)
        if optimized.orders_assigned == greedy.orders_assigned:
            self.assertLess(optimized.total_distance_m, greedy.total_distance_m)

    def test_day_with_no_orders_saves_an_empty_plan(self):
        plan = plan_routes(date(2027, 1, 1), RoutePlan.Solver.ORTOOLS, time_limit_s=1)

        self.assertEqual(plan.orders_total, 0)
        self.assertEqual(plan.routes.count(), 0)

    def test_command_prints_the_comparison(self):
        out = StringIO()

        call_command("plan_routes", "--date", SERVICE_DAY.isoformat(), "--time-limit", "1", stdout=out)

        self.assertIn("OR-tools", out.getvalue())
        self.assertIn("Greedy dispatch", out.getvalue())
        self.assertIn("less driving", out.getvalue())
        self.assertEqual(RoutePlan.objects.count(), 2)


class RoutePlanApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        make_world()
        cls.plan = plan_routes(SERVICE_DAY, RoutePlan.Solver.ORTOOLS, time_limit_s=1)

    def test_list_filters_by_date(self):
        matching = self.client.get("/api/route-plans/", {"date": SERVICE_DAY.isoformat()}).json()
        other = self.client.get("/api/route-plans/", {"date": "2027-01-01"}).json()

        self.assertEqual([plan["id"] for plan in matching], [self.plan.id])
        self.assertEqual(matching[0]["drivers_used"], self.plan.routes.count())
        self.assertEqual(other, [])

    def test_detail_returns_routes_as_geojson_with_ordered_stops(self):
        body = self.client.get(f"/api/route-plans/{self.plan.id}/").json()

        routes = body["routes"]
        self.assertEqual(routes["type"], "FeatureCollection")
        self.assertEqual(len(routes["features"]), self.plan.routes.count())
        for feature in routes["features"]:
            self.assertEqual(feature["geometry"]["type"], "LineString")
            stops = feature["properties"]["stops"]
            self.assertEqual([s["sequence"] for s in stops], list(range(1, len(stops) + 1)))
            for s in stops:
                self.assertTrue(s["window_start"] <= s["arrival"] <= s["window_end"])
