import random
from dataclasses import replace

from django.test import SimpleTestCase

from logistics.services import routing

DEPOT = (-112.07, 33.45)
HOUR = 3600


def stop(order_id, east_km=0.0, north_km=0.0, kind=routing.PICKUP, bags=1, start=9, end=11):
    return routing.Stop(
        order_id=order_id,
        lon=DEPOT[0] + east_km / 93.0,  # about 93 km per degree of longitude at Phoenix's latitude
        lat=DEPOT[1] + north_km / 110.5,
        kind=kind,
        bags=bags,
        window_start=start * HOUR,
        window_end=end * HOUR,
    )


def van(driver_id=1, capacity=10, start=7, end=19):
    return routing.Vehicle(driver_id, capacity, start * HOUR, end * HOUR)


def solve_both(problem):
    return [routing.solve_ortools(problem, time_limit_s=1), routing.solve_greedy(problem)]


class DistanceTests(SimpleTestCase):
    def test_same_point_is_zero(self):
        self.assertEqual(routing.grid_distance_m(DEPOT, DEPOT), 0)

    def test_distance_is_symmetric(self):
        a, b = DEPOT, (DEPOT[0] + 0.05, DEPOT[1] + 0.03)
        self.assertEqual(routing.grid_distance_m(a, b), routing.grid_distance_m(b, a))

    def test_distance_follows_the_street_grid(self):
        corner = (DEPOT[0] + 0.05, DEPOT[1])
        target = (DEPOT[0] + 0.05, DEPOT[1] + 0.03)
        across = routing.grid_distance_m(DEPOT, target)
        around = routing.grid_distance_m(DEPOT, corner) + routing.grid_distance_m(corner, target)
        self.assertAlmostEqual(across, around, delta=20)


class SolverTests(SimpleTestCase):
    def test_empty_day_has_no_routes(self):
        problem = routing.Problem(DEPOT, [], [van()])
        for solution in solve_both(problem):
            self.assertEqual(solution.routes, [])
            self.assertEqual(solution.unassigned, [])

    def test_random_day_is_valid_and_ortools_drives_less(self):
        rng = random.Random(1)
        stops = []
        for i in range(30):
            start = rng.choice([7, 9, 11, 13, 15])
            stops.append(
                stop(
                    i,
                    east_km=rng.uniform(-15, 15),
                    north_km=rng.uniform(-12, 12),
                    kind=rng.choice([routing.PICKUP, routing.DELIVERY]),
                    bags=rng.randint(1, 4),
                    start=start,
                    end=start + 2,
                )
            )
        problem = routing.Problem(DEPOT, stops, [van(1, 30), van(2, 30, 11, 19), van(3, 35)])

        optimized, greedy = solve_both(problem)

        self.assertEqual(routing.check_solution(problem, optimized), [])
        self.assertEqual(routing.check_solution(problem, greedy), [])
        self.assertGreaterEqual(optimized.assigned_count, greedy.assigned_count)
        if optimized.assigned_count == greedy.assigned_count:
            self.assertLess(optimized.total_distance_m, greedy.total_distance_m)

    def test_orders_that_do_not_fit_are_left_unassigned(self):
        problem = routing.Problem(DEPOT, [stop(1, 2, bags=3), stop(2, -2, bags=3)], [van(capacity=5)])

        for solution in solve_both(problem):
            self.assertEqual(routing.check_solution(problem, solution), [])
            self.assertEqual(solution.assigned_count, 1)
            self.assertEqual(len(solution.unassigned), 1)

    def test_tight_truck_delivers_before_it_picks_up(self):
        # Leaving with 3 delivery bags and grabbing 3 more first would be 6 bags in a 4-bag van.
        pickup = stop(1, east_km=1, kind=routing.PICKUP, bags=3, start=9, end=17)
        delivery = stop(2, east_km=8, kind=routing.DELIVERY, bags=3, start=9, end=17)
        problem = routing.Problem(DEPOT, [pickup, delivery], [van(capacity=4)])

        optimized, greedy = solve_both(problem)

        self.assertEqual(routing.check_solution(problem, optimized), [])
        self.assertEqual(optimized.routes[0].stops, [1, 0])
        self.assertLessEqual(optimized.routes[0].max_load, 4)
        # The greedy baseline grabs the nearby pickup first and can never fit the delivery after it.
        self.assertEqual(routing.check_solution(problem, greedy), [])
        self.assertEqual(greedy.assigned_count, 1)

    def test_time_windows_decide_the_order(self):
        late_but_close = stop(1, east_km=1, start=13, end=15)
        early_but_far = stop(2, east_km=10, start=9, end=11)
        problem = routing.Problem(DEPOT, [late_but_close, early_but_far], [van()])

        for solution in solve_both(problem):
            route = solution.routes[0]
            self.assertEqual(route.stops, [1, 0])
            self.assertEqual(routing.check_solution(problem, solution), [])

    def test_orders_outside_every_shift_are_unassigned(self):
        problem = routing.Problem(DEPOT, [stop(1, 2, start=15, end=17)], [van(start=7, end=11)])

        for solution in solve_both(problem):
            self.assertEqual(solution.unassigned, [0])


class CheckerTests(SimpleTestCase):
    def setUp(self):
        self.problem = routing.Problem(DEPOT, [stop(1, 3, bags=2), stop(2, 6, bags=2)], [van(capacity=10)])
        matrix = routing.distance_matrix(self.problem.points())
        self.route = routing.simulate(self.problem, self.problem.vehicles[0], [0, 1], matrix)

    def test_valid_route_passes(self):
        self.assertEqual(routing.check_route(self.problem, self.route), [])

    def test_catches_service_outside_the_window(self):
        broken = replace(self.route, arrivals=[self.route.arrivals[0], 12 * HOUR])
        self.assertTrue(any("time window" in issue for issue in routing.check_route(self.problem, broken)))

    def test_catches_impossible_driving_speed(self):
        broken = replace(self.route, arrivals=[self.route.start, self.route.arrivals[1]])
        self.assertTrue(any("faster than driving" in issue for issue in routing.check_route(self.problem, broken)))

    def test_catches_over_capacity(self):
        small_van = replace(self.problem, vehicles=[van(capacity=3)])
        self.assertTrue(any("capacity" in issue for issue in routing.check_route(small_van, self.route)))

    def test_catches_missing_orders(self):
        solution = routing.Solution("test", [replace(self.route, stops=[0], arrivals=[self.route.arrivals[0]])], [], 0)
        self.assertTrue(routing.check_solution(self.problem, solution))
