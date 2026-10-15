import { describe, expect, it } from "vitest";

import { FORECAST_RAMP, labelInk, OVERFLOW_ROUTE_COLOR, rampClass, routeColor } from "./colors";

describe("colors", () => {
  it("gives eight drivers distinct colors and folds the rest to gray", () => {
    const first = Array.from({ length: 8 }, (_, i) => routeColor(i));
    expect(new Set(first).size).toBe(8);
    expect(routeColor(8)).toBe(OVERFLOW_ROUTE_COLOR);
  });

  it("bins forecasts into five classes from light to dark", () => {
    expect(rampClass(0, 10)).toBe(0);
    expect(rampClass(5, 10)).toBe(2);
    expect(rampClass(10, 10)).toBe(FORECAST_RAMP.length - 1);
    expect(rampClass(3, 0)).toBe(0);
  });

  it("puts white labels on the dark classes", () => {
    expect(labelInk(0)).not.toBe("#ffffff");
    expect(labelInk(4)).toBe("#ffffff");
  });
});
