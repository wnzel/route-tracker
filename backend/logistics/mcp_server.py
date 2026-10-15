"""MCP server so an AI assistant can plan routes, read plans, and forecast volume.

The tools wrap the same services the REST API uses. They are plain sync
functions: the MCP SDK runs sync tools on a worker thread, which keeps Django's
ORM out of the async event loop. Each call closes its thread's database
connection when it finishes.

Run it locally over stdio for Claude Desktop or Claude Code, or over
Streamable HTTP behind a bearer token for remote clients:

    python manage.py mcp_server
    python manage.py mcp_server --transport http --port 8001
"""

from __future__ import annotations

import functools
import hmac
import json
from datetime import date, datetime, time
from typing import Annotated, Any, Literal

from django.db import close_old_connections
from django.db.models import Prefetch
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from logistics.models import Driver, Order, Route, RoutePlan, RouteStop
from logistics.services import forecasting
from logistics.services.planning import plan_routes as run_planner

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
CREATES_PLANS = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)

INSTRUCTIONS = """\
Route Tracker plans pickup and delivery routes for a laundry service in metro Phoenix.
Drivers leave one depot, visit customers inside two-hour time windows, and carry a
limited number of bags. Two solvers exist: "ortools" (optimized) and "greedy"
(a dispatcher-style baseline). All data is simulated.

Start with route_tracker_list_service_days to see which days have pending orders
and saved plans. Read saved plans with route_tracker_get_plan and
route_tracker_get_route. Only call route_tracker_plan_routes when a day has no plan
or the user asks to re-plan; it takes several seconds and saves a new plan.
Distances are kilometers and times are local (America/Phoenix).
"""

ServiceDate = Annotated[date, Field(description="Service day as YYYY-MM-DD, for example 2026-10-19.")]
SolverName = Annotated[
    Literal["ortools", "greedy"],
    Field(description='"ortools" for the optimized plan, "greedy" for the dispatcher-style baseline.'),
]


def to_json(value: Any) -> Any:
    """Dates and times as ISO strings so every tool result is plain JSON."""
    if isinstance(value, (date, datetime, time)):
        return value.isoformat(timespec="minutes") if isinstance(value, time) else value.isoformat()
    if isinstance(value, dict):
        return {key: to_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json(item) for item in value]
    return value


def km(meters: int) -> float:
    return round(meters / 1000, 1)


def percent_saved(optimized: RoutePlan, baseline: RoutePlan) -> float | None:
    """Total distance saved, or distance per order when the plans serve different counts."""
    if not optimized.orders_assigned or not baseline.orders_assigned or not baseline.total_distance_m:
        return None
    if optimized.orders_assigned == baseline.orders_assigned:
        return round(100 * (1 - optimized.total_distance_m / baseline.total_distance_m), 1)
    per_order = optimized.total_distance_m / optimized.orders_assigned
    baseline_per_order = baseline.total_distance_m / baseline.orders_assigned
    return round(100 * (1 - per_order / baseline_per_order), 1)


def newest_plan(service_date: date, solver: str) -> RoutePlan:
    plan = RoutePlan.objects.filter(service_date=service_date, solver=solver).order_by("-created_at", "-id").first()
    if plan is None:
        raise ToolError(
            f"No {solver} plan for {service_date} yet. Call route_tracker_plan_routes with "
            f"service_date={service_date} and solver={solver} to create one."
        )
    return plan


def plan_totals(plan: RoutePlan) -> dict:
    return {
        "plan_id": plan.id,
        "service_date": plan.service_date,
        "solver": plan.solver,
        "orders_total": plan.orders_total,
        "orders_served": plan.orders_assigned,
        "drivers_used": plan.routes.count(),
        "total_km": km(plan.total_distance_m),
        "solve_seconds": round(plan.solve_ms / 1000, 2),
        "created_at": plan.created_at,
    }


# --- Tools ----------------------------------------------------------------------------------------


def list_service_days() -> list[dict[str, Any]]:
    """List every day with pending orders, its order count, and the newest plan ID from each solver.

    Start here to find dates to ask about. A day with an empty "plans" object has not been
    planned yet.
    """
    days = Order.objects.filter(status=Order.Status.PENDING).values_list("service_date", flat=True).distinct()
    result = []
    for service_date in sorted(set(days)):
        plans = {}
        for solver in RoutePlan.Solver.values:
            plan = RoutePlan.objects.filter(service_date=service_date, solver=solver).order_by("-created_at", "-id").first()
            if plan:
                plans[solver] = plan.id
        pending = Order.objects.filter(service_date=service_date, status=Order.Status.PENDING).count()
        result.append({"service_date": service_date, "pending_orders": pending, "plans": plans})
    return to_json(result)


