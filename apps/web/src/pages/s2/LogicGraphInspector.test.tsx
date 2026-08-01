import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import type { LogicBlockKind, LogicGraphNode } from "./logicCanvasGraph";
import {
  LogicGraphInspector,
  type LogicInspectorDirtyReason,
} from "./LogicGraphInspector";

type HarnessState = {
  node: LogicGraphNode;
  entryNodeIds: string[];
  dirtyReasons: LogicInspectorDirtyReason[];
  validationErrors: string[];
};

let latest: HarnessState;

function node(kind: LogicBlockKind, config: Record<string, unknown> = {}): LogicGraphNode {
  return {
    id: `${kind}-1`,
    kind,
    label: `${kind} label`,
    position_x: 10,
    position_y: 20,
    config,
  };
}

function Harness({
  initialNode,
  initialEntries = [],
  disabled = false,
}: {
  initialNode: LogicGraphNode;
  initialEntries?: string[];
  disabled?: boolean;
}) {
  const [selectedNode, setSelectedNode] = useState(initialNode);
  const [entryNodeIds, setEntryNodeIds] = useState(initialEntries);
  const [dirtyReasons, setDirtyReasons] = useState<LogicInspectorDirtyReason[]>([]);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  latest = { node: selectedNode, entryNodeIds, dirtyReasons, validationErrors };
  return (
    <LogicGraphInspector
      selectedNode={selectedNode}
      entryNodeIds={entryNodeIds}
      disabled={disabled}
      onNodeChange={setSelectedNode}
      onEntryNodeIdsChange={setEntryNodeIds}
      onDirty={(reason) => setDirtyReasons((previous) => [...previous, reason])}
      onValidationError={(message) => setValidationErrors((previous) => [...previous, message])}
    />
  );
}

