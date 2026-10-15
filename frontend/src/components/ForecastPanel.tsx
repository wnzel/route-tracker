import type { Forecast } from "../api";
import { dayLabel, percent } from "../lib/format";
import { ForecastChart } from "./ForecastChart";

interface Props {
  forecast: Forecast;
  date: string | null;
  onDate: (date: string) => void;
}

function score(value: number | null): string {
  return value === null ? "n/a" : percent(value);
}

/** Within a tenth of the noise floor counts as about as good as the data allows. */
export function nearFloor(error: number | null, floor: number | null): boolean {
  return error !== null && floor !== null && error <= floor * 1.1;
}

export function ForecastPanel({ forecast, date, onDate }: Props) {
  const day = forecast.city.find((d) => d.date === date) ?? forecast.city[0];
  const zones = forecast.zones
    .map((zone) => ({ zone: zone.zone, ...zone.daily.find((d) => d.date === day.date)! }))
    .sort((a, b) => b.forecast - a.forecast);
  const backtest = forecast.backtest;

  return (
    <div className="forecast">
      <section className="summary" aria-label="Forecast summary">
        <div className="hero">
          <p className="hero-figure">{Math.round(day.forecast)}</p>
          <p className="hero-line">orders expected on {dayLabel(day.date)}</p>
          <p className="hero-detail">{day.booked} booked so far.</p>
        </div>
      </section>

      <ForecastChart days={forecast.city} selected={day.date} onSelect={onDate} />

      {backtest && (
        <section aria-label="Forecast accuracy">
          <h2>How accurate is it?</h2>
          <p className="note">
            Over the last eight weeks, daily city forecasts were off by {score(backtest.scores.model.city_day_wape)} on
            average. Day-to-day randomness alone accounts for {score(backtest.noise_floor.city_day_wape)}
            {nearFloor(backtest.scores.model.city_day_wape, backtest.noise_floor.city_day_wape)
              ? ", so there's little left to gain."
              : ", so there's still room to improve."}
          </p>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Method</th>
                <th scope="col">City error</th>
                <th scope="col">Zone error</th>
              </tr>
            </thead>
            <tbody>
              <tr className="row-strong">
                <th scope="row">This forecast</th>
                <td>{score(backtest.scores.model.city_day_wape)}</td>
                <td>{score(backtest.scores.model.zone_day_wape)}</td>
              </tr>
              <tr>
                <th scope="row">Four-week average</th>
                <td>{score(backtest.scores.four_week_avg.city_day_wape)}</td>
                <td>{score(backtest.scores.four_week_avg.zone_day_wape)}</td>
              </tr>
              <tr>
                <th scope="row">Same day last week</th>
                <td>{score(backtest.scores.last_week.city_day_wape)}</td>
                <td>{score(backtest.scores.last_week.zone_day_wape)}</td>
              </tr>
              <tr className="row-muted">
                <th scope="row">Perfect model</th>
                <td>{score(backtest.noise_floor.city_day_wape)}</td>
                <td>{score(backtest.noise_floor.zone_day_wape)}</td>
              </tr>
            </tbody>
          </table>
        </section>
      )}

      <section aria-label="Forecast by zone">
        <h2>By zone, {dayLabel(day.date)}</h2>
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Zone</th>
              <th scope="col">Expected</th>
              <th scope="col">Booked</th>
            </tr>
          </thead>
          <tbody>
            {zones.map((zone) => (
              <tr key={zone.zone}>
                <th scope="row">{zone.zone}</th>
                <td>{zone.forecast.toFixed(1)}</td>
                <td>{zone.booked}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
