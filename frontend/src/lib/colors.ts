// Route colors: the dataviz reference categorical palette in its validated order. Every
// adjacent pair clears the colorblind separation checks on the gray basemap; the lighter
// hues sit under 3:1 contrast, so routes are always labeled by driver name on the dispatch
// board rather than identified by color alone.
const ROUTE_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];

// Past eight drivers, extra routes share a neutral gray instead of a generated ninth hue.
export const OVERFLOW_ROUTE_COLOR = "#8a8f98";

export function routeColor(index: number): string {
  return ROUTE_COLORS[index] ?? OVERFLOW_ROUTE_COLOR;
}

export const UNASSIGNED_COLOR = "#6b7280";
export const DEPOT_COLOR = "#151922";

// Forecast map: one blue hue, light to dark, five classes. Validated as an ordinal ramp
// (the lightest step still clears 2:1 against white).
export const FORECAST_RAMP = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b"];

/** Equal-width class for `value` on a 0..max scale. */
export function rampClass(value: number, max: number): number {
  if (max <= 0) return 0;
  return Math.min(FORECAST_RAMP.length - 1, Math.floor((value / max) * FORECAST_RAMP.length));
}

/** Labels sit inside the fill, so pick ink or white by how dark the class is. */
export function labelInk(classIndex: number): string {
  return classIndex >= 2 ? "#ffffff" : "#151922";
}
