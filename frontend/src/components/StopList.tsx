import type { RouteFeature } from "../api";
import { clock, km, timeWindow } from "../lib/format";

interface Props {
  route: RouteFeature;
  color: string;
  onClose: () => void;
}

export function StopList({ route, color, onClose }: Props) {
  const p = route.properties;
  return (
    <section className="stops-panel" aria-label={`${p.driver_name}'s stops`}>
      <div className="stops-head">
        <h2>
          <span className="route-key" style={{ background: color }} aria-hidden />
          {p.driver_name}
        </h2>
        <button type="button" className="text-button" onClick={onClose}>
          Show all drivers
        </button>
      </div>
      <p className="note">
        Leaves the depot at {clock(p.start_time)} with {p.start_load_bags} delivery bags and drives {km(p.distance_m)},
        back by {clock(p.end_time)}.
      </p>
      <table className="stops">
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Customer</th>
            <th scope="col">Arrives</th>
            <th scope="col">On board</th>
          </tr>
        </thead>
        <tbody>
          {p.stops.map((stop) => (
            <tr key={stop.order}>
              <td className="num">{stop.sequence}</td>
              <td>
                <span className="stop-name">{stop.customer_name}</span>
                <span className="stop-detail">
                  <span className={`kind kind-${stop.kind}`}>{stop.kind === "pickup" ? "Pickup" : "Delivery"}</span>{" "}
                  {stop.bags} bag{stop.bags === 1 ? "" : "s"}, window {timeWindow(stop.window_start, stop.window_end)}
                </span>
              </td>
              <td className="num">{clock(stop.arrival)}</td>
              <td className="num">{stop.load_after_bags}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
