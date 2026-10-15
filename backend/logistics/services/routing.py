"""Vehicle routing for mixed pickups and deliveries with capacities and time windows.

This module is plain Python with no database access, so the solvers can be tested
on small hand-built problems. Times are seconds after midnight and distances are
meters.

Load model: a driver leaves the depot carrying every delivery bag on their route,
drops bags at deliveries, and collects bags at pickups. The truck must stay within
capacity the whole way, so the order of stops matters, not just the total.
"""

from __future__ import annotations

import math
import time as clock
from dataclasses import dataclass, field

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

PICKUP = "pickup"
DELIVERY = "delivery"

SERVICE_SECONDS = 5 * 60  # time spent at each stop
SPEED_MPS = 11.0  # about 40 km/h average city driving
MAX_WAIT_SECONDS = 4 * 3600  # longest a driver may idle before a time window opens
DROP_PENALTY = 10_000_000  # cost of leaving an order unassigned, far above any detour

METERS_PER_DEGREE_LAT = 110_540
METERS_PER_DEGREE_LON_AT_EQUATOR = 111_320


@dataclass(frozen=True)
class Stop:
    order_id: int
    lon: float
    lat: float
    kind: str
    bags: int
    window_start: int
    window_end: int


@dataclass(frozen=True)
class Vehicle:
    driver_id: int
    capacity: int
    shift_start: int
    shift_end: int


@dataclass
class Problem:
    depot: tuple[float, float]  # (lon, lat)
    stops: list[Stop]
    vehicles: list[Vehicle]
    service_seconds: int = SERVICE_SECONDS
    speed_mps: float = SPEED_MPS

    def points(self) -> list[tuple[float, float]]:
        """Node 0 is the depot, node i is stops[i - 1]."""
        return [self.depot] + [(stop.lon, stop.lat) for stop in self.stops]


@dataclass
class RouteResult:
    driver_id: int
    stops: list[int]  # indexes into Problem.stops, in visiting order
    arrivals: list[int]  # service start time at each stop
    loads_after: list[int]  # bags on board after each stop
    start: int  # departure from the depot
    end: int  # return to the depot
    distance_m: int
    start_load: int

    @property
    def max_load(self) -> int:
        return max([self.start_load, *self.loads_after])


@dataclass
class Solution:
    solver: str
    routes: list[RouteResult]
    unassigned: list[int]  # indexes into Problem.stops
    solve_ms: int
    total_distance_m: int = field(init=False)

    def __post_init__(self):
        self.total_distance_m = sum(route.distance_m for route in self.routes)

    @property
    def assigned_count(self) -> int:
        return sum(len(route.stops) for route in self.routes)


def grid_distance_m(a: tuple[float, float], b: tuple[float, float]) -> int:
    """Manhattan distance in meters.

    Phoenix streets mostly run on a north-south / east-west grid, so driving
    distance is closer to |dx| + |dy| than to a straight line.
    """
    mean_lat = math.radians((a[1] + b[1]) / 2)
    dx = abs(a[0] - b[0]) * METERS_PER_DEGREE_LON_AT_EQUATOR * math.cos(mean_lat)
    dy = abs(a[1] - b[1]) * METERS_PER_DEGREE_LAT
    return round(dx + dy)


def distance_matrix(points: list[tuple[float, float]]) -> list[list[int]]:
    return [[grid_distance_m(a, b) for b in points] for a in points]


def travel_seconds(distance_m: int, speed_mps: float) -> int:
    return math.ceil(distance_m / speed_mps)


def route_distance(matrix: list[list[int]], stops: list[int]) -> int:
    nodes = [0] + [i + 1 for i in stops] + [0]
    return sum(matrix[a][b] for a, b in zip(nodes, nodes[1:]))


def loads_along(problem: Problem, stops: list[int]) -> tuple[int, list[int]]:
    """Return the starting load and the load after each stop."""
    load = sum(problem.stops[i].bags for i in stops if problem.stops[i].kind == DELIVERY)
    start_load, loads = load, []
    for i in stops:
        stop = problem.stops[i]
        load += stop.bags if stop.kind == PICKUP else -stop.bags
        loads.append(load)
    return start_load, loads


