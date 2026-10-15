import { useState } from "react";

import type { PlanStop, RouteFeature } from "../api";
import { clock, hourLabel, km, minutes, timeWindow } from "../lib/format";
import { useElementWidth } from "../lib/useElementWidth";

// The service day runs 7 AM to 7 PM; pad half an hour each side so edge stops aren't clipped.
const DAY_START = 6.5 * 60;
const DAY_END = 19.5 * 60;
const HOURS = [7, 9, 11, 13, 15, 17, 19];
const ROW_HEIGHT = 34;

interface Props {
  routes: RouteFeature[];
  colors: Map<number, string>;
  selected: number | null;
  onSelect: (routeId: number | null) => void;
  onHover: (routeId: number | null) => void;
}

interface HoveredStop {
  stop: PlanStop;
  driver: string;
  x: number;
  y: number;
}

export function DispatchBoard({ routes, colors, selected, onSelect, onHover }: Props) {
  const [trackRef, trackWidth] = useElementWidth<HTMLDivElement>();
  const [hovered, setHovered] = useState<HoveredStop | null>(null);
  const x = (time: string) => ((minutes(time) - DAY_START) / (DAY_END - DAY_START)) * trackWidth;

  return (
    <section className="board" aria-label="Dispatch board">
      <div className="board-head">
        <div className="board-title">
          <h2>Dispatch board</h2>
          <p>Each row is one driver's day. Dots mark arrival times; select a row to see its stops.</p>
        </div>
        <div className="board-columns" aria-hidden>
          <span>Stops</span>
          <span>Driving</span>
          <span>Peak load</span>
        </div>
        <div className="board-axis" ref={trackRef} aria-hidden>
          {trackWidth > 0 &&
            HOURS.map((hour) => (
              <span key={hour} style={{ left: x(`${hour}:00:00`) }}>
                {hourLabel(hour)}
              </span>
            ))}
        </div>
      </div>

      <ol className="board-rows">
        {routes.map((route) => {
          const p = route.properties;
          const id = Number(route.id);
          const color = colors.get(p.driver);
          const isSelected = selected === id;
          return (
            <li key={id}>
              <button
                type="button"
                className="board-row"
                aria-pressed={isSelected}
                onClick={() => onSelect(isSelected ? null : id)}
                onPointerEnter={() => onHover(id)}
                onPointerLeave={() => onHover(null)}
                onFocus={() => onHover(id)}
                onBlur={() => onHover(null)}
              >
                <span className="board-driver">
                  <span className="route-key" style={{ background: color }} aria-hidden />
                  {p.driver_name}
                </span>
                <span className="board-num">{p.stops.length}</span>
                <span className="board-num">{km(p.distance_m)}</span>
                <span className="board-num">
                  {p.max_load_bags}
                  <span className="of"> / {p.capacity_bags}</span>
                </span>
                <span className="board-track">
                  {trackWidth > 0 && (
                    <svg width={trackWidth} height={ROW_HEIGHT} aria-hidden>
                      {HOURS.map((hour) => (
                        <line
                          key={hour}
                          className="gridline"
                          x1={x(`${hour}:00:00`)}
                          x2={x(`${hour}:00:00`)}
                          y1={0}
                          y2={ROW_HEIGHT}
                        />
                      ))}
                      <rect
                        className="shift"
                        x={x(p.shift_start)}
                        width={x(p.shift_end) - x(p.shift_start)}
                        y={ROW_HEIGHT / 2 - 6}
                        height={12}
                        rx={6}
                      />
                      <line
                        x1={x(p.start_time)}
                        x2={x(p.end_time)}
                        y1={ROW_HEIGHT / 2}
                        y2={ROW_HEIGHT / 2}
                        stroke={color}
                        strokeWidth={2}
                        strokeLinecap="round"
                      />
                      {p.stops.map((stop) => (
                        <g
                          key={stop.order}
                          className="board-stop"
                          onPointerEnter={(event) => {
                            const box = (event.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
                            setHovered({ stop, driver: p.driver_name, x: box.left + x(stop.arrival), y: box.top });
                          }}
                          onPointerLeave={() => setHovered(null)}
                        >
                          <circle cx={x(stop.arrival)} cy={ROW_HEIGHT / 2} r={12} fill="transparent" />
                          <circle
                            cx={x(stop.arrival)}
                            cy={ROW_HEIGHT / 2}
                            r={4.5}
                            fill={stop.kind === "pickup" ? color : "#ffffff"}
                            stroke={stop.kind === "pickup" ? "#ffffff" : color}
                            strokeWidth={2}
                          />
                        </g>
                      ))}
                    </svg>
                  )}
                </span>
              </button>
            </li>
          );
        })}
      </ol>

      {hovered && (
        <div className="tooltip" role="status" style={{ left: hovered.x, top: hovered.y }}>
          <strong>{clock(hovered.stop.arrival)}</strong>
          <span>
            Stop {hovered.stop.sequence} for {hovered.driver}: {hovered.stop.customer_name}
          </span>
          <span>
            {hovered.stop.kind === "pickup" ? "Pickup" : "Delivery"} of {hovered.stop.bags} bag
            {hovered.stop.bags === 1 ? "" : "s"}, window {timeWindow(hovered.stop.window_start, hovered.stop.window_end)}
          </span>
        </div>
      )}
    </section>
  );
}
