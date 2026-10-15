// Distinct hues that hold up on a light basemap.
const ROUTE_COLORS = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2", "#db2777", "#65a30d"];

export function routeColor(index: number): string {
  return ROUTE_COLORS[index % ROUTE_COLORS.length];
}

export const UNASSIGNED_COLOR = "#6b7280";
export const DEPOT_COLOR = "#111827";
