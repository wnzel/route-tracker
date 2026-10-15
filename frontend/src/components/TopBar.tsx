import { SOLVER_LABELS, SOLVERS, type Solver } from "../api";
import { dayLabel } from "../lib/format";

export type View = "routes" | "forecast";

interface Props {
  days: { date: string; label: string }[];
  date: string | null;
  onDate: (date: string) => void;
  view: View;
  onView: (view: View) => void;
  solver: Solver;
  onSolver: (solver: Solver) => void;
}

export function TopBar({ days, date, onDate, view, onView, solver, onSolver }: Props) {
  const index = days.findIndex((d) => d.date === date);
  const step = (delta: number) => {
    const next = days[index + delta];
    if (next) onDate(next.date);
  };

  return (
    <header className="topbar">
      <p className="wordmark">
        Route Tracker <span>Phoenix</span>
      </p>

      <div className="day-picker" role="group" aria-label="Service day">
        <button type="button" className="icon-button" onClick={() => step(-1)} disabled={index <= 0} aria-label="Previous day">
          <svg viewBox="0 0 16 16" aria-hidden>
            <path d="M10 3 5 8l5 5" />
          </svg>
        </button>
        <select value={date ?? ""} onChange={(event) => onDate(event.target.value)} aria-label="Service day">
          {days.map((d) => (
            <option key={d.date} value={d.date}>
              {dayLabel(d.date)}, {d.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="icon-button"
          onClick={() => step(1)}
          disabled={index < 0 || index >= days.length - 1}
          aria-label="Next day"
        >
          <svg viewBox="0 0 16 16" aria-hidden>
            <path d="m6 3 5 5-5 5" />
          </svg>
        </button>
      </div>

      <div className="switch" role="group" aria-label="View">
        <button type="button" aria-pressed={view === "routes"} onClick={() => onView("routes")}>
          Routes
        </button>
        <button type="button" aria-pressed={view === "forecast"} onClick={() => onView("forecast")}>
          Next week
        </button>
      </div>

      {view === "routes" && (
        <div className="switch" role="group" aria-label="Solver">
          {SOLVERS.map((s) => (
            <button key={s} type="button" aria-pressed={solver === s} onClick={() => onSolver(s)}>
              {SOLVER_LABELS[s]}
            </button>
          ))}
        </div>
      )}
    </header>
  );
}
