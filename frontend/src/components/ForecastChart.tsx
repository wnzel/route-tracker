import { useState } from "react";

import type { ForecastDay } from "../api";
import { dayLabel, shortDayLabel } from "../lib/format";
import { useElementWidth } from "../lib/useElementWidth";

const PLOT_HEIGHT = 150;
const AXIS_HEIGHT = 26;
const LEFT = 30;
const TOP = 20;
const MAX_COLUMN = 24;

interface Props {
  days: ForecastDay[];
  selected: string | null;
  onSelect: (date: string) => void;
}

function niceStep(max: number): number {
  const rough = max / 4;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  return [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((step) => step >= rough) ?? rough;
}

/** Column with a 4px rounded data end and a square foot on the baseline. */
function columnPath(x: number, width: number, top: number, base: number): string {
  const r = Math.min(4, (base - top) / 2, width / 2);
  return `M${x},${base} V${top + r} Q${x},${top} ${x + r},${top} H${x + width - r} Q${x + width},${top} ${x + width},${top + r} V${base} Z`;
}

export function ForecastChart({ days, selected, onSelect }: Props) {
  const [ref, width] = useElementWidth<HTMLDivElement>();
  const [hovered, setHovered] = useState<string | null>(null);

  const peak = Math.max(1, ...days.flatMap((d) => [d.forecast, d.booked]));
  const step = niceStep(peak);
  const yMax = Math.ceil(peak / step) * step;
  const ticks = Array.from({ length: Math.round(yMax / step) + 1 }, (_, i) => i * step);
  const base = TOP + PLOT_HEIGHT;
  const y = (value: number) => base - (value / yMax) * PLOT_HEIGHT;
  const band = width > LEFT ? (width - LEFT) / days.length : 0;
  const columnWidth = Math.min(MAX_COLUMN, band * 0.5);
  const center = (i: number) => LEFT + band * i + band / 2;
  const shown = days.find((d) => d.date === (hovered ?? selected));
  const shownIndex = shown ? days.indexOf(shown) : -1;

  return (
    <figure className="chart">
      <figcaption>
        <span>Orders per day, city-wide</span>
        <span className="legend-keys" aria-hidden>
          <span>
            <i className="key-bar" /> Forecast
          </span>
          <span>
            <i className="key-tick" /> Booked
          </span>
        </span>
      </figcaption>
      <div className="chart-body" ref={ref}>
        {width > 0 && (
          <svg width={width} height={base + AXIS_HEIGHT} role="group" aria-label="Forecast by day">
            {ticks.map((tick) => (
              <g key={tick}>
                <line className={tick === 0 ? "baseline" : "gridline"} x1={LEFT} x2={width} y1={y(tick)} y2={y(tick)} />
                <text className="tick" x={LEFT - 6} y={y(tick)} dy="0.32em" textAnchor="end">
                  {tick}
                </text>
              </g>
            ))}
            {days.map((day, i) => {
              const isSelected = day.date === selected;
              const label = `${dayLabel(day.date)}: ${Math.round(day.forecast)} orders forecast, ${day.booked} booked`;
              return (
                <g
                  key={day.date}
                  className="column"
                  role="button"
                  tabIndex={0}
                  aria-label={label}
                  aria-pressed={isSelected}
                  onClick={() => onSelect(day.date)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelect(day.date);
                    }
                  }}
                  onPointerEnter={() => setHovered(day.date)}
                  onPointerLeave={() => setHovered(null)}
                  onFocus={() => setHovered(day.date)}
                  onBlur={() => setHovered(null)}
                >
                  <rect className="hit" x={LEFT + band * i} y={TOP} width={band} height={PLOT_HEIGHT} />
                  <path
                    className={isSelected ? "bar bar-selected" : "bar"}
                    d={columnPath(center(i) - columnWidth / 2, columnWidth, y(day.forecast), base)}
                  />
                  <line
                    className="booked"
                    x1={center(i) - columnWidth / 2 - 4}
                    x2={center(i) + columnWidth / 2 + 4}
                    y1={y(day.booked)}
                    y2={y(day.booked)}
                  />
                  <text
                    className={isSelected ? "day day-selected" : "day"}
                    x={center(i)}
                    y={base + 17}
                    textAnchor="middle"
                  >
                    {shortDayLabel(day.date)}
                  </text>
                  {isSelected && (
                    <text className="cap" x={center(i)} y={Math.min(y(day.forecast), y(day.booked)) - 7} textAnchor="middle">
                      {Math.round(day.forecast)}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        )}
        {shown && hovered && width > 0 && (
          <div className="chart-tooltip" style={{ left: Math.min(Math.max(center(shownIndex), 70), width - 70) }}>
            <strong>{Math.round(shown.forecast)} forecast</strong>
            <span>{shown.booked} booked</span>
            <span>{dayLabel(shown.date)}</span>
          </div>
        )}
      </div>
      <table className="visually-hidden">
        <caption>Forecast and booked orders by day</caption>
        <thead>
          <tr>
            <th scope="col">Day</th>
            <th scope="col">Forecast</th>
            <th scope="col">Booked</th>
          </tr>
        </thead>
        <tbody>
          {days.map((day) => (
            <tr key={day.date}>
              <td>{dayLabel(day.date)}</td>
              <td>{day.forecast}</td>
              <td>{day.booked}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
