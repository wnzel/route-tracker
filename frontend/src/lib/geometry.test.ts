import { describe, expect, it } from "vitest";

import { gridPath, toLatLng } from "./geometry";

describe("geometry", () => {
  it("swaps GeoJSON lon/lat into Leaflet lat/lng", () => {
    expect(toLatLng([-112.07, 33.45])).toEqual([33.45, -112.07]);
  });

  it("turns each leg into an east-west then north-south L", () => {
    const path = gridPath([
      [-112.0, 33.4],
      [-111.9, 33.5],
      [-112.0, 33.4],
    ]);
    expect(path).toEqual([
      [33.4, -112.0],
      [33.4, -111.9],
      [33.5, -111.9],
      [33.5, -112.0],
      [33.4, -112.0],
    ]);
  });

  it("skips the corner when a leg is already straight", () => {
    expect(
      gridPath([
        [-112.0, 33.4],
        [-112.0, 33.5],
      ]),
    ).toEqual([
      [33.4, -112.0],
      [33.5, -112.0],
    ]);
  });
});