def simulate(problem: Problem, vehicle: Vehicle, stops: list[int], matrix: list[list[int]]) -> RouteResult | None:
    """Drive a fixed stop order as early as possible. Returns None if any constraint breaks."""
    start_load, loads = loads_along(problem, stops)
    if start_load > vehicle.capacity or any(load > vehicle.capacity for load in loads):
        return None

    now, node, arrivals = vehicle.shift_start, 0, []
    for i in stops:
        stop = problem.stops[i]
        now += travel_seconds(matrix[node][i + 1], problem.speed_mps)
        now = max(now, stop.window_start)  # wait for the window to open
        if now > stop.window_end:
            return None
        arrivals.append(now)
        now += problem.service_seconds
        node = i + 1
    now += travel_seconds(matrix[node][0], problem.speed_mps)
    if now > vehicle.shift_end:
        return None

    return RouteResult(
        driver_id=vehicle.driver_id,
        stops=list(stops),
        arrivals=arrivals,
        loads_after=loads,
        start=vehicle.shift_start,
        end=now,
        distance_m=route_distance(matrix, stops),
        start_load=start_load,
    )


def check_route(problem: Problem, route: RouteResult) -> list[str]:
    """Independently verify a route. Returns a list of human-readable violations."""
    vehicle = next(v for v in problem.vehicles if v.driver_id == route.driver_id)
    matrix = distance_matrix(problem.points())
    problems = []

    if route.start < vehicle.shift_start:
        problems.append(f"driver {vehicle.driver_id} leaves before their shift")
    if route.end > vehicle.shift_end:
        problems.append(f"driver {vehicle.driver_id} returns after their shift")

    start_load, loads = loads_along(problem, route.stops)
    if max([start_load, *loads], default=0) > vehicle.capacity:
        problems.append(f"driver {vehicle.driver_id} goes over capacity")
    if loads != route.loads_after:
        problems.append(f"driver {vehicle.driver_id} has wrong load numbers")

    ready, node = route.start, 0
    for i, arrival in zip(route.stops, route.arrivals):
        stop = problem.stops[i]
        if not stop.window_start <= arrival <= stop.window_end:
            problems.append(f"order {stop.order_id} is served outside its time window")
        if arrival < ready + travel_seconds(matrix[node][i + 1], problem.speed_mps):
            problems.append(f"order {stop.order_id} is reached faster than driving allows")
        ready, node = arrival + problem.service_seconds, i + 1
    if route.end < ready + travel_seconds(matrix[node][0], problem.speed_mps):
        problems.append(f"driver {vehicle.driver_id} gets back to the depot faster than driving allows")
    if route.distance_m != route_distance(matrix, route.stops):
        problems.append(f"driver {vehicle.driver_id} has the wrong distance")
    return problems


def check_solution(problem: Problem, solution: Solution) -> list[str]:
    problems = []
    seen = [i for route in solution.routes for i in route.stops] + solution.unassigned
    if sorted(seen) != list(range(len(problem.stops))):
        problems.append("every order must be routed once or listed as unassigned")
    for route in solution.routes:
        problems.extend(check_route(problem, route))
    return problems


def solve_greedy(problem: Problem) -> Solution:
    """Baseline that works like a manual dispatcher.

    Each driver, in shift order, keeps taking the stop whose time window closes
    soonest, breaking ties by distance, as long as the route stays feasible.
    """
    started = clock.perf_counter()
    matrix = distance_matrix(problem.points())
    remaining = set(range(len(problem.stops)))
    routes = []

    for vehicle in sorted(problem.vehicles, key=lambda v: (v.shift_start, v.driver_id)):
        route, stops = None, []
        while remaining:
            here = stops[-1] + 1 if stops else 0
            by_deadline = sorted(remaining, key=lambda i: (problem.stops[i].window_end, matrix[here][i + 1], i))
            for candidate in by_deadline:
                attempt = simulate(problem, vehicle, stops + [candidate], matrix)
                if attempt is not None:
                    route, stops = attempt, attempt.stops
                    remaining.discard(candidate)
                    break
            else:
                break
        if route is not None:
            routes.append(route)

    return Solution("greedy", routes, sorted(remaining), round((clock.perf_counter() - started) * 1000))