function button(host: HTMLElement, label: string): HTMLButtonElement {
  const found = host.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`);
  if (!found) throw new Error(`missing button: ${label}`);
  return found;
}

function field(host: HTMLElement, label: string): HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement {
  const found = host.querySelector<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(`[aria-label="${label}"]`);
  if (!found) throw new Error(`missing field: ${label}`);
  return found;
}

async function enter(host: HTMLElement, label: string, value: string): Promise<void> {
  const control = field(host, label);
  await act(async () => {
    const descriptor = Object.getOwnPropertyDescriptor(
      control instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : control instanceof HTMLSelectElement
          ? HTMLSelectElement.prototype
          : HTMLInputElement.prototype,
      "value",
    );
    descriptor?.set?.call(control, value);
    control.dispatchEvent(new Event(control instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }));
  });
}

describe("LogicGraphInspector", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
  });

  it("shows an honest empty state without emitting changes", async () => {
    await act(async () => root.render(
      <LogicGraphInspector
        selectedNode={null}
        entryNodeIds={[]}
        onNodeChange={() => { throw new Error("unexpected node change"); }}
        onEntryNodeIdsChange={() => { throw new Error("unexpected entry change"); }}
        onDirty={() => { throw new Error("unexpected dirty"); }}
      />,
    ));
    expect(host.textContent).toContain("选择一个 Block");
  });

  it("edits the top-level label without writing config.label", async () => {
    await act(async () => root.render(<Harness initialNode={node("use_llm", { prompt: "old" })} />));
    await enter(host, "Block 标签", "Risk analysis");
    await act(async () => button(host, "应用标签").click());

    expect(latest.node.label).toBe("Risk analysis");
    expect(latest.node.config).toEqual({ prompt: "old" });
    expect(latest.dirtyReasons).toContain("node_label");
  });

  it("sets and cancels the selected node as an entry", async () => {
    const selected = node("input", { schema: {} });
    await act(async () => root.render(<Harness initialNode={selected} />));
    const toggle = field(host, "设为入口节点") as HTMLInputElement;
    await act(async () => toggle.click());
    expect(latest.entryNodeIds).toEqual([selected.id]);
    expect(latest.dirtyReasons).toContain("entry_change");

    await act(async () => (field(host, "设为入口节点") as HTMLInputElement).click());
    expect(latest.entryNodeIds).toEqual([]);
  });

  it.each([
    ["create_variable", "变量名", "name", "risk_score"],
    ["create_variable", "变量表达式", "expression", "risk * 2"],
    ["get_property", "Property", "property", "status"],
    ["use_llm", "Prompt", "prompt", "Assess this order"],
    ["use_llm", "Model", "model", "gpt-5"],
    ["use_tool", "Tool", "tool", "lookup_order"],
    ["transform", "Expression", "expression", "row.total"],
    ["apply_action", "Action", "action", "Order.flag"],
    ["execute", "Target", "target", "draft_inbox"],
  ] as const)("edits %s config field %s", async (kind, label, key, value) => {
    await act(async () => root.render(<Harness initialNode={node(kind)} />));
    await enter(host, label, value);
    await act(async () => button(host, `应用${label}`).click());

    expect(latest.node.config[key]).toBe(value);
    expect(latest.dirtyReasons).toContain("node_config");
  });

  it("rejects malformed or non-object input schema and commits valid JSON only", async () => {
    await act(async () => root.render(<Harness initialNode={node("input", { schema: { type: "object" } })} />));
    await enter(host, "Input Schema JSON", "{");
    await act(async () => button(host, "应用 Input Schema").click());
    expect(host.querySelector('[role="alert"]')?.textContent).toContain("JSON");
    expect(latest.node.config.schema).toEqual({ type: "object" });
    expect(latest.dirtyReasons).toEqual([]);

    await enter(host, "Input Schema JSON", "[]");
    await act(async () => button(host, "应用 Input Schema").click());
    expect(host.querySelector('[role="alert"]')?.textContent).toContain("对象");
    expect(latest.node.config.schema).toEqual({ type: "object" });

    await enter(host, "Input Schema JSON", '{"type":"object","required":["id"]}');
    await act(async () => button(host, "应用 Input Schema").click());
    expect(latest.node.config.schema).toEqual({ type: "object", required: ["id"] });
    expect(latest.dirtyReasons).toEqual(["node_config"]);
  });

  it("strictly rejects duplicate/default/unknown branch paths before committing", async () => {
    const paths = [
      { id: "high", label: "High", condition: "risk > 80", default: false },
      { id: "default", label: "Default", condition: "true", default: true },
    ];
    await act(async () => root.render(<Harness initialNode={node("branch", { paths })} />));
    await enter(host, "Branch Paths JSON", JSON.stringify([
      { id: "same", label: "A", condition: "a", default: true },
      { id: "same", label: "B", condition: "b", default: true, unexpected: 1 },
    ]));
    await act(async () => button(host, "应用 Branch Paths").click());
    expect(host.querySelector('[role="alert"]')?.textContent).toMatch(/重复|default|未知字段/);
    expect(latest.node.config.paths).toEqual(paths);
    expect(latest.dirtyReasons).toEqual([]);

    const valid = [
      { id: "approved", label: "Approved", condition: "score >= 80", default: false },
      { id: "fallback", label: "Fallback", condition: "true", default: true },
    ];
    await enter(host, "Branch Paths JSON", JSON.stringify(valid));
    await act(async () => button(host, "应用 Branch Paths").click());
    expect(latest.node.config.paths).toEqual(valid);
    expect(latest.dirtyReasons).toEqual(["node_config"]);
  });

  it("edits handoff decision and only allows known handoff targets", async () => {
    await act(async () => root.render(<Harness initialNode={node("handoff", {
      decision: "old",
      handoff_to: "draft_inbox",
    })} />));
    await enter(host, "Decision", "manual review required");
    await act(async () => button(host, "应用Decision").click());
    expect(latest.node.config.decision).toBe("manual review required");

    await enter(host, "Handoff To", "webhook");
    expect(latest.node.config.handoff_to).toBe("webhook");
    expect(latest.dirtyReasons).toEqual(["node_config", "node_config"]);
  });

  it("applies and explicitly removes optional get_property source without treating blank as required", async () => {
    await act(async () => root.render(<Harness initialNode={node("get_property", {
      property: "status",
      source: "upstream",
    })} />));

    expect(field(host, "Source")).toHaveProperty("value", "upstream");
    await act(async () => button(host, "应用Source").click());
    expect(latest.node.config.source).toBe("upstream");
    expect(latest.dirtyReasons).toEqual([]);

    await enter(host, "Source", "  input  ");
    expect(latest.node.config.source).toBe("upstream");
    expect(latest.dirtyReasons).toEqual([]);
    await act(async () => button(host, "应用Source").click());
    expect(latest.node.config.source).toBe("input");
    expect(latest.dirtyReasons).toEqual(["node_config"]);

    await enter(host, "Source", "   ");
    await act(async () => button(host, "应用Source").click());
    expect(latest.node.config).not.toHaveProperty("source");
    expect(latest.dirtyReasons).toEqual(["node_config", "node_config"]);
    expect(latest.validationErrors).toEqual([]);
  });

  it.each([
    ["use_tool", "Tool Arguments JSON", "应用 Tool Arguments", "arguments", { previous: true }, { limit: 10 }],
    ["execute", "Execute Request JSON", "应用 Execute Request", "request", { previous: true }, { object_id: "wo-1" }],
  ] as const)("keeps %s JSON as a draft, rejects non-objects, and applies objects explicitly", async (
    kind,
    label,
    applyLabel,
    key,
    initialValue,
    validValue,
  ) => {
    await act(async () => root.render(<Harness initialNode={node(kind, { [key]: initialValue })} />));

    await enter(host, label, "[]");
    await act(async () => button(host, applyLabel).click());
    expect(host.querySelector('[role="alert"]')?.textContent).toContain("JSON 对象");
    expect(latest.node.config[key]).toEqual(initialValue);
    expect(latest.dirtyReasons).toEqual([]);

    await enter(host, label, JSON.stringify(validValue));
    expect(latest.node.config[key]).toEqual(initialValue);
    await act(async () => button(host, applyLabel).click());
    expect(latest.node.config[key]).toEqual(validValue);
    expect(latest.dirtyReasons).toEqual(["node_config"]);
  });

  it("strictly rejects invalid action edits without mutating the node, then applies a normalized non-empty array", async () => {
    const original = [{ object_id: "wo-old", field: "status", value: "open" }];
    await act(async () => root.render(<Harness initialNode={node("apply_action", {
      action: "WorkOrder.update",
      edits: original,
    })} />));

    const invalidDrafts = [
      "[]",
      JSON.stringify({ object_id: "wo-1", field: "status", value: "closed" }),
      JSON.stringify([{ object_id: 1, field: "status", value: "closed" }]),
      JSON.stringify([{ object_id: "wo-1", field: " ", value: "closed" }]),
      JSON.stringify([{ object_id: "wo-1", field: "status" }]),
      JSON.stringify([{ object_id: "wo-1", field: "status", value: "closed", unexpected: true }]),
    ];
    for (const draft of invalidDrafts) {
      await enter(host, "Action Edits JSON", draft);
      await act(async () => button(host, "应用 Action Edits").click());
      expect(latest.node.config.edits).toEqual(original);
      expect(latest.dirtyReasons).toEqual([]);
    }
    expect(latest.validationErrors.some((message) => message.includes("非空 JSON 数组"))).toBe(true);
    expect(latest.validationErrors.some((message) => message.includes("必须是字符串"))).toBe(true);
    expect(latest.validationErrors.some((message) => message.includes("不能为空"))).toBe(true);
    expect(latest.validationErrors.some((message) => message.includes("必须包含 value"))).toBe(true);
    expect(latest.validationErrors.some((message) => message.includes("未知字段"))).toBe(true);

    await enter(host, "Action Edits JSON", JSON.stringify([
      { object_id: "  wo-1 ", field: " priority ", value: null },
    ]));
    await act(async () => button(host, "应用 Action Edits").click());
    expect(latest.node.config.edits).toEqual([
      { object_id: "wo-1", field: "priority", value: null },
    ]);
    expect(latest.dirtyReasons).toEqual(["node_config"]);
  });

  it.each([
    ["get_property", "Source", "应用Source"],
    ["use_tool", "Tool Arguments JSON", "应用 Tool Arguments"],
    ["apply_action", "Action Edits JSON", "应用 Action Edits"],
    ["execute", "Execute Request JSON", "应用 Execute Request"],
  ] as const)("disables the new %s editor and its explicit apply action", async (kind, label, applyLabel) => {
    await act(async () => root.render(<Harness initialNode={node(kind)} disabled />));
    expect(field(host, label).disabled).toBe(true);
    expect(button(host, applyLabel).disabled).toBe(true);
  });
});
