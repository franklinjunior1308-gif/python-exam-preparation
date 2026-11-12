import { describe, expect, test } from "bun:test";
import {
  addDays,
  formatClock,
  isoToZonedInput,
  localParts,
  rangeIso,
  weekdayOf,
  weekStart,
  zonedInputToIso,
} from "@/lib/time";

const BISHKEK = "Asia/Bishkek"; // UTC+6 all year

describe("organization-zone conversion", () => {
  test("wall time in Bishkek becomes the right UTC instant", () => {
    expect(zonedInputToIso("2026-11-16T10:00", BISHKEK)).toBe("2026-11-16T04:00:00.000Z");
    expect(zonedInputToIso("2026-11-16T00:00", BISHKEK)).toBe("2026-11-15T18:00:00.000Z");
  });

  test("round trip keeps the typed value", () => {
    const iso = zonedInputToIso("2026-11-16T14:30", BISHKEK);
    expect(isoToZonedInput(iso, BISHKEK)).toBe("2026-11-16T14:30");
  });

  test("zones with daylight saving use the offset of that date", () => {
    expect(zonedInputToIso("2026-07-01T12:00", "Europe/Berlin")).toBe("2026-07-01T10:00:00.000Z");
    expect(zonedInputToIso("2026-01-15T12:00", "Europe/Berlin")).toBe("2026-01-15T11:00:00.000Z");
  });

  test("the browser's own zone does not matter", () => {
    const iso = "2026-11-16T04:00:00.000Z";
    expect(formatClock(iso, BISHKEK)).toBe("10:00");
    expect(formatClock(iso, "UTC")).toBe("04:00");
    expect(localParts(iso, BISHKEK)).toEqual({ date: "2026-11-16", minutes: 600 });
  });

  test("a late evening instant lands on the next local day", () => {
    expect(localParts("2026-11-16T19:30:00.000Z", BISHKEK).date).toBe("2026-11-17");
  });
});

describe("calendar helpers", () => {
  test("addDays crosses month and year borders", () => {
    expect(addDays("2026-11-30", 1)).toBe("2026-12-01");
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
  });

  test("weeks start on Monday", () => {
    expect(weekdayOf("2026-11-16")).toBe(0); // Monday
    expect(weekStart("2026-11-18")).toBe("2026-11-16");
    expect(weekStart("2026-11-22")).toBe("2026-11-16"); // Sunday belongs to the week before
    expect(weekStart("2026-11-16")).toBe("2026-11-16");
  });

  test("a week range is seven local days long", () => {
    const { from, to } = rangeIso("2026-11-16", 7, BISHKEK);
    expect(new Date(to).getTime() - new Date(from).getTime()).toBe(7 * 24 * 3600 * 1000);
    expect(from).toBe("2026-11-15T18:00:00.000Z");
  });
});
