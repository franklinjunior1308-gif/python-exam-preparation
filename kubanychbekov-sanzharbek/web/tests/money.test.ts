import { describe, expect, test } from "bun:test";
import {
  formatDuration,
  formatKgs,
  laborTotalCents,
  lineTotalCents,
  parseKgsToCents,
  parseQuantityMilli,
  trimQuantity,
} from "@/lib/money";

describe("amounts in whole tyiyn", () => {
  test("formatting groups thousands and always shows two decimals", () => {
    expect(formatKgs(123456)).toBe("1 234.56 KGS");
    expect(formatKgs(5)).toBe("0.05 KGS");
    expect(formatKgs(0)).toBe("0.00 KGS");
    expect(formatKgs(-250)).toBe("-2.50 KGS");
  });

  test("typed amounts are parsed without floating point", () => {
    expect(parseKgsToCents("120.50")).toBe(12050);
    expect(parseKgsToCents("120,5")).toBe(12050);
    expect(parseKgsToCents("7")).toBe(700);
    expect(parseKgsToCents(" 0.07 ")).toBe(7);
    expect(parseKgsToCents("0.1")).toBe(10); // the classic 0.1 + 0.2 trap does not exist here
  });

  test("invalid amounts are rejected", () => {
    for (const bad of ["", "abc", "-5", "1.234", "1..2", "12 000", "1e3"]) {
      expect(parseKgsToCents(bad)).toBeNull();
    }
  });

  test("quantities allow three decimals and must be positive", () => {
    expect(parseQuantityMilli("2")).toBe(2000);
    expect(parseQuantityMilli("0.5")).toBe(500);
    expect(parseQuantityMilli("1,25")).toBe(1250);
    expect(parseQuantityMilli("0")).toBeNull();
    expect(parseQuantityMilli("0.0001")).toBeNull();
    expect(parseQuantityMilli("-1")).toBeNull();
  });

  test("rounding is half-up, like the backend", () => {
    expect(lineTotalCents(500, 333)).toBe(167); // 0.5 x 3.33 = 1.665 -> 1.67
    expect(lineTotalCents(2000, 1050)).toBe(2100);
    expect(lineTotalCents(1333, 100)).toBe(133);
    expect(laborTotalCents(90, 120_000)).toBe(180_000);
    expect(laborTotalCents(1, 100)).toBe(2); // 1.666 -> 2
  });

  test("API quantities are shown without trailing zeros", () => {
    expect(trimQuantity("2.000")).toBe("2");
    expect(trimQuantity("0.500")).toBe("0.5");
    expect(trimQuantity("12")).toBe("12");
  });

  test("durations are shown in hours and minutes", () => {
    expect(formatDuration(150, "h", "min")).toBe("2 h 30 min");
    expect(formatDuration(120, "h", "min")).toBe("2 h");
    expect(formatDuration(45, "h", "min")).toBe("45 min");
    expect(formatDuration(-90, "h", "min")).toBe("1 h 30 min"); // sign is the caller's business
  });
});