def plan_routes(
    service_date: ServiceDate,
    solver: Annotated[
        Literal["ortools", "greedy", "both"],
        Field(description='Which solver to run. "both" also reports how much less driving OR-tools needs.'),
    ] = "both",
    time_limit_seconds: Annotated[float, Field(ge=1, le=30, description="OR-tools search time, 1 to 30 seconds.")] = 5,
) -> dict[str, Any]:
    """Plan driver routes for one day's pending orders and save the plan.

    OR-tools takes about time_limit_seconds; greedy is instant. Each call saves new plans,
    so read existing ones with route_tracker_get_plan instead of re-planning.
    """
    if not Order.objects.filter(service_date=service_date, status=Order.Status.PENDING).exists():
        raise ToolError(f"{service_date} has no pending orders. Call route_tracker_list_service_days for valid dates.")
    solvers = RoutePlan.Solver.values if solver == "both" else [solver]
    plans = {name: run_planner(service_date, name, time_limit_s=time_limit_seconds) for name in solvers}
    result: dict[str, Any] = {"plans": [plan_totals(plan) for plan in plans.values()]}
    if len(plans) == 2:
        result["ortools_percent_less_driving"] = percent_saved(plans["ortools"], plans["greedy"])
    return to_json(result)


def get_plan(service_date: ServiceDate, solver: SolverName = "ortools") -> dict[str, Any]:
    """Get the newest saved plan for a day: totals, each driver's route summary, and unassigned orders.

    Each route lists the driver, number of stops, distance, departure and return times, and the
    most bags on board compared with capacity. Use route_tracker_get_route for one driver's stops.
    """
    plan = newest_plan(service_date, solver)
    routes = plan.routes.select_related("driver").prefetch_related("stops")
    result = plan_totals(plan)
    result["routes"] = [
        {
            "driver_id": route.driver_id,
            "driver": route.driver.name,
            "stops": route.stops.count(),
            "km": km(route.distance_m),
            "departs": route.start_time,
            "returns": route.end_time,
            "max_bags_on_board": route.max_load_bags,
            "capacity_bags": route.driver.capacity_bags,
        }
        for route in routes
    ]
    result["unassigned_order_ids"] = list(plan.unassigned_orders.values_list("id", flat=True))
    return to_json(result)


def get_route(
    service_date: ServiceDate,
    driver: Annotated[str, Field(min_length=1, description='Driver name or ID, for example "Dana Lopez" or "4".')],
    solver: SolverName = "ortools",
) -> dict[str, Any]:
    """List one driver's stops in order, with arrival time, time window, kind, bags, and load after each stop."""
    plan = newest_plan(service_date, solver)
    stops = RouteStop.objects.select_related("order__customer__zone")
    routes = plan.routes.select_related("driver").prefetch_related(Prefetch("stops", queryset=stops))
    needle = driver.strip()
    matches = [r for r in routes if needle == str(r.driver_id) or needle.lower() in r.driver.name.lower()]
    if not matches:
        names = ", ".join(f"{r.driver.name} ({r.driver_id})" for r in routes) or "none"
        raise ToolError(f'No driver matching "{driver}" has a route in this plan. Drivers with routes: {names}.')
    if len(matches) > 1:
        names = ", ".join(f"{r.driver.name} ({r.driver_id})" for r in matches)
        raise ToolError(f'"{driver}" matches more than one driver: {names}. Pass the driver ID instead.')
    route: Route = matches[0]
    return to_json(
        {
            "plan_id": plan.id,
            "driver_id": route.driver_id,
            "driver": route.driver.name,
            "capacity_bags": route.driver.capacity_bags,
            "departs": route.start_time,
            "returns": route.end_time,
            "km": km(route.distance_m),
            "leaves_depot_with_bags": route.start_load_bags,
            "stops": [
                {
                    "sequence": stop.sequence,
                    "order_id": stop.order_id,
                    "customer": stop.order.customer.name,
                    "zone": stop.order.customer.zone.name if stop.order.customer.zone else None,
                    "kind": stop.order.kind,
                    "bags": stop.order.bags,
                    "window": f"{stop.order.window_start:%H:%M}-{stop.order.window_end:%H:%M}",
                    "arrives": stop.arrival,
                    "bags_on_board_after": stop.load_after_bags,
                }
                for stop in route.stops.all()
            ],
        }
    )


def compare_solvers(service_date: ServiceDate) -> dict[str, Any]:
    """Compare the newest OR-tools and greedy plans for a day: orders served, drivers, distance, and percent saved."""
    optimized, baseline = newest_plan(service_date, "ortools"), newest_plan(service_date, "greedy")
    return to_json(
        {
            "service_date": service_date,
            "ortools": plan_totals(optimized),
            "greedy": plan_totals(baseline),
            "ortools_percent_less_driving": percent_saved(optimized, baseline),
            "extra_orders_served_by_ortools": optimized.orders_assigned - baseline.orders_assigned,
        }
    )


