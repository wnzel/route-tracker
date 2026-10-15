"""Daily order volume forecasts per zone.

Model (top-down): forecast the whole city, then split it across zones.

1. Count orders per zone per day over the training window. Every order placed
   counts as demand, including cancelled ones.
2. Weekday index: the city's average volume on each weekday divided by its
   overall average.
3. City trend: divide out the weekday index and fit a straight line (level +
   trend) to the city total by least squares.
4. Zone share: each zone's fraction of all orders in the window.
5. Forecast for a zone on a day = city line x weekday index x zone share.

Why top-down: a zone only sees a handful of orders a day, so a trend fit per
zone mostly chases noise. A first version did exactly that and lost to the
four-week average baseline in the backtest. The city total is large enough for
the weekly shape and trend to be clear, and zone shares are stable.

The backtest is rolling-origin: for each of the last eight weeks, fit on
everything before that week and forecast it. Scores are WAPE (total absolute
error / total actual orders) against two baselines: the same weekday last
week, and the average of the same weekday over the previous four weeks. A
single holdout window was too noisy to rank the models reliably.

It also reports a noise floor: the error a perfect model would still have if
daily orders are Poisson around the forecast. The sample data is generated
that way, so a model near the floor has learned everything there is to learn.

The math here is plain Python on small lists so it can be tested without a
database; the functions at the bottom read and shape the Django data.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Count

from logistics.models import Order, Zone

TRAINING_WEEKS = 12
BACKTEST_FOLDS = 8
BACKTEST_HORIZON = 7


@dataclass(frozen=True)
class Model:
    first_day: date  # day index 0 of the training window
    weekday_index: tuple[float, ...]  # Monday..Sunday, averages to 1
    intercept: float  # deseasonalized city orders per day at day index 0
    slope: float  # change in deseasonalized city orders per day
    shares: dict[str, float]  # each zone's fraction of city orders

    def predict_city(self, day: date) -> float:
        t = (day - self.first_day).days
        return max(0.0, (self.intercept + self.slope * t) * self.weekday_index[day.weekday()])

    def predict(self, zone: str, day: date) -> float:
        return self.predict_city(day) * self.shares[zone]


def least_squares(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Return (intercept, slope) of the best-fit line. A flat line if there's nothing to fit."""
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return mean_y, 0.0
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / var_x
    return mean_y - slope * mean_x, slope


def fit(days: list[date], counts: dict[str, list[int]], weeks: int = TRAINING_WEEKS) -> Model:
    """Fit on the last `weeks` full weeks of `days`. `counts[zone][i]` is orders on `days[i]`."""
    window = min(len(days), weeks * 7)
    if window < 7:
        raise ValueError("Need at least one full week of history to forecast.")
    days = days[-window:]
    counts = {zone: values[-window:] for zone, values in counts.items()}

    city = [sum(values[i] for values in counts.values()) for i in range(window)]
    overall = sum(city) / window
    by_weekday: dict[int, list[int]] = defaultdict(list)
    for day, total in zip(days, city):
        by_weekday[day.weekday()].append(total)
    weekday_index = tuple(
        (sum(by_weekday[d]) / len(by_weekday[d]) / overall) if by_weekday[d] and overall else 1.0
        for d in range(7)
    )

    first_day = days[0]
    xs = [float((day - first_day).days) for day in days]
    deseasonalized = [total / weekday_index[day.weekday()] for day, total in zip(days, city)]
    intercept, slope = least_squares(xs, deseasonalized)

    city_total = sum(city)
    shares = {zone: (sum(values) / city_total if city_total else 1 / len(counts)) for zone, values in counts.items()}
    return Model(first_day=first_day, weekday_index=weekday_index, intercept=intercept, slope=slope, shares=shares)


def wape(actual: list[float], predicted: list[float]) -> float | None:
    total = sum(actual)
    if not total:
        return None
    return sum(abs(a - p) for a, p in zip(actual, predicted)) / total


def poisson_mean_abs_deviation(rate: float) -> float:
    """E|X - rate| for X ~ Poisson(rate): the error left over when the forecast is exactly right."""
    if rate <= 0:
        return 0.0
    k = math.floor(rate)
    return 2 * math.exp(-rate + (k + 1) * math.log(rate) - math.lgamma(k + 1))


