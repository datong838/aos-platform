import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DecisionLineagePage } from "./aip";

const evidenceMocks = vi.hoisted(() => ({ lineage: vi.fn() }));
vi.mock("../../api/aipEvidence", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/aipEvidence")>();
  return { ...original, aipEvidenceSdk: { lineage: evidenceMocks.lineage } };
});

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("DecisionLineagePage authority interaction", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    evidenceMocks.lineage.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("初始状态不展示固定 Trace 或六段示例", async () => {
    await act(async () => root.render(<MemoryRouter><DecisionLineagePage /></MemoryRouter>));
    expect(host.textContent).toContain("不会展示示例 Trace 或固定步骤");
    expect(host.textContent).not.toContain("tr-8f3a2c91");
    expect(host.textContent).not.toContain("维修派单 Buddy");
    expect(evidenceMocks.lineage).not.toHaveBeenCalled();
  });

  it("真实空列表显示空态且不回填默认步骤", async () => {
    evidenceMocks.lineage.mockResolvedValue([]);
    await act(async () => root.render(<MemoryRouter><DecisionLineagePage /></MemoryRouter>));
    const input = host.querySelector<HTMLInputElement>("[aria-label='lineage-root-id']")!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, "run-1");
    await act(async () => input.dispatchEvent(new Event("input", { bubbles: true })));
    const query = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "查询权威谱系")!;
    await act(async () => query.click());
    await flush();
    expect(evidenceMocks.lineage).toHaveBeenCalledWith("task_run", "run-1");
    expect(host.querySelector("[data-testid='lineage-empty']")).not.toBeNull();
    expect(host.querySelector("[data-testid='lineage-authority-timeline']")).toBeNull();
    expect(host.querySelector("[data-testid='lineage-observability-blocked']")).not.toBeNull();
    expect(host.querySelector("[data-testid='lineage-jump-observability']")).toBeNull();
  });

  it("权威事件按服务端序列展示 source 与质量", async () => {
    evidenceMocks.lineage.mockResolvedValue([{
      eventId: "evt-1", lineageId: "lin-1", rootType: "task_run", rootId: "run-1",
      sequence: 1, eventType: "input", payloadHash: "a".repeat(64), quality: "measured",
      occurredAt: "2026-08-12T01:00:00Z", observedAt: "2026-08-12T01:00:01Z",
      sourceKind: "task_run", sourceId: "run-1", sourceHash: "b".repeat(64), subject: null, artifact: null,
    }]);
    await act(async () => root.render(<MemoryRouter><DecisionLineagePage /></MemoryRouter>));
    const input = host.querySelector<HTMLInputElement>("[aria-label='lineage-root-id']")!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, "run-1");
    await act(async () => input.dispatchEvent(new Event("input", { bubbles: true })));
    const query = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "查询权威谱系")!;
    await act(async () => query.click());
    await flush();
    expect(host.textContent).toContain("lin-1");
    expect(host.textContent).toContain("#1 input");
    expect(host.textContent).toContain("task_run · run-1");
    expect(host.textContent).toContain("measured");
    expect(host.querySelector<HTMLAnchorElement>("[data-testid='lineage-jump-observability']")?.getAttribute("href"))
      .toBe("/aip/observability?lineageId=lin-1&rootType=task_run&rootId=run-1");
  });
});
