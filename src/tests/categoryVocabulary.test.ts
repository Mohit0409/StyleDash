import { describe, expect, it } from "vitest";
import { CATEGORY_DESCRIPTIONS, CATEGORY_DISPLAY_ORDER, STORE_CATEGORIES } from "../data/categories";

describe("production category vocabulary", () => {
  it("keeps the 19 production product and store categories in sync", () => {
    expect(CATEGORY_DISPLAY_ORDER).toHaveLength(19);
    expect(STORE_CATEGORIES).toBe(CATEGORY_DISPLAY_ORDER);
    expect(new Set(CATEGORY_DISPLAY_ORDER).size).toBe(19);
    expect(CATEGORY_DISPLAY_ORDER).toContain("Health & Nutrition");
    expect(CATEGORY_DISPLAY_ORDER).toContain("Health & Pharmacy");
    expect(CATEGORY_DISPLAY_ORDER).toContain("General Store");
    for (const category of CATEGORY_DISPLAY_ORDER) {
      expect(CATEGORY_DESCRIPTIONS[category]).toBeTruthy();
    }
  });
});