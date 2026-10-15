import type { Position } from "geojson";
import type { LatLngTuple } from "leaflet";

export function toLatLng(position: Position): LatLngTuple {
  return [position[1], position[0]];
}

/**
 * Draw each leg as an L: east-west first, then north-south.
 * The planner measures distance on Phoenix's street grid, so this matches what it scored.
 */
export function gridPath(positions: Position[]): LatLngTuple[] {
  const path: LatLngTuple[] = [];
  const push = (point: LatLngTuple) => {
    const last = path[path.length - 1];
    if (!last || last[0] !== point[0] || last[1] !== point[1]) {
      path.push(point);
    }
  };
  positions.forEach((position, i) => {
    if (i > 0) {
      const [previousLon] = positions[i - 1];
      const [lon, lat] = position;
      if (previousLon !== lon) {
        push([positions[i - 1][1], lon]);
      }
      push([lat, lon]);
    } else {
      push(toLatLng(position));
    }
  });
  return path;
}
