import type { RoutePlan } from "../api";
import { drivingSaved, duration, km, percent } from "../lib/format";

interface Props {
  plan: RoutePlan;
  optimized?: RoutePlan;
  baseline?: RoutePlan;
}

export function PlanSummary({ plan, optimized, baseline }: Props) {
  const saved = optimized && baseline ? drivingSaved(optimized, baseline) : null;
  const extraOrders = optimized && baseline ? optimized.orders_assigned - baseline.orders_assigned : 0;
  const perOrder = plan.orders_assigned ? plan.total_distance_m / plan.orders_assigned : 0;

  return (
    <section className="summary" aria-label="Plan summary">
      <dl className="stats">
        <div>
          <dt>Orders served</dt>
          <dd>
            {plan.orders_assigned}
            <small> / {plan.orders_total}</small>
          </dd>
        </div>
        <div>
          <dt>Drivers</dt>
          <dd>{plan.drivers_used}</dd>
        </div>
        <div>
          <dt>Driving</dt>
          <dd>{km(plan.total_distance_m)}</dd>
        </div>
        <div>
          <dt>Per order</dt>
          <dd>{km(perOrder)}</dd>
        </div>
      </dl>
      {saved !== null && (
        <p className="comparison">
          OR-tools needs <strong>{percent(saved)} less driving</strong> than greedy dispatch
          {extraOrders > 0 && ` and serves ${extraOrders} more order${extraOrders === 1 ? "" : "s"}`}.
        </p>
      )}
      <p className="meta">Solved in {duration(plan.solve_ms)}</p>
    </section>
  );
}
