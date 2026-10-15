import { SOLVER_LABELS, type RoutePlan } from "../api";
import { drivingSaved, duration, km, percent, plural } from "../lib/format";

interface Props {
  plan: RoutePlan;
  optimized?: RoutePlan;
  baseline?: RoutePlan;
}

export function RouteSummary({ plan, optimized, baseline }: Props) {
  const saved = optimized && baseline ? drivingSaved(optimized, baseline) : null;
  const extra = optimized && baseline ? optimized.orders_assigned - baseline.orders_assigned : 0;
  const perOrder = plan.orders_assigned ? plan.total_distance_m / plan.orders_assigned : 0;

  return (
    <section className="summary" aria-label="Plan summary">
      {saved !== null && optimized && baseline ? (
        <div className="hero">
          <p className="hero-figure">{percent(saved)}</p>
          {/* Non-breaking hyphen so "OR-tools" never splits across lines. */}
          <p className="hero-line">less driving with OR&#8209;tools than greedy dispatch</p>
          <p className="hero-detail">
            {km(optimized.total_distance_m)} instead of {km(baseline.total_distance_m)}
            {extra === 0
              ? ` for the same ${optimized.orders_assigned} orders.`
              : `, while serving ${plural(Math.abs(extra), "order")} ${extra > 0 ? "more" : "fewer"}.`}
          </p>
        </div>
      ) : (
        <div className="hero">
          <p className="hero-line">Plan both solvers for this day to compare them.</p>
        </div>
      )}

      <dl className="facts">
        <dt>Plan shown</dt>
        <dd>{SOLVER_LABELS[plan.solver]}</dd>
        <dt>Orders served</dt>
        <dd>
          {plan.orders_assigned} of {plan.orders_total}
        </dd>
        <dt>Drivers out</dt>
        <dd>{plan.drivers_used}</dd>
        <dt>Driving</dt>
        <dd>{km(plan.total_distance_m)}</dd>
        <dt>Per order</dt>
        <dd>{km(perOrder)}</dd>
        <dt>Solved in</dt>
        <dd>{duration(plan.solve_ms)}</dd>
      </dl>

      {plan.unassigned_orders.length > 0 && (
        <p className="note">
          {plural(plan.unassigned_orders.length, "order")} didn't fit any route. They're the gray dashed dots on the map.
        </p>
      )}
    </section>
  );
}
