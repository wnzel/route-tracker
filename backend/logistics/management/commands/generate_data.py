from datetime import date

from django.core.management.base import BaseCommand, CommandError

from logistics.models import Zone
from logistics.services.data_generator import GeneratorConfig, generate


class Command(BaseCommand):
    help = "Generate synthetic customers, drivers, and pickup/delivery orders around Phoenix."

    def add_arguments(self, parser):
        defaults = GeneratorConfig()
        parser.add_argument("--customers", type=int, default=defaults.customers)
        parser.add_argument("--drivers", type=int, default=defaults.drivers)
        parser.add_argument("--history-days", type=int, default=defaults.history_days)
        parser.add_argument("--future-days", type=int, default=defaults.future_days)
        parser.add_argument("--orders-per-day", type=float, default=defaults.orders_per_day)
        parser.add_argument("--seed", type=int, default=defaults.seed)
        parser.add_argument(
            "--end-date",
            type=date.fromisoformat,
            help="Last day of order history (YYYY-MM-DD). Defaults to yesterday.",
        )
        parser.add_argument("--reset", action="store_true", help="Delete existing data first.")

    def handle(self, *args, **options):
        if Zone.objects.exists() and not options["reset"]:
            raise CommandError("Data already exists. Re-run with --reset to replace it.")

        config = GeneratorConfig(
            customers=options["customers"],
            drivers=options["drivers"],
            history_days=options["history_days"],
            future_days=options["future_days"],
            orders_per_day=options["orders_per_day"],
            seed=options["seed"],
            end_date=options["end_date"],
        )
        summary = generate(config, reset=options["reset"])

        history_start, history_end = summary["history"]
        future_start, future_end = summary["future"]
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {summary['zones']} zones, {summary['customers']} customers, "
                f"{summary['drivers']} drivers, and {summary['orders']} orders.\n"
                f"History: {history_start} to {history_end}. Pending: {future_start} to {future_end}."
            )
        )
