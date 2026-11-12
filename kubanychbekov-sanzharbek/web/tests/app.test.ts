import { describe, expect, test } from "bun:test";
import { buildQuery } from "@/lib/api-client";
import { en, ru } from "@/lib/i18n/dict";
import { pickLang, translate } from "@/lib/i18n";
import { needsReason } from "@/lib/format";
import { STATUSES } from "@/lib/types";

describe("translations", () => {
  test("Russian has exactly the same keys as English", () => {
    expect(Object.keys(ru).sort()).toEqual(Object.keys(en).sort());
  });

  test("no Russian value is empty", () => {
    for (const [key, value] of Object.entries(ru)) expect(value.length > 0, key).toBe(true);
  });

  test("every request status has a label in both languages", () => {
    for (const status of STATUSES) {
      expect(`status.${status}` in en).toBe(true);
      expect(`status.${status}` in ru).toBe(true);
    }
  });

  test("placeholders are filled", () => {
    expect(translate("en", "common.page", { page: 2, pages: 5 })).toBe("Page 2 of 5");
    expect(translate("ru", "common.page", { page: 2, pages: 5 })).toBe("Страница 2 из 5");
  });

  test("language follows the cookie, then Accept-Language", () => {
    expect(pickLang("ru", "en-US")).toBe("ru");
    expect(pickLang(undefined, "ru-RU,ru;q=0.9")).toBe("ru");
    expect(pickLang(undefined, "en-US")).toBe("en");
    expect(pickLang("xx", null)).toBe("en");
  });
});

describe("api helpers", () => {
  test("query string skips empty values", () => {
    expect(buildQuery({ page: 2, q: "", status: undefined, dir: "asc" })).toBe("?page=2&dir=asc");
    expect(buildQuery({})).toBe("");
  });
});

describe("reason rules (UX mirror of the backend)", () => {
  test("blocking and rework always need a reason", () => {
    expect(needsReason("IN_PROGRESS", "BLOCKED", "technician")).toBe(true);
    expect(needsReason("COMPLETED", "REOPENED", "customer")).toBe(true);
  });

  test("customers cancel and close without a reason, staff must give one", () => {
    expect(needsReason("SUBMITTED", "CANCELED", "customer")).toBe(false);
    expect(needsReason("SUBMITTED", "CANCELED", "dispatcher")).toBe(true);
    expect(needsReason("COMPLETED", "CLOSED", "customer")).toBe(false);
    expect(needsReason("COMPLETED", "CLOSED", "admin")).toBe(true);
  });
});
