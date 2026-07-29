import { describe, expect, it } from "vitest";
import {
  bindVariableToConfig,
  filterCanvasNodesByQuery,
  formatModuleVariableRef,
  normalizeModuleVariablesPayload,
} from "./canvasWidgets";
import { formatVariableDisplayValue, listModuleVariableRefs } from "./CanvasTabs";

describe("W4-B1 · module variable helpers", () => {
  it("formatModuleVariableRef adds $ prefix once", () => {
    expect(formatModuleVariableRef("selectedStatus")).toBe("$selectedStatus");
    expect(formatModuleVariableRef("$already")).toBe("$already");
    expect(formatModuleVariableRef("  ")).toBe("");
  });

  it("normalizeModuleVariablesPayload maps API items", () => {
    const items = normalizeModuleVariablesPayload({
      items: [
        {
          id: "var-1",
          name: "pageSize",
          varType: "number",
          group: "数值",
          initialValue: 20,
          currentValue: 20,
          description: "每页",
        },
        { id: "", name: "bad" },
      ],
    });
    expect(items).toHaveLength(1);
    expect(items[0].name).toBe("pageSize");
    expect(items[0].varType).toBe("number");
  });

  it("bindVariableToConfig sets and clears boundVariable", () => {
    expect(bindVariableToConfig({ objectType: "WorkOrder" }, "site")).toEqual({
      objectType: "WorkOrder",
      boundVariable: "site",
    });
    expect(bindVariableToConfig({ boundVariable: "site", objectType: "WorkOrder" }, null)).toEqual({
      objectType: "WorkOrder",
    });
  });

  it("filterCanvasNodesByQuery matches title/kind/id", () => {
    const nodes = [
      { id: "n-table", title: "Object Table", kind: "table" },
      { id: "n-filter", title: "Filter · site", kind: "filter" },
    ];
    expect(filterCanvasNodesByQuery(nodes, "table")).toHaveLength(1);
    expect(filterCanvasNodesByQuery(nodes, "FILTER")).toHaveLength(1);
    expect(filterCanvasNodesByQuery(nodes, "")).toHaveLength(2);
  });

  it("CanvasTabs listModuleVariableRefs / display value", () => {
    const refs = listModuleVariableRefs([
      { id: "1", name: "a", varType: "string", currentValue: "x" },
      { id: "2", name: "b", varType: "number", initialValue: 3 },
    ]);
    expect(refs).toEqual(["$a", "$b"]);
    expect(
      formatVariableDisplayValue({ id: "1", name: "a", varType: "string", currentValue: { k: 1 } }),
    ).toBe('{"k":1}');
  });
});
