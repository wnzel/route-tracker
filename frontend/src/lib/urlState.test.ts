import { describe, expect, it } from "vitest";

import { readUrlState, writeUrlState } from "./urlState";

describe("url state", () => {
  it("defaults to today's routes with OR-tools", () => {
    expect(readUrlState("")).toEqual({ view: "routes", date: null, solver: "ortools" });
  });

  it("round-trips a shared link", () => {
    const state = { view: "forecast" as const, date: "2026-10-19", solver: "greedy" as const };
    expect(readUrlState(writeUrlState(state))).toEqual(state);
  });

  it("ignores values it doesn't understand", () => {
    expect(readUrlState("?view=map&date=tomorrow&solver=magic")).toEqual({
      view: "routes",
      date: null,
      solver: "ortools",
    });
  });

  it("leaves defaults out of the URL", () => {
    expect(writeUrlState({ view: "routes", date: null, solver: "ortools" })).toBe("");
  });
});
