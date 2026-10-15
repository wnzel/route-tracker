from datetime import date

from django.core.management.base import BaseCommand, CommandError

from logistics.services import forecasting


def percent(value):
    return "n/a" if value is None else f"{value:.1%}"


class Command(BaseCommand):
    help = "Forecast daily orders per zone and show how the model scored on recent history."

    def add_arguments(self, parser):
        parser.add_argument("--start", type=date.fromisoformat, help="First forecast day. Defaults to the day after history.")
        parser.add_argument("--days", type=int, default=7)

    def handle(self, *args, **options):
        try:
            result = forecasting.forecast(options["start"], options["days"])
        except ValueError as error:
            raise CommandError(str(error))

        self.stdout.write("Day          Forecast  Booked")
        for day in result["city"]:
            self.stdout.write(f"{day['date']:%a %b %d}  {day['forecast']:>8.1f}  {day['booked']:>6}")

        backtest = result["backtest"]
        if backtest is None:
            self.stdout.write("\nNot enough history for a backtest yet (it needs about twelve weeks).")
            return
        self.stdout.write(
            f"\nBacktest {backtest['test_start']} to {backtest['test_end']}, {backtest['method']} (WAPE, lower is better)"
        )
        rows = [
            ("Top-down model", backtest["scores"]["model"]),
            ("4-week same-day average", backtest["scores"]["four_week_avg"]),
            ("Same day last week", backtest["scores"]["last_week"]),
            ("Noise floor (perfect model)", backtest["noise_floor"]),
        ]
        for label, score in rows:
            self.stdout.write(
                f"  {label:<28} zone-day {percent(score['zone_day_wape']):>6}   city-day {percent(score['city_day_wape']):>6}"
            )
