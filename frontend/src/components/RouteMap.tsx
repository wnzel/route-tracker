import { latLngBounds, type LatLngTuple } from "leaflet";
import { useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Polygon, Polyline, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";

import type { Depots, OrderFeature, RouteFeature, Zones } from "../api";
import { DEPOT_COLOR, FORECAST_RAMP, labelInk, rampClass, UNASSIGNED_COLOR } from "../lib/colors";
import { clock, timeWindow } from "../lib/format";
import { gridPath, toLatLng } from "../lib/geometry";

const PHOENIX: LatLngTuple = [33.5, -112.05];

interface Props {
  zones: Zones | null;
  depots: Depots | null;
  routes: RouteFeature[];
  colors: Map<number, string>;
  unassigned: OrderFeature[];
  /** Selected or hovered route; the others fade. */
  emphasized: number | null;
  selected: number | null;
  onSelect: (routeId: number | null) => void;
  /** When set, zones are shaded by expected orders and routes are hidden. */
  zoneForecast: Map<string, number> | null;
}

const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function FitBounds({ points }: { points: LatLngTuple[] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length > 1) {
      map.fitBounds(latLngBounds(points), { padding: [28, 28], maxZoom: 14, animate: !prefersReducedMotion() });
    }
  }, [map, points]);
  return null;
}

export function RouteMap({ zones, depots, routes, colors, unassigned, emphasized, selected, onSelect, zoneForecast }: Props) {
  const showRoutes = zoneForecast === null;
  const focus = useMemo(() => {
    const shown = !showRoutes ? [] : selected === null ? routes : routes.filter((route) => route.id === selected);
    const points = shown.flatMap((route) => route.geometry.coordinates.map(toLatLng));
    return points.length ? points : (zones?.features.flatMap((zone) => zone.geometry.coordinates[0].map(toLatLng)) ?? []);
  }, [routes, selected, zones, showRoutes]);
  const forecastMax = zoneForecast ? Math.max(...zoneForecast.values()) : 0;

  return (
    <div className="map-wrap">
      <MapContainer center={PHOENIX} zoom={11} className="map" preferCanvas>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
          className="basemap"
        />
        <FitBounds points={focus} />

        {zones?.features.map((zone) => {
          const expected = zoneForecast?.get(zone.properties.name);
          const shade = expected === undefined ? null : rampClass(expected, forecastMax);
          return (
            <Polygon
              key={`${zone.properties.name}-${shade ?? "outline"}`}
              positions={zone.geometry.coordinates[0].map(toLatLng)}
              pathOptions={
                shade === null
                  ? { color: "#8b94a1", weight: 1, fillOpacity: 0 }
                  : { color: "#ffffff", weight: 2, fillColor: FORECAST_RAMP[shade], fillOpacity: 0.82 }
              }
              interactive={false}
            >
              <Tooltip permanent direction="center" className="zone-label">
                <span style={shade === null ? undefined : { color: labelInk(shade) }}>
                  {zone.properties.name}
                  {expected !== undefined && <b>{expected.toFixed(1)}</b>}
                </span>
              </Tooltip>
            </Polygon>
          );
        })}

        {showRoutes &&
          routes.map((route) => {
            const id = Number(route.id);
            const color = colors.get(route.properties.driver);
            const faded = emphasized !== null && emphasized !== id;
            return (
              <Polyline
                key={`line-${id}`}
                positions={gridPath(route.geometry.coordinates)}
                pathOptions={{ color, weight: emphasized === id ? 4 : 2.5, opacity: faded ? 0.12 : 0.9 }}
                eventHandlers={{ click: () => onSelect(selected === id ? null : id) }}
              />
            );
          })}

        {showRoutes &&
          routes.map((route) => {
            const id = Number(route.id);
            const color = colors.get(route.properties.driver);
            const faded = emphasized !== null && emphasized !== id;
            return route.properties.stops.map((stop, i) => (
              <CircleMarker
                key={`stop-${stop.order}`}
                center={toLatLng(route.geometry.coordinates[i + 1])}
                radius={5}
                pathOptions={{
                  color: stop.kind === "pickup" ? "#ffffff" : color,
                  weight: 2,
                  opacity: faded ? 0.25 : 1,
                  fillColor: stop.kind === "pickup" ? color : "#ffffff",
                  fillOpacity: faded ? 0.25 : 1,
                }}
                eventHandlers={{ click: () => onSelect(id) }}
              >
                <Popup>
                  <p className="popup-title">{stop.customer_name}</p>
                  <p>
                    Stop {stop.sequence} for {route.properties.driver_name}, arrives {clock(stop.arrival)}
                  </p>
                  <p>
                    {stop.kind === "pickup" ? "Pickup" : "Delivery"} of {stop.bags} bag{stop.bags === 1 ? "" : "s"}, window{" "}
                    {timeWindow(stop.window_start, stop.window_end)}
                  </p>
                  <p>
                    {stop.load_after_bags} of {route.properties.capacity_bags} bags on board after this stop
                  </p>
                </Popup>
              </CircleMarker>
            ));
          })}

        {showRoutes &&
          unassigned.map((order) => (
            <CircleMarker
              key={`unassigned-${order.id}`}
              center={toLatLng(order.geometry.coordinates)}
              radius={5}
              pathOptions={{ color: UNASSIGNED_COLOR, weight: 2, dashArray: "2 2", fillColor: "#e5e7eb", fillOpacity: 1 }}
            >
              <Popup>
                <p className="popup-title">{order.properties.customer_name}</p>
                <p>
                  Unassigned {order.properties.kind} of {order.properties.bags} bags, window{" "}
                  {timeWindow(order.properties.window_start, order.properties.window_end)}
                </p>
              </Popup>
            </CircleMarker>
          ))}

        {depots?.features.map((depot) => (
          <CircleMarker
            key={`depot-${depot.id}`}
            center={toLatLng(depot.geometry.coordinates)}
            radius={8}
            pathOptions={{ color: "#ffffff", weight: 3, fillColor: DEPOT_COLOR, fillOpacity: 1 }}
          >
            <Tooltip direction="top" offset={[0, -8]}>
              {depot.properties.name}
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>

      {showRoutes ? (
        <div className="legend" aria-label="Map key">
          <span>
            <i className="dot dot-pickup" /> Pickup
          </span>
          <span>
            <i className="dot dot-delivery" /> Delivery
          </span>
          <span>
            <i className="dot dot-unassigned" /> Didn't fit
          </span>
          <span>
            <i className="dot dot-depot" /> Depot
          </span>
          <small>Lines follow the street grid between stops, not exact roads.</small>
        </div>
      ) : (
        <div className="legend" aria-label="Map key">
          <span className="legend-title">Expected orders</span>
          <span className="ramp" aria-hidden>
            {FORECAST_RAMP.map((color) => (
              <i key={color} style={{ background: color }} />
            ))}
          </span>
          <span className="ramp-ends">
            <span>0</span>
            <span>{forecastMax.toFixed(0)}</span>
          </span>
        </div>
      )}
    </div>
  );
}
