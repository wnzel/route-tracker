import random
from datetime import date, timedelta
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APITestCase

from logistics.services import forecasting
from logistics.services.data_generator import GeneratorConfig, generate, poisson

MONDAY = date(2026, 6, 1)


def synthetic_history(weeks, weekday_factors, zone_rates, growth=0.0, noise_seed=None):
    rng = random.Random(noise_seed)
    days = [MONDAY + timedelta(days=i) for i in range(weeks * 7)]
    counts = {}
    for zone, rate in zone_rates.items():
        values = []
        for i, day in enumerate(days):
            expected = rate * weekday_factors[day.weekday()] * (1 + growth * i)
            values.append(poisson(rng, expected) if noise_seed is not None else round(expected))
        counts[zone] = values
    return days, counts


class MathTests(SimpleTestCase):
    def test_least_squares_recovers_a_line(self):
        intercept, slope = forecasting.least_squares([0, 1, 2, 3], [1, 3, 5, 7])
        self.assertAlmostEqual(intercept, 1)
        self.assertAlmostEqual(slope, 2)

    def test_least_squares_on_a_single_x_is_flat(self):
        self.assertEqual(forecasting.least_squares([2, 2], [4, 6]), (5, 0.0))

    def test_wape(self):
        self.assertAlmostEqual(forecasting.wape([10, 10], [8, 13]), 0.25)
        self.assertIsNone(forecasting.wape([0, 0], [1, 2]))

    def test_poisson_noise_floor_matches_simulation(self):
        rng = random.Random(0)
        rate = 6.0
        draws = [poisson(rng, rate) for _ in range(20000)]
        simulated = sum(abs(x - rate) for x in draws) / len(draws)
        self.assertAlmostEqual(forecasting.poisson_mean_abs_deviation(rate), simulated, delta=0.05)


class ModelTests(SimpleTestCase):
    factors = (1.4, 1.0, 1.0, 1.1, 1.2, 0.7, 0.5)

    def test_learns_the_weekly_pattern_and_zone_shares_exactly_without_noise(self):
        days, counts = synthetic_history(8, self.factors, {"A1": 20, "B2": 60})
        model = forecasting.fit(days, counts)

        next_monday = days[-1] + timedelta(days=1)
        self.assertAlmostEqual(model.shares["B2"], 0.75, places=2)
        self.assertAlmostEqual(model.predict("A1", next_monday), 28, delta=0.6)
        self.assertAlmostEqual(model.predict("B2", next_monday + timedelta(days=6)), 30, delta=0.6)

    def test_follows_growth(self):
        days, counts = synthetic_history(8, self.factors, {"A1": 50}, growth=0.01)
        model = forecasting.fit(days, counts)

        later = days[-1] + timedelta(days=7)
        self.assertGreater(model.predict("A1", later), model.predict("A1", days[-1]))  # both Sundays

    def test_needs_a_full_week(self):
        days, counts = synthetic_history(1, self.factors, {"A1": 5})
        with self.assertRaises(ValueError):
            forecasting.fit(days[:5], {"A1": counts["A1"][:5]})

    def test_backtest_beats_baselines_and_stays_near_the_noise_floor(self):
        days, counts = synthetic_history(
            17, self.factors, {f"Z{i}": rate for i, rate in enumerate([3, 4, 5, 6, 8])}, growth=0.002, noise_seed=4
        )
        result = forecasting.backtest(days, counts)

        model = result["scores"]["model"]
        self.assertLess(model["city_day_wape"], result["scores"]["last_week"]["city_day_wape"])
        self.assertLess(model["zone_day_wape"], result["scores"]["four_week_avg"]["zone_day_wape"])
        self.assertLess(model["city_day_wape"], result["noise_floor"]["city_day_wape"] * 1.25)
        self.assertEqual(result["test_end"], days[-1])


class ForecastDataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        generate(
            GeneratorConfig(
                customers=150, drivers=3, history_days=98, future_days=7, orders_per_day=40, seed=5, end_date=date(2026, 9, 30)
            )
        )

    def test_forecast_starts_after_history_and_splits_city_volume_across_zones(self):
        result = forecasting.forecast(days=7)

        self.assertEqual(result["history_end"], date(2026, 9, 30))
        self.assertEqual(result["start"], date(2026, 10, 1))
        self.assertEqual(len(result["city"]), 7)
        for i, day in enumerate(result["city"]):
            zone_sum = sum(zone["daily"][i]["forecast"] for zone in result["zones"])
            self.assertAlmostEqual(zone_sum, day["forecast"], delta=0.6)
        self.assertGreater(result["weekday_index"]["mon"], result["weekday_index"]["sun"])

    def test_booked_counts_match_pending_orders(self):
        from logistics.models import Order

        result = forecasting.forecast(days=7)

        for day in result["city"]:
            pending = Order.objects.filter(service_date=day["date"], status=Order.Status.PENDING).count()
            self.assertEqual(day["booked"], pending)

    def test_refuses_to_forecast_the_past(self):
        with self.assertRaises(ValueError):
            forecasting.forecast(date(2026, 9, 1))

    def test_command_prints_forecast_and_backtest(self):
        out = StringIO()

        call_command("forecast_volume", "--days", "3", stdout=out)

        self.assertIn("Thu Oct 01", out.getvalue())
        self.assertIn("Noise floor", out.getvalue())


class ShortHistoryTests(TestCase):
    def test_forecasts_without_a_backtest_when_history_is_short(self):
        generate(GeneratorConfig(customers=40, drivers=2, history_days=21, future_days=1, seed=2, end_date=date(2026, 9, 30)))

        result = forecasting.forecast(days=2)
        out = StringIO()
        call_command("forecast_volume", "--days", "2", stdout=out)

        self.assertIsNone(result["backtest"])
        self.assertEqual(len(result["city"]), 2)
        self.assertIn("Not enough history", out.getvalue())


class ForecastApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        generate(
            GeneratorConfig(
                customers=120, drivers=3, history_days=98, future_days=3, orders_per_day=30, seed=9, end_date=date(2026, 9, 30)
            )
        )

    def test_returns_daily_forecasts_and_backtest(self):
        body = self.client.get("/api/forecast/", {"days": 3}).json()

        self.assertEqual([day["date"] for day in body["city"]], ["2026-10-01", "2026-10-02", "2026-10-03"])
        self.assertEqual(len(body["zones"]), 12)
        self.assertIn("noise_floor", body["backtest"])

    def test_rejects_bad_input(self):
        self.assertEqual(self.client.get("/api/forecast/", {"days": 0}).status_code, 400)
        self.assertEqual(self.client.get("/api/forecast/", {"days": "week"}).status_code, 400)
        self.assertEqual(self.client.get("/api/forecast/", {"start": "2026-08-01"}).status_code, 400)