def backtest(
    days: list[date], counts: dict[str, list[int]], folds: int = BACKTEST_FOLDS, horizon: int = BACKTEST_HORIZON
) -> dict:
    """Rolling-origin backtest over the last `folds` x `horizon` days, at zone-day and city-day level."""
    if len(days) < folds * horizon + 28:
        raise ValueError("Need at least four weeks of history before the backtest period.")
    names = ("model", "last_week", "four_week_avg")
    zone_actual: list[float] = []
    zone_guess: dict[str, list[float]] = {name: [] for name in names}
    city_actual: list[float] = []
    city_guess: dict[str, list[float]] = {name: [] for name in names}
    zone_floor = city_floor = 0.0

    for fold in range(folds):
        cut = len(days) - horizon * (folds - fold)
        model = fit(days[:cut], {zone: values[:cut] for zone, values in counts.items()})
        for i in range(cut, cut + horizon):
            day = days[i]
            city_actual.append(sum(values[i] for values in counts.values()))
            totals = dict.fromkeys(names, 0.0)
            for zone, values in counts.items():
                # Same weekday in the four weeks before the fold, so baselines never see the test week.
                same_weekday = [values[i - 7 * k] for k in range(1, 5)]
                guesses = {
                    "model": model.predict(zone, day),
                    "last_week": float(same_weekday[0]),
                    "four_week_avg": sum(same_weekday) / 4,
                }
                zone_actual.append(values[i])
                for name, guess in guesses.items():
                    zone_guess[name].append(guess)
                    totals[name] += guess
                zone_floor += poisson_mean_abs_deviation(guesses["model"])
            for name in names:
                city_guess[name].append(totals[name])
            city_floor += poisson_mean_abs_deviation(model.predict_city(day))

    scores = {
        name: {"zone_day_wape": wape(zone_actual, zone_guess[name]), "city_day_wape": wape(city_actual, city_guess[name])}
        for name in names
    }
    return {
        "method": f"rolling origin, {folds} folds of {horizon} days",
        "test_start": days[-folds * horizon],
        "test_end": days[-1],
        "scores": scores,
        "noise_floor": {
            "zone_day_wape": zone_floor / sum(zone_actual) if sum(zone_actual) else None,
            "city_day_wape": city_floor / sum(city_actual) if sum(city_actual) else None,
        },
    }


# --- Django data access ----------------------------------------------------------------------------


def history_counts(end: date, days: int) -> tuple[list[date], dict[str, list[int]]]:
    """Orders placed per zone per day for the `days` days ending on `end` (pending orders excluded)."""
    start = end - timedelta(days=days - 1)
    dates = [start + timedelta(days=i) for i in range(days)]
    zones = list(Zone.objects.order_by("name").values_list("name", flat=True))
    counts = {zone: [0] * days for zone in zones}
    rows = (
        Order.objects.filter(service_date__range=(start, end), customer__zone__isnull=False)
        .exclude(status=Order.Status.PENDING)
        .values("service_date", "customer__zone__name")
        .annotate(n=Count("id"))
    )
    for row in rows:
        counts[row["customer__zone__name"]][(row["service_date"] - start).days] = row["n"]
    return dates, counts


def last_history_day() -> date | None:
    latest = (
        Order.objects.exclude(status=Order.Status.PENDING).order_by("-service_date").values_list("service_date", flat=True).first()
    )
    return latest


def booked_counts(start: date, days: int) -> dict[tuple[str, date], int]:
    end = start + timedelta(days=days - 1)
    rows = (
        Order.objects.filter(service_date__range=(start, end), status=Order.Status.PENDING, customer__zone__isnull=False)
        .values("service_date", "customer__zone__name")
        .annotate(n=Count("id"))
    )
    return {(row["customer__zone__name"], row["service_date"]): row["n"] for row in rows}


def forecast(start: date | None = None, days: int = 7) -> dict:
    """Forecast `days` days from `start` (default: the day after history ends), plus a backtest."""
    end = last_history_day()
    if end is None:
        raise ValueError("No order history yet. Run generate_data first.")
    start = start or end + timedelta(days=1)
    if start <= end:
        raise ValueError(f"Forecasts start after the last day of history ({end.isoformat()}).")

    history_days = (end - Order.objects.order_by("service_date").values_list("service_date", flat=True).first()).days + 1
    dates, counts = history_counts(end, history_days)
    model = fit(dates, counts)
    booked = booked_counts(start, days)
    forecast_days = [start + timedelta(days=i) for i in range(days)]

    zones = []
    for zone in sorted(counts):
        daily = [
            {"date": day, "forecast": round(model.predict(zone, day), 1), "booked": booked.get((zone, day), 0)}
            for day in forecast_days
        ]
        zones.append({"zone": zone, "total_forecast": round(sum(d["forecast"] for d in daily), 1), "daily": daily})

    city = [
        {
            "date": day,
            "forecast": round(model.predict_city(day), 1),
            "booked": sum(booked.get((zone, day), 0) for zone in counts),
        }
        for day in forecast_days
    ]
    return {
        "start": start,
        "days": days,
        "history_end": end,
        "weekday_index": dict(zip(("mon", "tue", "wed", "thu", "fri", "sat", "sun"), (round(v, 3) for v in model.weekday_index))),
        "city": city,
        "zones": zones,
        "backtest": backtest_or_none(dates, counts),
    }


def backtest_or_none(days: list[date], counts: dict[str, list[int]]) -> dict | None:
    """The backtest needs about twelve weeks of history; with less, forecast anyway and skip it."""
    try:
        return backtest(days, counts)
    except ValueError:
        return None
