import json
from datetime import date

import anyio
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError

from logistics import mcp_server as tools
from logistics.models import Order, RoutePlan
from logistics.services.data_generator import GeneratorConfig, generate

END = date(2026, 9, 30)
SERVICE_DAY = date(2026, 10, 1)


def make_world(**overrides):
    config = dict(customers=90, drivers=4, history_days=35, future_days=2, orders_per_day=30, seed=21, end_date=END)
    config.update(overrides)
    generate(GeneratorConfig(**config))


class ToolTests(TestCase):
    """The tool functions, called directly."""

    @classmethod
    def setUpTestData(cls):
        make_world()

    def test_list_service_days_shows_pending_days_and_plans(self):
        tools.plan_routes(SERVICE_DAY, "greedy")

        days = tools.list_service_days()

        self.assertEqual([d["service_date"] for d in days], ["2026-10-01", "2026-10-02"])
        self.assertEqual(set(days[0]["plans"]), {"greedy"})
        self.assertEqual(days[1]["plans"], {})

    def test_reading_a_missing_plan_says_how_to_create_it(self):
        with self.assertRaisesMessage(ToolError, "Call route_tracker_plan_routes"):
            tools.get_plan(SERVICE_DAY)

    def test_plan_both_then_compare(self):
        result = tools.plan_routes(SERVICE_DAY, "both", time_limit_seconds=1)

        self.assertEqual([p["solver"] for p in result["plans"]], ["ortools", "greedy"])
        comparison = tools.compare_solvers(SERVICE_DAY)
        self.assertEqual(comparison["ortools_percent_less_driving"], result["ortools_percent_less_driving"])
        self.assertGreater(comparison["ortools_percent_less_driving"], 0)
        json.dumps(comparison)  # everything is plain JSON

    def test_planning_a_day_without_orders_is_refused(self):
        with self.assertRaisesMessage(ToolError, "no pending orders"):
            tools.plan_routes(date(2027, 3, 1), "greedy")

    def test_get_plan_and_route_by_name_or_id(self):
        tools.plan_routes(SERVICE_DAY, "greedy")
        plan = tools.get_plan(SERVICE_DAY, "greedy")
        first = plan["routes"][0]

        by_id = tools.get_route(SERVICE_DAY, str(first["driver_id"]), "greedy")
        by_name = tools.get_route(SERVICE_DAY, first["driver"].upper(), "greedy")

        self.assertEqual(by_id, by_name)
        self.assertEqual(len(by_id["stops"]), first["stops"])
        self.assertEqual([s["sequence"] for s in by_id["stops"]], list(range(1, first["stops"] + 1)))

    def test_unknown_driver_lists_the_drivers_on_the_plan(self):
        tools.plan_routes(SERVICE_DAY, "greedy")
        with self.assertRaisesMessage(ToolError, "Drivers with routes:"):
            tools.get_route(SERVICE_DAY, "nobody", "greedy")

    def test_find_order_reports_its_stop(self):
        tools.plan_routes(SERVICE_DAY, "ortools", time_limit_seconds=1)
        plan = RoutePlan.objects.get(solver="ortools")
        order = plan.routes.first().stops.first().order

        found = tools.find_order(order.id)

        self.assertEqual(found["scheduled_stop"]["sequence"], 1)
        self.assertEqual(found["service_date"], SERVICE_DAY.isoformat())
        with self.assertRaisesMessage(ToolError, "No order"):
            tools.find_order(10_000_000)

    def test_forecast_filters_to_one_zone(self):
        result = tools.forecast_volume(days=3, zone="b2")

        self.assertEqual([z["zone"] for z in result["zones"]], ["B2"])
        self.assertEqual(len(result["city"]), 3)
        with self.assertRaisesMessage(ToolError, "Zones are:"):
            tools.forecast_volume(zone="Z9")


class ProtocolTests(TransactionTestCase):
    """The real MCP protocol through the SDK's in-memory client.

    Tools run on a worker thread with their own database connection, so the data has to be
    committed, which is why this is a TransactionTestCase.
    """

    def setUp(self):
        make_world(customers=40, history_days=7, future_days=1, orders_per_day=15)

    def call(self, *requests):
        async def run():
            async with Client(tools.build_server()) as client:
                listed = await client.list_tools()
                results = [await client.call_tool(name, args) for name, args in requests]
                return listed.tools, results

        return anyio.run(run)

    def test_tools_are_listed_with_annotations_and_return_structured_json(self):
        listed, (days, missing) = self.call(
            ("route_tracker_list_service_days", {}),
            ("route_tracker_get_plan", {"service_date": SERVICE_DAY.isoformat()}),
        )

        by_name = {tool.name: tool for tool in listed}
        self.assertEqual(len(by_name), 7)
        self.assertTrue(all(name.startswith("route_tracker_") for name in by_name))
        self.assertFalse(by_name["route_tracker_plan_routes"].annotations.read_only_hint)
        self.assertTrue(by_name["route_tracker_get_plan"].annotations.read_only_hint)

        self.assertFalse(days.is_error)
        pending = Order.objects.filter(service_date=SERVICE_DAY, status=Order.Status.PENDING).count()
        self.assertEqual(days.structured_content["result"][0]["pending_orders"], pending)
        self.assertTrue(missing.is_error)
        self.assertIn("route_tracker_plan_routes", missing.content[0].text)

    def test_bad_arguments_are_rejected_before_the_tool_runs(self):
        _, (result,) = self.call(("route_tracker_plan_routes", {"service_date": "next tuesday"}))

        self.assertTrue(result.is_error)
        self.assertEqual(RoutePlan.objects.count(), 0)


class BearerTokenTests(SimpleTestCase):
    def request(self, headers):
        sent = []

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        async def send(message):
            sent.append(message)

        async def receive():
            return {"type": "http.request", "body": b""}

        middleware = tools.BearerTokenMiddleware(app, "s3cret")
        anyio.run(middleware, {"type": "http", "headers": headers}, receive, send)
        return sent[0]["status"]

    def test_accepts_the_right_token(self):
        self.assertEqual(self.request([(b"authorization", b"Bearer s3cret")]), 200)

    def test_rejects_a_missing_or_wrong_token(self):
        self.assertEqual(self.request([]), 401)
        self.assertEqual(self.request([(b"authorization", b"Bearer nope")]), 401)
