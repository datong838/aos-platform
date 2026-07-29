import { describe, expect, it } from "vitest";
import {
  deriveMockFields,
  displayFieldLabel,
  fieldsToEntryParams,
  paramsToFields,
  type InterfaceField,
} from "./ModuleInterfacePage";

describe("ModuleInterfacePage · paramsToFields", () => {
  it("maps key/type without direction as input", () => {
    const fields = paramsToFields([{ key: "orderId", type: "string", required: true }]);
    expect(fields).toHaveLength(1);
    expect(fields[0].name).toBe("orderId");
    expect(fields[0].type).toBe("string");
    expect(fields[0].direction).toBe("input");
  });

  it("maps name + direction output", () => {
    const fields = paramsToFields([
      { name: "selectedId", type: "string", direction: "output" },
    ]);
    expect(fields[0].direction).toBe("output");
    expect(fields[0].name).toBe("selectedId");
  });

  it("skips empty names", () => {
    expect(paramsToFields([{ type: "string" }, { name: "ok", type: "number" }])).toHaveLength(1);
  });

  it("handles null/empty", () => {
    expect(paramsToFields(null)).toEqual([]);
    expect(paramsToFields([])).toEqual([]);
  });
});

describe("ModuleInterfacePage · fieldsToEntryParams", () => {
  it("serializes name/key/type/direction and drops blank names", () => {
    const fields: InterfaceField[] = [
      { id: "1", name: "selection", type: "WorkOrder[]", direction: "input" },
      { id: "2", name: "  ", type: "string", direction: "output" },
      { id: "3", name: "selectedId", type: "string", direction: "output" },
    ];
    const params = fieldsToEntryParams(fields);
    expect(params).toHaveLength(2);
    expect(params[0]).toEqual({
      name: "selection",
      key: "selection",
      type: "WorkOrder[]",
      direction: "input",
    });
    expect(params[1].direction).toBe("output");
  });

  it("round-trips with paramsToFields", () => {
    const original: InterfaceField[] = [
      { id: "a", name: "filterStatus", type: "string", direction: "input" },
      { id: "b", name: "selectedId", type: "string", direction: "output" },
    ];
    const again = paramsToFields(fieldsToEntryParams(original));
    expect(again.map((f) => ({ name: f.name, type: f.type, direction: f.direction }))).toEqual(
      original.map((f) => ({ name: f.name, type: f.type, direction: f.direction })),
    );
  });
});

describe("ModuleInterfacePage · deriveMockFields / displayFieldLabel", () => {
  it("derives input+output from widgets", () => {
    const fields = deriveMockFields({
      id: "m1",
      name: "Inbox",
      objectType: "WorkOrder",
      widgets: ["table", "filters", "selection"],
    });
    expect(fields.some((f) => f.name === "filterStatus" && f.direction === "input")).toBe(true);
    expect(fields.some((f) => f.name === "selectedId" && f.direction === "output")).toBe(true);
    expect(fields.some((f) => f.name === "selection" && f.direction === "output")).toBe(true);
  });

  it("labels with input./output. prefix", () => {
    expect(
      displayFieldLabel({ id: "1", name: "selection", type: "string", direction: "input" }),
    ).toBe("input.selection");
    expect(
      displayFieldLabel({ id: "2", name: "selectedId", type: "string", direction: "output" }),
    ).toBe("output.selectedId");
  });
});
