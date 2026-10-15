import type { Solver } from "../api";
import type { View } from "../components/TopBar";

export interface UrlState {
  view: View;
  date: string | null;
  solver: Solver;
}

/** Read the shareable parts of the screen from ?view=&date=&solver=. Unknown values fall back to defaults. */
export function readUrlState(search: string): UrlState {
  const params = new URLSearchParams(search);
  const date = params.get("date");
  return {
    view: params.get("view") === "forecast" ? "forecast" : "routes",
    date: date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : null,
    solver: params.get("solver") === "greedy" ? "greedy" : "ortools",
  };
}

export function writeUrlState(state: UrlState): string {
  const params = new URLSearchParams();
  if (state.view !== "routes") params.set("view", state.view);
  if (state.date) params.set("date", state.date);
  if (state.solver !== "ortools") params.set("solver", state.solver);
  const query = params.toString();
  return query ? `?${query}` : "";
}
