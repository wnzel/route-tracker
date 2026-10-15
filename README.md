# Route Tracker

A pickup and delivery route planner for a laundry delivery service in metro Phoenix. Drivers (valets) start at a depot, visit customers inside two-hour time windows, and carry a limited number of bags.

The project is built in stages:

1. **Backend and data (done):** Django + PostGIS models, a seeded generator for realistic order history, and a GeoJSON API.
2. **Route optimization (done):** a capacitated vehicle routing solver with time windows and mixed pickups and deliveries (Google OR-tools), compared against a greedy dispatch baseline.
3. **Map frontend (done):** React + TypeScript map of zones, routes, and stops, with a side-by-side comparison of both solvers.
4. **Forecasting and MCP:** next-week pickup volume per zone, and an MCP server so Claude can plan routes and answer operations questions.

## Stack

- Python 3.12, Django 5.2, Django REST Framework, djangorestframework-gis
- Google OR-tools 9.15
- React 19, TypeScript 7, Vite 8, Leaflet (react-leaflet), Vitest
- PostgreSQL 16 + PostGIS 3.4
- Docker Compose

## Quick start

Requires Docker Desktop.

```bash
docker compose up --build
```

In a second terminal, load the sample data and plan a week of routes:

```bash
docker compose exec web python manage.py generate_data
```

```bash
docker compose exec web python manage.py plan_routes --days 7
```

Then open the map at http://localhost:5173, or the API at http://localhost:8000/api/.

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

## Route planning

Plan today's pending orders with both solvers and compare them:

```bash
docker compose exec web python manage.py plan_routes
```

Options: `--date YYYY-MM-DD`, `--days N` (plan N consecutive days), `--solver ortools|greedy|both`, and `--time-limit` (OR-tools search seconds, default 5).

**The problem.** Each driver leaves the depot loaded with every delivery bag on their route, drops bags at deliveries, and picks bags up at pickups. Every stop has a two-hour window, every driver has a shift and a bag capacity, and the van has to stay under capacity the whole way, so the order of stops matters, not just the total. Distances use a Manhattan (street grid) approximation because Phoenix roads mostly run north-south and east-west, at an average 40 km/h plus 5 minutes per stop.

**OR-tools model.** Distance is the arc cost. A Time dimension enforces windows and shifts and allows waiting. Two capacity dimensions handle mixed loads: `Delivered` counts delivery bags on the route, and `Load` tracks bags on board (up at pickups, down at deliveries), with each van's starting load constrained to at least its delivered total. Any order can be dropped at a large penalty, so impossible orders show up as unassigned instead of making the whole day fail. Search uses path-cheapest-arc for a first solution and guided local search after that.

**Baseline.** A greedy dispatcher: each driver, in shift order, keeps taking the stop whose window closes soonest (ties go to the closest), as long as the route stays feasible.

**Validation.** Every plan is re-checked by an independent route checker (windows, shifts, drive times, capacity at every stop, every order routed once or listed as unassigned) before it is saved.

**Results** on the 7 pending days from the default seed (5 second OR-tools limit):

| Day | Orders | OR-tools | Greedy dispatch | Less driving |
|---|---|---|---|---|
| Wed | 60 | 60 served, 682 km | 60 served, 971 km | 29.7% |
| Thu | 77 | 77 served, 756 km | 76 served, 1,070 km | 30.2% per order |
| Fri | 84 | 84 served, 789 km | 84 served, 1,173 km | 32.7% |
| Sat | 37 | 37 served, 522 km | 37 served, 641 km | 18.6% |
| Sun | 37 | 37 served, 532 km | 37 served, 716 km | 25.7% |
| Mon | 88 | 88 served, 809 km | 88 served, 1,125 km | 28.1% |
| Tue | 75 | 75 served, 753 km | 75 served, 1,002 km | 24.9% |
| **Week** | **458** | **458 served, 4,843 km** | **457 served, 6,696 km** | **27.7%** |

## Map

The map at http://localhost:5173 shows one service day at a time:

- Pick a day and switch between the OR-tools and greedy dispatch plans. Both load together, so switching is instant, and the summary shows how much less driving OR-tools needs.
- Each driver keeps the same color in both plans. Filled dots are pickups, hollow dots are deliveries, gray dashed dots are orders no route could fit, and the black dot is the depot.
- Click a driver (or any of their stops) to highlight the route and list its stops with arrival times, time windows, and bags on board.
- Route lines are drawn as east-west then north-south legs, matching the street-grid distance the planner optimizes. They aren't turn-by-turn roads.

Basemap tiles come from the OpenStreetMap tile servers, which are fine for development and demos. A public deployment with real traffic should use a commercial tile provider.

## API

All endpoints are read-only. Map data is returned as GeoJSON.

| Endpoint | Returns |
|---|---|
| `GET /api/depots/` | Depot locations |
| `GET /api/zones/` | Zone polygons with `customer_count` |
| `GET /api/customers/?zone=B2` | Customers, optionally by zone |
| `GET /api/drivers/` | Drivers, capacities, and shifts |
| `GET /api/orders/?date=2026-10-15&status=pending&kind=pickup&zone=B2` | Orders at each customer's location |
| `GET /api/route-plans/?date=2026-10-15` | Saved plans with totals and drivers used |
| `GET /api/service-days/` | Days with pending orders and the newest plan ID from each solver |
| `GET /api/route-plans/<id>/` | One plan: each route as a GeoJSON line with its ordered stops, arrival times, and load after each stop |

Paginated endpoints accept `?page_size=` up to 2000.

## Tests

The backend tests need PostGIS, so run them in the container:

```bash
docker compose run --rm web python manage.py test
```

Frontend type check and unit tests:

```bash
docker compose run --rm --no-deps frontend sh -c "npm run typecheck && npm test"
```
