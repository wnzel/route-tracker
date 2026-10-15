from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from logistics.models import RoutePlan
from logistics.services.planning import plan_routes


class Command(BaseCommand):
    help = "Plan driver routes for one day's pending orders and compare OR-tools against a greedy dispatch baseline."

    def add_arguments(self, parser):
        parser.add_argument("--date", type=date.fromisoformat, help="Service date (YYYY-MM-DD). Defaults to today.")
        parser.add_argument(
            "--solver",
            choices=["both", *RoutePlan.Solver.values],
            default="both",
            help="Which solver to run.",
        )
        parser.add_argument("--time-limit", type=float, default=5.0, help="OR-tools search time in seconds.")

    def handle(self, *args, **options):
        service_date = options["date"] or timezone.localdate()
        solvers = RoutePlan.Solver.values if options["solver"] == "both" else [options["solver"]]

        plans = {}
        for solver in solvers:
            plan = plan_routes(service_date, solver, time_limit_s=options["time_limit"])
            plans[solver] = plan
            km = plan.total_distance_m / 1000
            per_order = km / plan.orders_assigned if plan.orders_assigned else 0
            self.stdout.write(
                f"{plan.get_solver_display():<15} plan #{plan.pk}: {plan.orders_assigned}/{plan.orders_total} orders, "
                f"{plan.routes.count()} drivers, {km:.1f} km ({per_order:.2f} km per order), {plan.solve_ms} ms"
            )

        if len(plans) == 2:
            self.stdout.write(self.style.SUCCESS(compare(plans[RoutePlan.Solver.ORTOOLS], plans[RoutePlan.Solver.GREEDY])))


def compare(optimized: RoutePlan, baseline: RoutePlan) -> str:
    extra = optimized.orders_assigned - baseline.orders_assigned
    if extra == 0 and baseline.total_distance_m:
        saved = 1 - optimized.total_distance_m / baseline.total_distance_m
        return f"OR-tools served the same {optimized.orders_assigned} orders with {saved:.1%} less driving."
    if optimized.orders_assigned and baseline.orders_assigned:
        optimized_rate = optimized.total_distance_m / optimized.orders_assigned
        baseline_rate = baseline.total_distance_m / baseline.orders_assigned
        return (
            f"OR-tools served {extra:+d} orders versus the baseline, "
            f"with {1 - optimized_rate / baseline_rate:.1%} less driving per order."
        )
    return "Not enough assigned orders to compare."
