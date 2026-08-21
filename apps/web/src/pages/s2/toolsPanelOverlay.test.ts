import { describe, expect, it } from "vitest";
import {
  decodeToolsPanelOverlay,
  encodeToolsPanelOverlay,
  isPanelMetaToolId,
} from "./toolsPanelOverlay";

describe("toolsPanelOverlay W-T1", () => {
  it("encode/decode roundtrip keeps tools mode hitl", () => {
    const encoded = encodeToolsPanelOverlay({
      tools: [
        { id: "query.objects", name: "Query", kind: "query" },
        { id: "fn.echo", name: "Echo", category: "function" },
      ],
      mode: "prompted",
      hitl: "draft",
    });
    expect(encoded.some((i) => i.id === "panel.cfg.mode" && i.name === "prompted")).toBe(true);
    expect(encoded.some((i) => i.id === "panel.cfg.hitl" && i.name === "draft")).toBe(true);
    const decoded = decodeToolsPanelOverlay(encoded, {
      defaultCategories: ["action", "query"],
    });
    expect(decoded.mode).toBe("prompted");
    expect(decoded.hitl).toBe("draft");
    expect(decoded.toolItems.map((t) => t.id).sort()).toEqual(["fn.echo", "query.objects"]);
    expect(decoded.categories.has("query")).toBe(true);
    expect(decoded.categories.has("function")).toBe(true);
  });

  it("empty overlay falls back to default categories", () => {
    const decoded = decodeToolsPanelOverlay([], {
      defaultCategories: ["action", "query", "function"],
    });
    expect(decoded.toolItems).toEqual([]);
    expect([...decoded.categories].sort()).toEqual(["action", "function", "query"]);
  });

  it("ignores panel meta as tools", () => {
    expect(isPanelMetaToolId("panel.cfg.mode")).toBe(true);
    expect(isPanelMetaToolId("query.objects")).toBe(false);
  });
});
