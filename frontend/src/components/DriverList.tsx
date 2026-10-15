import type { RouteFeature } from "../api";
import { clock, km } from "../lib/format";

interface Props {
  routes: RouteFeature[];
  colors: Map<number, string>;
  selected: number | null;
  onSelect: (routeId: number | null) => void;
  unassignedCount: number;
}

export function DriverList({ routes, colors, selected, onSelect, unassignedCount }: Props) {
  return (
    <section aria-label="Drivers">
      <h2>Drivers</h2>
      <ul className="drivers">
        {routes.map((route) => {
          const p = route.properties;
          const id = Number(route.id);
          const color = colors.get(p.driver);
          return (
            <li key={id}>
              <button
                type="button"
                className="driver"
                aria-pressed={selected === id}
                onClick={() => onSelect(selected === id ? null : id)}
              >
                <span className="swatch" style={{ background: color }} aria-hidden />
                <span className="driver-main">
                  <span className="driver-name">{p.driver_name}</span>
                  <span className="driver-detail">
                    {p.stops.length} stops · {km(p.distance_m)} · {clock(p.start_time)} – {clock(p.end_time)}
                  </span>
                  <span className="load" title={`Most bags on board: ${p.max_load_bags} of ${p.capacity_bags}`}>
                    <span
                      className="load-fill"
                      style={{ width: `${(p.max_load_bags / p.capacity_bags) * 100}%`, background: color }}
                    />
                  </span>
                </span>
                <span className="driver-load">
                  {p.max_load_bags}/{p.capacity_bags}
                  <small>bags</small>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      {unassignedCount > 0 && (
        <p className="unassigned-note">
          {unassignedCount} order{unassignedCount === 1 ? "" : "s"} couldn't fit any route (gray on the map).
        </p>
      )}
    </section>
  );
}
