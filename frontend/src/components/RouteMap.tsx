import { latLngBounds, type LatLngTuple } from "leaflet";
import { useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Polygon, Polyline, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";

import type { Depots, OrderFeature, RouteFeature, Zones } from "../api";
import { DEPOT_COLOR, UNASSIGNED_COLOR } from "../lib/colors";
import { clock, timeWindow } from "../lib/format";
import { gridPath, toLatLng } from "../lib/geometry";

const PHOENIX: LatLngTuple = [33.5, -112.05];

interface Props {
  zones: Zones | null;
  depots: Depots | null;
  routes: RouteFeature[];
  colors: Map<number, string>;
  unassigned: OrderFeature[];
  selected: number | null;
  onSelect: (routeId: number | null) => void;
}

function FitBounds({ points }: { points: LatLngTuple[] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length > 1) {
      map.fitBounds(latLngBounds(points), { padding: [32, 32], maxZoom: 14 });
    }
  }, [map, points]);
  return null;
}

export function RouteMap({ zones, depots, routes, colors, unassigned, selected, onSelect }: Props) {
  const focus = useMemo(() => {
    const shown = selected === null ? routes : routes.filter((route) => route.id === selected);
    const points = shown.flatMap((route) => route.geometry.coordinates.map(toLatLng));
    return points.length ? points : (zones?.features.flatMap((zone) => zone.geometry.coordinates[0].map(toLatLng)) ?? []);
  }, [routes, selected, zones]);

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

        {zones?.features.map((zone) => (
          <Polygon
            key={zone.properties.name}
            positions={zone.geometry.coordinates[0].map(toLatLng)}
            pathOptions={{ color: "#94a3b8", weight: 1, dashArray: "4 4", fillOpacity: 0.02 }}
            interactive={false}
          >
            <Tooltip permanent direction="center" className="zone-label">
              {zone.properties.name}
            </Tooltip>
          </Polygon>
        ))}

        {routes.map((route) => {
          const id = Number(route.id);
          const color = colors.get(route.properties.driver) ?? "#2563eb";
          const dimmed = selected !== null && selected !== id;
          return (
            <Polyline
              key={`line-${id}`}
              positions={gridPath(route.geometry.coordinates)}
              pathOptions={{ color, weight: selected === id ? 5 : 3, opacity: dimmed ? 0.15 : 0.85 }}
              eventHandlers={{ click: () => onSelect(selected === id ? null : id) }}
            />
          );
        })}

        {routes.map((route) => {
          const id = Number(route.id);
          const color = colors.get(route.properties.driver) ?? "#2563eb";
          const dimmed = selected !== null && selected !== id;
          return route.properties.stops.map((stop, i) => (
            <CircleMarker
              key={`stop-${stop.order}`}
              center={toLatLng(route.geometry.coordinates[i + 1])}
              radius={6}
              pathOptions={{
                color,
                weight: 2,
                opacity: dimmed ? 0.3 : 1,
                fillColor: stop.kind === "pickup" ? color : "#ffffff",
                fillOpacity: dimmed ? 0.3 : 1,
              }}
              eventHandlers={{ click: () => onSelect(id) }}
            >
              <Popup>
                <strong>
                  #{stop.sequence} · {stop.customer_name}
                </strong>
                <br />
                {stop.kind === "pickup" ? "Pickup" : "Delivery"} · {stop.bags} bag{stop.bags === 1 ? "" : "s"}
                <br />
                Window {timeWindow(stop.window_start, stop.window_end)}
                <br />
                Arrives {clock(stop.arrival)} with {route.properties.driver_name}
                <br />
                {stop.load_after_bags} of {route.properties.capacity_bags} bags on board after
              </Popup>
            </CircleMarker>
          ));
        })}

        {unassigned.map((order) => (
          <CircleMarker
            key={`unassigned-${order.id}`}
            center={toLatLng(order.geometry.coordinates)}
            radius={6}
            pathOptions={{ color: UNASSIGNED_COLOR, weight: 2, dashArray: "2 2", fillColor: "#e5e7eb", fillOpacity: 1 }}
          >
            <Popup>
              <strong>{order.properties.customer_name}</strong>
              <br />
              Unassigned {order.properties.kind} · {order.properties.bags} bags
              <br />
              Window {timeWindow(order.properties.window_start, order.properties.window_end)}
            </Popup>
          </CircleMarker>
        ))}

        {depots?.features.map((depot) => (
          <CircleMarker
            key={`depot-${depot.id}`}
            center={toLatLng(depot.geometry.coordinates)}
            radius={9}
            pathOptions={{ color: "#ffffff", weight: 3, fillColor: DEPOT_COLOR, fillOpacity: 1 }}
          >
            <Tooltip direction="top" offset={[0, -8]}>
              {depot.properties.name}
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>

      <div className="legend" aria-label="Map legend">
        <span>
          <i className="dot dot-pickup" /> Pickup
        </span>
        <span>
          <i className="dot dot-delivery" /> Delivery
        </span>
        <span>
          <i className="dot dot-unassigned" /> Unassigned
        </span>
        <span>
          <i className="dot dot-depot" /> Depot
        </span>
        <small>Lines follow the street grid between stops, not exact roads.</small>
      </div>
    </div>
  );
}
