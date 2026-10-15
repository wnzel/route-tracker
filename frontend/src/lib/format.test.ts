import { describe, expect, it } from "vitest";

import { clock, dayLabel, drivingSaved, duration, km, percent, timeWindow } from "./format";

describe("format", () => {
  it("formats meters as kilometers", () => {
    expect(km(681976)).toBe("682.0 km");
    expect(km(1234567)).toBe("1,234.6 km");
  });

  it("formats 24-hour times as 12-hour clock times", () => {
    expect(clock("07:00:00")).toBe("7:00 AM");
    expect(clock("12:30:00")).toBe("12:30 PM");
    expect(clock("13:07:00")).toBe("1:07 PM");
    expect(clock("00:05:00")).toBe("12:05 AM");
    expect(timeWindow("11:00:00", "13:00:00")).toBe("11:00 AM – 1:00 PM");
  });

  it("shows short solve times in milliseconds", () => {
    expect(duration(6)).toBe("6 ms");
    expect(duration(5013)).toBe("5.0 s");
  });

  it("labels a date without shifting the day", () => {
    expect(dayLabel("2026-10-14")).toBe("Wed, Oct 14");
  });

  it("compares total distance when both plans serve the same orders", () => {
    const saved = drivingSaved({ orders_assigned: 60, total_distance_m: 682_000 }, { orders_assigned: 60, total_distance_m: 970_700 });
    expect(saved).toBeCloseTo(0.2974, 3);
    expect(percent(saved!)).toBe("29.7%");
  });

  it("compares distance per order when the plans serve different counts", () => {
    const saved = drivingSaved({ orders_assigned: 77, total_distance_m: 756_300 }, { orders_assigned: 76, total_distance_m: 1_069_800 });
    expect(saved).toBeCloseTo(1 - 756_300 / 77 / (1_069_800 / 76), 6);
  });

  it("has nothing to compare against an empty plan", () => {
    expect(drivingSaved({ orders_assigned: 5, total_distance_m: 100 }, { orders_assigned: 0, total_distance_m: 0 })).toBeNull();
  });
});
