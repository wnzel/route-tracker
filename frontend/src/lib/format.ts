export function km(meters: number): string {
  const value = (meters / 1000).toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return `${value} km`;
}

/** "13:07:00" -> "1:07 PM" */
export function clock(time: string): string {
  const [hours, minutes] = time.split(":").map(Number);
  const suffix = hours >= 12 ? "PM" : "AM";
  const hour12 = hours % 12 === 0 ? 12 : hours % 12;
  return `${hour12}:${String(minutes).padStart(2, "0")} ${suffix}`;
}

export function timeWindow(start: string, end: string): string {
  return `${clock(start)} – ${clock(end)}`;
}

/** "2026-10-14" -> "Wed, Oct 14". Parsed at noon so no time zone can shift the day. */
export function dayLabel(isoDate: string): string {
  return new Date(`${isoDate}T12:00:00`).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export function duration(ms: number): string {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

interface PlanTotals {
  orders_assigned: number;
  total_distance_m: number;
}

/**
 * How much less driving the first plan needs than the second.
 * Compares totals when both serve the same orders, otherwise distance per order.
 */
export function drivingSaved(plan: PlanTotals, baseline: PlanTotals): number | null {
  if (!plan.orders_assigned || !baseline.orders_assigned || !baseline.total_distance_m) {
    return null;
  }
  if (plan.orders_assigned === baseline.orders_assigned) {
    return 1 - plan.total_distance_m / baseline.total_distance_m;
  }
  const perOrder = plan.total_distance_m / plan.orders_assigned;
  const baselinePerOrder = baseline.total_distance_m / baseline.orders_assigned;
  return 1 - perOrder / baselinePerOrder;
}

export function percent(fraction: number): string {
  return `${(fraction * 100).toFixed(1)}%`;
}
