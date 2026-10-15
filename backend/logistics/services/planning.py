"""Turn a day's pending orders into saved route plans."""

from __future__ import annotations

from datetime import date, time

from django.contrib.gis.geos import LineString
from django.db import transaction

from logistics.models import Depot, Driver, Order, Route, RoutePlan, RouteStop
from logistics.services import routing


def to_seconds(value: time) -> int:
    return value.hour * 3600 + value.minute * 60 + value.second


def to_time(seconds: int) -> time:
    seconds = min(seconds, 24 * 3600 - 1)
    return time(seconds // 3600, seconds % 3600 // 60, seconds % 60)


def build_problem(service_date: date) -> tuple[routing.Problem, list[Order], list[Driver], Depot]:
    depot = Depot.objects.order_by("id").first()
    if depot is None:
        raise ValueError("No depot found. Run generate_data first.")
    orders = list(
        Order.objects.filter(service_date=service_date, status=Order.Status.PENDING)
        .select_related("customer")
        .order_by("id")
    )
    drivers = list(Driver.objects.filter(active=True, depot=depot).order_by("id"))
    problem = routing.Problem(
        depot=(depot.location.x, depot.location.y),
        stops=[
            routing.Stop(
                order_id=order.id,
                lon=order.customer.location.x,
                lat=order.customer.location.y,
                kind=order.kind,
                bags=order.bags,
                window_start=to_seconds(order.window_start),
                window_end=to_seconds(order.window_end),
            )
            for order in orders
        ],
        vehicles=[
            routing.Vehicle(
                driver_id=driver.id,
                capacity=driver.capacity_bags,
                shift_start=to_seconds(driver.shift_start),
                shift_end=to_seconds(driver.shift_end),
            )
            for driver in drivers
        ],
    )
    return problem, orders, drivers, depot


def solve(problem: routing.Problem, solver: str, time_limit_s: float) -> routing.Solution:
    if solver == RoutePlan.Solver.ORTOOLS:
        return routing.solve_ortools(problem, time_limit_s=time_limit_s)
    if solver == RoutePlan.Solver.GREEDY:
        return routing.solve_greedy(problem)
    raise ValueError(f"Unknown solver: {solver}")


@transaction.atomic
def plan_routes(service_date: date, solver: str, time_limit_s: float = 5.0) -> RoutePlan:
    problem, orders, drivers, depot = build_problem(service_date)
    solution = solve(problem, solver, time_limit_s)

    violations = routing.check_solution(problem, solution)
    if violations:
        # The solver should never return a broken plan; refuse to save one if it does.
        raise RuntimeError(f"{solver} produced an invalid plan: {violations[:5]}")

    plan = RoutePlan.objects.create(
        service_date=service_date,
        solver=solver,
        orders_total=len(orders),
        orders_assigned=solution.assigned_count,
        total_distance_m=solution.total_distance_m,
        solve_ms=solution.solve_ms,
    )
    plan.unassigned_orders.set([orders[i] for i in solution.unassigned])

    drivers_by_id = {driver.id: driver for driver in drivers}
    depot_xy = (depot.location.x, depot.location.y)
    for result in solution.routes:
        stop_xy = [(problem.stops[i].lon, problem.stops[i].lat) for i in result.stops]
        route = Route.objects.create(
            plan=plan,
            driver=drivers_by_id[result.driver_id],
            start_time=to_time(result.start),
            end_time=to_time(result.end),
            distance_m=result.distance_m,
            start_load_bags=result.start_load,
            max_load_bags=result.max_load,
            path=LineString([depot_xy, *stop_xy, depot_xy], srid=4326),
        )
        RouteStop.objects.bulk_create(
            RouteStop(
                route=route,
                order=orders[i],
                sequence=position,
                arrival=to_time(arrival),
                load_after_bags=load,
            )
            for position, (i, arrival, load) in enumerate(
                zip(result.stops, result.arrivals, result.loads_after), start=1
            )
        )
    return plan
