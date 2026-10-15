import type { RouteFeature } from "../api";
import { clock, timeWindow } from "../lib/format";

interface Props {
  route: RouteFeature;
  color: string;
}

export function StopList({ route, color }: Props) {
  const p = route.properties;
  return (
    <section aria-label={`${p.driver_name}'s stops`}>
      <h2>{p.driver_name}'s route</h2>
      <p className="meta">
        Leaves the depot at {clock(p.start_time)} with {p.start_load_bags} delivery bags, back by {clock(p.end_time)}.
      </p>
      <ol className="stops">
        {p.stops.map((stop) => (
          <li key={stop.order} className="stop">
            <span className="stop-number" style={{ borderColor: color, color }}>
              {stop.sequence}
            </span>
            <span className="stop-main">
              <span className="stop-name">
                {stop.customer_name}
                <span className={`chip chip-${stop.kind}`}>
                  {stop.kind === "pickup" ? "Pickup" : "Delivery"} · {stop.bags} bag{stop.bags === 1 ? "" : "s"}
                </span>
              </span>
              <span className="stop-detail">
                Arrives {clock(stop.arrival)} · window {timeWindow(stop.window_start, stop.window_end)}
              </span>
            </span>
            <span className="stop-load" title="Bags on board after this stop">
              {stop.load_after_bags}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
