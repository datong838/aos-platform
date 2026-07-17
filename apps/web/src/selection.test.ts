import { describe, expect, it } from "vitest";
import {
  applyThemeToDocument,
  resolveTheme,
} from "./lib/appearance";
import { addFilter, canAddFilter, SELECTION_LIMIT } from "./selection";

describe("appearance", () => {
  it("resolves system preference", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
  });

  it("writes data-aos-theme", () => {
    const el = document.createElement("html");
    applyThemeToDocument("dark", el);
    expect(el.getAttribute("data-aos-theme")).toBe("dark");
  });
});

describe("selection limit", () => {
  it("blocks over 10 dimensions", () => {
    const current = Array.from({ length: SELECTION_LIMIT }, (_, i) => ({
      field: `f${i}`,
      value: "v",
    }));
    const gate = canAddFilter(current, { field: "extra", value: "1" });
    expect(gate.ok).toBe(false);
    expect(() => addFilter(current, { field: "extra", value: "1" })).toThrow(
      /上限/,
    );
  });

  it("allows within limit", () => {
    const gate = canAddFilter([], { field: "site", value: "DC-East" });
    expect(gate.ok).toBe(true);
  });
});
