import { useEffect, useMemo, useState } from "react";

import {
  api,
  SOLVER_LABELS,
  SOLVERS,
  type Depots,
  type OrderFeature,
  type Orders,
  type RoutePlan,
  type ServiceDay,
  type Solver,
  type Zones,
} from "./api";
import { DriverList } from "./components/DriverList";
import { PlanSummary } from "./components/PlanSummary";
import { RouteMap } from "./components/RouteMap";
import { StopList } from "./components/StopList";
import { routeColor } from "./lib/colors";
import { dayLabel } from "./lib/format";

type Plans = Partial<Record<Solver, RoutePlan>>;

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export default function App() {
  const [days, setDays] = useState<ServiceDay[] | null>(null);
  const [zones, setZones] = useState<Zones | null>(null);
  const [depots, setDepots] = useState<Depots | null>(null);
  const [date, setDate] = useState<string | null>(null);
  const [solver, setSolver] = useState<Solver>("ortools");
  const [plans, setPlans] = useState<Plans>({});
  const [orders, setOrders] = useState<Orders | null>(null);
  const [selectedRoute, setSelectedRoute] = useState<number | null>(null);
  const [loadingDay, setLoadingDay] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The day list and the static map layers load once.
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([api.serviceDays(controller.signal), api.zones(controller.signal), api.depots(controller.signal)])
      .then(([serviceDays, zoneData, depotData]) => {
        setDays(serviceDays);
        setZones(zoneData);
        setDepots(depotData);
        const firstPlanned = serviceDays.find((day) => Object.keys(day.plans).length > 0) ?? serviceDays[0];
        setDate(firstPlanned?.date ?? null);
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

  const plan = plans[solver] ?? null;
  // Stable array identity so the map only refits when the plan actually changes.
  const routes = useMemo(() => plan?.routes.features ?? [], [plan]);

  // Give each driver the same color in both solvers' plans.
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

  const selected = plan?.routes.features.find((route) => route.id === selectedRoute) ?? null;

  return (
    <div className="app">
      <aside className="panel">
        <header className="panel-header">
          <h1>Route Tracker</h1>
          <p>Pickup and delivery routes for a Phoenix laundry service</p>
        </header>

        {error && (
          <div className="notice notice-error" role="alert">
            Couldn't load data ({error}). Make sure <code>docker compose up</code> is running.
          </div>
        )}

        {days && days.length === 0 && (
          <div className="notice">
            No pending orders yet. Run <code>docker compose exec web python manage.py generate_data</code>.
          </div>
        )}

        {days && days.length > 0 && (
          <div className="controls">
            <label className="field">
              <span>Service day</span>
              <select value={date ?? ""} onChange={(event) => setDate(event.target.value)}>
                {days.map((d) => (
                  <option key={d.date} value={d.date}>
                    {dayLabel(d.date)} · {d.pending_orders} orders
                  </option>
                ))}
              </select>
            </label>
            <div className="segmented" role="group" aria-label="Solver">
              {SOLVERS.map((s) => (
                <button
                  key={s}
                  type="button"
                  aria-pressed={solver === s}
                  onClick={() => {
                    setSolver(s);
                    setSelectedRoute(null);
                  }}
                >
                  {SOLVER_LABELS[s]}
                </button>
              ))}
            </div>
          </div>
        )}

        {day && !plan && !loadingDay && (
          <div className="notice">
            No {SOLVER_LABELS[solver]} plan for this day yet. Run{" "}
            <code>docker compose exec web python manage.py plan_routes --date {day.date}</code>
          </div>
        )}

        {plan && <PlanSummary plan={plan} optimized={plans.ortools} baseline={plans.greedy} />}

        {plan && (
          <DriverList
            routes={plan.routes.features}
            colors={driverColors}
            selected={selectedRoute}
            onSelect={setSelectedRoute}
            unassignedCount={plan.unassigned_orders.length}
          />
        )}

        {selected && <StopList route={selected} color={driverColors.get(selected.properties.driver)!} />}
      </aside>

      <main className="map-area">
        <RouteMap
          zones={zones}
          depots={depots}
          routes={routes}
          colors={driverColors}
          unassigned={unassigned}
          selected={selectedRoute}
          onSelect={setSelectedRoute}
        />
        {loadingDay && <div className="map-status">Loading routes…</div>}
      </main>
    </div>
  );
}
