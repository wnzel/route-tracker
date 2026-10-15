import { useEffect, useMemo, useState } from "react";

import {
  api,
  SOLVER_LABELS,
  SOLVERS,
  type Depots,
  type Forecast,
  type OrderFeature,
  type Orders,
  type RoutePlan,
  type ServiceDay,
  type Solver,
  type Zones,
} from "./api";
import { DispatchBoard } from "./components/DispatchBoard";
import { ForecastPanel } from "./components/ForecastPanel";
import { RouteMap } from "./components/RouteMap";
import { RouteSummary } from "./components/RouteSummary";
import { StopList } from "./components/StopList";
import { TopBar, type View } from "./components/TopBar";
import { routeColor } from "./lib/colors";
import { readUrlState, writeUrlState } from "./lib/urlState";

type Plans = Partial<Record<Solver, RoutePlan>>;

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

const initial = readUrlState(window.location.search);

export default function App() {
  const [days, setDays] = useState<ServiceDay[] | null>(null);
  const [zones, setZones] = useState<Zones | null>(null);
  const [depots, setDepots] = useState<Depots | null>(null);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [date, setDate] = useState<string | null>(initial.date);
  const [view, setView] = useState<View>(initial.view);
  const [solver, setSolver] = useState<Solver>(initial.solver);
  const [plans, setPlans] = useState<Plans>({});
  const [orders, setOrders] = useState<Orders | null>(null);
  const [selectedRoute, setSelectedRoute] = useState<number | null>(null);
  const [hoveredRoute, setHoveredRoute] = useState<number | null>(null);
  const [loadingDay, setLoadingDay] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The day list, map layers, and next week's forecast load once.
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api.serviceDays(controller.signal),
      api.zones(controller.signal),
      api.depots(controller.signal),
      api.forecast(controller.signal).catch(() => null),
    ])
      .then(([serviceDays, zoneData, depotData, forecastData]) => {
        setDays(serviceDays);
        setZones(zoneData);
        setDepots(depotData);
        setForecast(forecastData);
        // Keep a date from a shared link if it's still a service day; otherwise open the first planned day.
        const firstPlanned = serviceDays.find((day) => Object.keys(day.plans).length > 0) ?? serviceDays[0];
        setDate((current) => (serviceDays.some((day) => day.date === current) ? current : (firstPlanned?.date ?? null)));
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(errorMessage(err));
      });
    return () => controller.abort();
  }, []);

  const day = useMemo(() => days?.find((d) => d.date === date) ?? null, [days, date]);

  // Both solvers' plans for the day load together, so switching between them is instant.
  useEffect(() => {
    if (!day) return;
    const controller = new AbortController();
    setLoadingDay(true);
    setSelectedRoute(null);
    const requests = SOLVERS.flatMap((s) => {
      const id = day.plans[s];
      return id ? [api.plan(id, controller.signal).then((plan) => [s, plan] as const)] : [];
    });
    Promise.all([Promise.all(requests), api.pendingOrders(day.date, controller.signal)])
      .then(([loaded, pending]) => {
        setPlans(Object.fromEntries(loaded));
        setOrders(pending);
        setLoadingDay(false);
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          setError(errorMessage(err));
          setLoadingDay(false);
        }
      });
    return () => controller.abort();
  }, [day]);

  // Mirror the view, day, and solver into the URL so a link opens the same screen.
  useEffect(() => {
    window.history.replaceState(null, "", writeUrlState({ view, date, solver }) || window.location.pathname);
  }, [view, date, solver]);

  const plan = plans[solver] ?? null;
  // Stable identity so the map only refits when the plan actually changes.
  const routes = useMemo(() => plan?.routes.features ?? [], [plan]);

  // Color follows the driver, so each driver keeps one color in both plans.
  const driverColors = useMemo(() => {
    const ids = new Set<number>();
    Object.values(plans).forEach((p) => p?.routes.features.forEach((route) => ids.add(route.properties.driver)));
    return new Map([...ids].sort((a, b) => a - b).map((id, index) => [id, routeColor(index)]));
  }, [plans]);

  const unassigned = useMemo<OrderFeature[]>(() => {
    if (!plan || !orders) return [];
    const ids = new Set(plan.unassigned_orders);
    return orders.features.filter((order) => ids.has(Number(order.id)));
  }, [plan, orders]);

  const zoneForecast = useMemo(() => {
    if (view !== "forecast" || !forecast) return null;
    const target = forecast.city.some((d) => d.date === date) ? date : forecast.city[0]?.date;
    return new Map(
      forecast.zones.map((zone) => [zone.zone, zone.daily.find((d) => d.date === target)?.forecast ?? 0] as const),
    );
  }, [view, forecast, date]);

  const pickerDays = useMemo(() => {
    if (view === "forecast" && forecast) {
      return forecast.city.map((d) => ({ date: d.date, label: `${Math.round(d.forecast)} expected` }));
    }
    return (days ?? []).map((d) => ({ date: d.date, label: `${d.pending_orders} orders` }));
  }, [view, forecast, days]);

  const selected = plan?.routes.features.find((route) => route.id === selectedRoute) ?? null;
  const selectSolver = (next: Solver) => {
    setSolver(next);
    setSelectedRoute(null);
  };

  return (
    <div className="app" data-view={view}>
      <TopBar
        days={pickerDays}
        date={date}
        onDate={setDate}
        view={view}
        onView={setView}
        solver={solver}
        onSolver={selectSolver}
      />

      <aside className="rail">
        {error && (
          <p className="notice notice-error" role="alert">
            Couldn't reach the API ({error}). Start it with <code>docker compose up</code>, then reload.
          </p>
        )}
        {days && days.length === 0 && (
          <p className="notice">
            No pending orders yet. Load sample data with <code>docker compose exec web python manage.py generate_data</code>.
          </p>
        )}

        {view === "routes" && (
          <>
            {day && !plan && !loadingDay && (
              <p className="notice">
                There's no {SOLVER_LABELS[solver]} plan for this day yet. Create one with{" "}
                <code>docker compose exec web python manage.py plan_routes --date {day.date}</code>
              </p>
            )}
            {plan && !selected && <RouteSummary plan={plan} optimized={plans.ortools} baseline={plans.greedy} />}
            {selected && (
              <StopList
                route={selected}
                color={driverColors.get(selected.properties.driver)!}
                onClose={() => setSelectedRoute(null)}
              />
            )}
          </>
        )}

        {view === "forecast" &&
          (forecast ? (
            <ForecastPanel forecast={forecast} date={date} onDate={setDate} />
          ) : (
            <p className="notice">The forecast needs at least a week of order history.</p>
          ))}
      </aside>

      <main className="map-area">
        <RouteMap
          zones={zones}
          depots={depots}
          routes={routes}
          colors={driverColors}
          unassigned={unassigned}
          emphasized={selectedRoute ?? hoveredRoute}
          selected={selectedRoute}
          onSelect={setSelectedRoute}
          zoneForecast={zoneForecast}
        />
        {loadingDay && view === "routes" && <p className="map-status">Loading routes</p>}
      </main>

      {view === "routes" && plan && (
        <DispatchBoard
          routes={routes}
          colors={driverColors}
          selected={selectedRoute}
          onSelect={setSelectedRoute}
          onHover={setHoveredRoute}
        />
      )}
    </div>
  );
}
