# Route Tracker

A pickup and delivery route planner for a laundry delivery service in metro Phoenix. Drivers (valets) start at a depot, visit customers inside two-hour time windows, and carry a limited number of bags.

The project is built in stages:

1. **Backend and data (done):** Django + PostGIS models, a seeded generator for realistic order history, and a GeoJSON API.
2. **Route optimization:** a capacitated vehicle routing solver with time windows (Google OR-tools), compared against a nearest-stop baseline.
3. **Map frontend:** React + TypeScript map of zones, orders, and each driver's route.
4. **Forecasting and MCP:** next-week pickup volume per zone, and an MCP server so Claude can plan routes and answer operations questions.

## Stack

- Python 3.12, Django 5.2, Django REST Framework, djangorestframework-gis
- PostgreSQL 16 + PostGIS 3.4
- Docker Compose

## Quick start

Requires Docker Desktop.

```bash
docker compose up --build
```

In a second terminal, load the sample data:

```bash
docker compose exec web python manage.py generate_data
```

Then open http://localhost:8000/api/.

To use the Django admin, create a user with `docker compose exec web python manage.py createsuperuser` and go to http://localhost:8000/admin/.

## Sample data

`generate_data` builds a reproducible world from one seed:

- A depot in downtown Phoenix and a 3 x 4 grid of service zones (`A1` in the northwest to `C4` in the southeast).
- 400 customers spread unevenly across zones, so some neighborhoods are busier than others.
- 8 drivers with 30 to 40 bag capacity on morning (7am to 3pm) or afternoon (11am to 7pm) shifts.
- 120 days of completed and cancelled order history, plus 7 days of pending orders starting today.
- A weekly pattern (Mondays are about 2.7x busier than Sundays) and about 0.1% daily growth, so the forecasting stage has a real signal to learn.

Useful options:

```bash
docker compose exec web python manage.py generate_data --reset --seed 7 --customers 800 --orders-per-day 120
```

`--reset` is required to replace existing data. `--end-date YYYY-MM-DD` sets the last day of history (defaults to yesterday).

## API

All endpoints are read-only. Map data is returned as GeoJSON.

| Endpoint | Returns |
|---|---|
| `GET /api/depots/` | Depot locations |
| `GET /api/zones/` | Zone polygons with `customer_count` |
| `GET /api/customers/?zone=B2` | Customers, optionally by zone |
| `GET /api/drivers/` | Drivers, capacities, and shifts |
| `GET /api/orders/?date=2026-10-15&status=pending&kind=pickup&zone=B2` | Orders at each customer's location |

Paginated endpoints accept `?page_size=` up to 2000.

## Tests

The tests need PostGIS, so run them in the container:

```bash
docker compose run --rm web python manage.py test
```
