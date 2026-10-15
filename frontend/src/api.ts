import type { Feature, FeatureCollection, LineString, Point, Polygon } from "geojson";

export type Solver = "ortools" | "greedy";
export type OrderKind = "pickup" | "delivery";

export const SOLVERS: Solver[] = ["ortools", "greedy"];
export const SOLVER_LABELS: Record<Solver, string> = {
  ortools: "OR-tools",
  greedy: "Greedy dispatch",
};

export interface ServiceDay {
  date: string;
  pending_orders: number;
  plans: Partial<Record<Solver, number>>;
}

export interface PlanStop {
  sequence: number;
  order: number;
  kind: OrderKind;
  bags: number;
  customer_name: string;
  window_start: string;
  window_end: string;
  arrival: string;
  load_after_bags: number;
}

export interface RouteProperties {
  driver: number;
  driver_name: string;
  capacity_bags: number;
  shift_start: string;
  shift_end: string;
  start_time: string;
  end_time: string;
  distance_m: number;
  start_load_bags: number;
  max_load_bags: number;
  stops: PlanStop[];
}

/** Geometry runs depot, each stop in sequence order, then back to the depot. */
export type RouteFeature = Feature<LineString, RouteProperties>;

export interface RoutePlan {
  id: number;
  service_date: string;
  solver: Solver;
  orders_total: number;
  orders_assigned: number;
  drivers_used: number;
  total_distance_m: number;
  solve_ms: number;
  created_at: string;
  unassigned_orders: number[];
  routes: FeatureCollection<LineString, RouteProperties>;
}

export type Zones = FeatureCollection<Polygon, { name: string; customer_count: number }>;
export type Depots = FeatureCollection<Point, { name: string }>;

export interface OrderProperties {
  customer: number;
  customer_name: string;
  zone: string | null;
  kind: OrderKind;
  status: string;
  service_date: string;
  window_start: string;
  window_end: string;
  bags: number;
}

export type OrderFeature = Feature<Point, OrderProperties>;
export type Orders = FeatureCollection<Point, OrderProperties> & { count: number };

export interface ForecastDay {
  date: string;
  forecast: number;
  booked: number;
}

export interface ZoneForecast {
  zone: string;
  total_forecast: number;
  daily: ForecastDay[];
}

export interface ForecastScore {
  zone_day_wape: number | null;
  city_day_wape: number | null;
}

export interface Backtest {
  method: string;
  test_start: string;
  test_end: string;
  scores: { model: ForecastScore; last_week: ForecastScore; four_week_avg: ForecastScore };
  noise_floor: ForecastScore;
}

export interface Forecast {
  start: string;
  days: number;
  history_end: string;
  weekday_index: Record<string, number>;
  city: ForecastDay[];
  zones: ZoneForecast[];
  backtest: Backtest | null;
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal, headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  serviceDays: (signal?: AbortSignal) => getJson<ServiceDay[]>("/api/service-days/", signal),
  zones: (signal?: AbortSignal) => getJson<Zones>("/api/zones/", signal),
  depots: (signal?: AbortSignal) => getJson<Depots>("/api/depots/", signal),
  plan: (id: number, signal?: AbortSignal) => getJson<RoutePlan>(`/api/route-plans/${id}/`, signal),
  pendingOrders: (date: string, signal?: AbortSignal) =>
    getJson<Orders>(`/api/orders/?date=${date}&status=pending&page_size=2000`, signal),
  forecast: (signal?: AbortSignal) => getJson<Forecast>("/api/forecast/?days=7", signal),
};