def forecast_volume(
    start: Annotated[
        date | None, Field(description="First forecast day as YYYY-MM-DD. Omit to start the day after history ends.")
    ] = None,
    days: Annotated[int, Field(ge=1, le=28, description="How many days to forecast, 1 to 28.")] = 7,
    zone: Annotated[str | None, Field(description='Zone name such as "B2". Omit for every zone.')] = None,
) -> dict[str, Any]:
    """Forecast daily order volume city-wide and per zone, next to orders already booked.

    Also returns the backtest: forecast error (WAPE) over the last eight weeks for the model,
    two simple baselines, and the noise floor a perfect model would still have.
    """
    try:
        result = forecasting.forecast(start, days)
    except ValueError as error:
        raise ToolError(str(error)) from error
    if zone is not None:
        zones = [z for z in result["zones"] if z["zone"].lower() == zone.strip().lower()]
        if not zones:
            names = ", ".join(z["zone"] for z in result["zones"])
            raise ToolError(f'Unknown zone "{zone}". Zones are: {names}.')
        result["zones"] = zones
    return to_json(result)


def find_order(order_id: Annotated[int, Field(ge=1, description="Order ID, for example 412.")]) -> dict[str, Any]:
    """Look up an order: customer, zone, kind, bags, window, status, and its stop in the newest OR-tools plan."""
    order = Order.objects.select_related("customer__zone").filter(pk=order_id).first()
    if order is None:
        raise ToolError(f"No order {order_id}. Order IDs come from route_tracker_get_route or route_tracker_get_plan.")
    result: dict[str, Any] = {
        "order_id": order.id,
        "customer": order.customer.name,
        "address": order.customer.address,
        "zone": order.customer.zone.name if order.customer.zone else None,
        "kind": order.kind,
        "bags": order.bags,
        "service_date": order.service_date,
        "window": f"{order.window_start:%H:%M}-{order.window_end:%H:%M}",
        "status": order.status,
        "scheduled_stop": None,
    }
    plan = RoutePlan.objects.filter(service_date=order.service_date, solver="ortools").order_by("-created_at", "-id").first()
    if plan:
        stop = RouteStop.objects.select_related("route__driver").filter(route__plan=plan, order=order).first()
        if stop:
            result["scheduled_stop"] = {
                "plan_id": plan.id,
                "driver": stop.route.driver.name,
                "sequence": stop.sequence,
                "arrives": stop.arrival,
            }
        elif plan.unassigned_orders.filter(pk=order.pk).exists():
            result["scheduled_stop"] = {"plan_id": plan.id, "unassigned": True}
    return to_json(result)


TOOLS = [
    ("route_tracker_list_service_days", list_service_days, READ_ONLY),
    ("route_tracker_plan_routes", plan_routes, CREATES_PLANS),
    ("route_tracker_get_plan", get_plan, READ_ONLY),
    ("route_tracker_get_route", get_route, READ_ONLY),
    ("route_tracker_compare_solvers", compare_solvers, READ_ONLY),
    ("route_tracker_forecast_volume", forecast_volume, READ_ONLY),
    ("route_tracker_find_order", find_order, READ_ONLY),
]


def closes_db_connection(fn):
    @functools.wraps(fn)
    def run(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        finally:
            # Tools run on a worker thread with its own database connection; don't leak it.
            close_old_connections()

    return run


def build_server() -> MCPServer:
    server = MCPServer("route_tracker_mcp", title="Route Tracker", instructions=INSTRUCTIONS, version="0.4.0")
    for name, fn, annotations in TOOLS:
        server.tool(name=name, annotations=annotations, structured_output=True)(closes_db_connection(fn))
    return server


# --- HTTP auth ------------------------------------------------------------------------------------


class BearerTokenMiddleware:
    """Reject HTTP requests that don't carry `Authorization: Bearer <token>`.

    A single shared token fits a personal or team deployment. For per-user access, swap this
    for the SDK's OAuth support (MCPServer(token_verifier=..., auth=...)).
    """

    def __init__(self, app, token: str):
        self.app = app
        self.expected = f"Bearer {token}".encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            supplied = dict(scope.get("headers") or []).get(b"authorization", b"")
            if not hmac.compare_digest(supplied, self.expected):
                body = json.dumps({"error": "Missing or invalid bearer token."}).encode()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"www-authenticate", b"Bearer"),
                            (b"content-length", str(len(body)).encode()),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)