def solve_ortools(problem: Problem, time_limit_s: float = 5.0) -> Solution:
    """Capacitated VRP with time windows and mixed pickups/deliveries, solved with OR-tools."""
    started = clock.perf_counter()
    matrix = distance_matrix(problem.points())
    travel = [[travel_seconds(d, problem.speed_mps) for d in row] for row in matrix]
    stops, vehicles = problem.stops, problem.vehicles

    manager = pywrapcp.RoutingIndexManager(len(stops) + 1, len(vehicles), 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        return matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    routing.SetArcCostEvaluatorOfAllVehicles(routing.RegisterTransitCallback(distance_callback))

    # Time: service at the stop we're leaving plus the drive to the next one.
    def time_callback(from_index, to_index):
        a, b = manager.IndexToNode(from_index), manager.IndexToNode(to_index)
        return (problem.service_seconds if a else 0) + travel[a][b]

    routing.AddDimension(routing.RegisterTransitCallback(time_callback), MAX_WAIT_SECONDS, 24 * 3600, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")
    for node, stop in enumerate(stops, start=1):
        time_dim.CumulVar(manager.NodeToIndex(node)).SetRange(stop.window_start, stop.window_end)
    for v, vehicle in enumerate(vehicles):
        for index in (routing.Start(v), routing.End(v)):
            time_dim.CumulVar(index).SetRange(vehicle.shift_start, vehicle.shift_end)
        # Leave as late as possible and get back as early as possible.
        routing.AddVariableMaximizedByFinalizer(time_dim.CumulVar(routing.Start(v)))
        routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(routing.End(v)))

    capacities = [vehicle.capacity for vehicle in vehicles]

    # "Delivered" counts delivery bags on the route; its end value is what the truck must start with.
    def delivered_callback(index):
        node = manager.IndexToNode(index)
        return stops[node - 1].bags if node and stops[node - 1].kind == DELIVERY else 0

    routing.AddDimensionWithVehicleCapacity(
        routing.RegisterUnaryTransitCallback(delivered_callback), 0, capacities, True, "Delivered"
    )

    # "Load" is bags on board: up at pickups, down at deliveries, never above capacity.
    def load_callback(index):
        node = manager.IndexToNode(index)
        if not node:
            return 0
        stop = stops[node - 1]
        return stop.bags if stop.kind == PICKUP else -stop.bags

    routing.AddDimensionWithVehicleCapacity(
        routing.RegisterUnaryTransitCallback(load_callback), 0, capacities, False, "Load"
    )
    delivered_dim = routing.GetDimensionOrDie("Delivered")
    load_dim = routing.GetDimensionOrDie("Load")
    for v in range(len(vehicles)):
        # Starting with at least every delivery bag makes the Load dimension an upper bound on
        # the real load, so keeping it under capacity keeps the real truck under capacity too.
        routing.solver().Add(load_dim.CumulVar(routing.Start(v)) >= delivered_dim.CumulVar(routing.End(v)))

    for node in range(1, len(stops) + 1):
        routing.AddDisjunction([manager.NodeToIndex(node)], DROP_PENALTY)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromMilliseconds(int(time_limit_s * 1000))

    assignment = routing.SolveWithParameters(params)
    if assignment is None:
        return Solution("ortools", [], list(range(len(stops))), round((clock.perf_counter() - started) * 1000))

    routes, assigned = [], set()
    for v, vehicle in enumerate(vehicles):
        index = routing.Start(v)
        start = assignment.Min(time_dim.CumulVar(index))
        visit, arrivals = [], []
        index = assignment.Value(routing.NextVar(index))
        while not routing.IsEnd(index):
            visit.append(manager.IndexToNode(index) - 1)
            arrivals.append(assignment.Min(time_dim.CumulVar(index)))
            index = assignment.Value(routing.NextVar(index))
        if not visit:
            continue
        start_load, loads = loads_along(problem, visit)
        routes.append(
            RouteResult(
                driver_id=vehicle.driver_id,
                stops=visit,
                arrivals=arrivals,
                loads_after=loads,
                start=start,
                end=assignment.Min(time_dim.CumulVar(index)),
                distance_m=route_distance(matrix, visit),
                start_load=start_load,
            )
        )
        assigned.update(visit)

    unassigned = [i for i in range(len(stops)) if i not in assigned]
    return Solution("ortools", routes, unassigned, round((clock.perf_counter() - started) * 1000))
