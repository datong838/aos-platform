import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPut: vi.fn(),
  apiPost: vi.fn(),
  reload: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  apiGet: mocks.apiGet,
  apiPut: mocks.apiPut,
  apiPost: mocks.apiPost,
}));

vi.mock("./shared", () => ({
  S2Chrome: ({ children }: { children: React.ReactNode }) => <main>{children}</main>,
  useJsonGet: () => ({
    data: { items: [{ id: "pipe-align-04", sourceId: "src-align-04", datasetRid: "ri.dataset.align" }] },
    err: null,
    reload: mocks.reload,
  }),
}));

import { PipelineCanvasPage } from "./pipelineCanvas";

const graph = {
  pipeline_id: "pipe-align-04",
  nodes: [
    { id: "source-1", name: "source", node_type: "source", position_x: 60, position_y: 60, config: {} },
    { id: "transform-1", name: "Ingest", node_type: "transform", position_x: 300, position_y: 60, config: { expression: "row", filter: "" } },
    { id: "output-1", name: "output", node_type: "sink", position_x: 540, position_y: 60, config: {} },
  ],
  edges: [
    { id: "edge-1", source_node_id: "source-1", target_node_id: "transform-1" },
    { id: "edge-2", source_node_id: "transform-1", target_node_id: "output-1" },
  ],
  pipeline_type: "Batch",
  write_mode: "SNAPSHOT",
  persisted: true,
  demo: false,
};

describe("PipelineCanvasPage real interactions", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(async () => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    mocks.apiGet.mockReset().mockResolvedValue(graph);
    mocks.apiPut.mockReset().mockImplementation(async (path: string) => path.endsWith("/graph") ? graph : { demo: false });
    mocks.apiPost.mockReset().mockResolvedValue({ columns: [], rows: [], total: 0 });
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    await act(async () => {
      root.render(
        <MemoryRouter initialEntries={["/data/pipelines/pipe-align-04"]}>
          <Routes>
            <Route path="/data/pipelines/:pipelineId" element={<PipelineCanvasPage />} />
          </Routes>
        </MemoryRouter>,
      );
    });
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
  });

  it("binds palette and canvas nodes to the drag controller and supports click-to-add", async () => {
    const jdbc = [...host.querySelectorAll("button")].find((button) => button.textContent === "JDBC 源");
    const source = [...host.querySelectorAll("button")].find((button) => button.textContent?.includes("src-align-04"));
    expect(jdbc?.getAttribute("aria-describedby")).toBeTruthy();
    expect(source?.getAttribute("aria-describedby")).toBeTruthy();
    await act(async () => jdbc?.click());
    expect(host.textContent).toContain("双击移除");
    expect([...host.querySelectorAll("button")].some((button) => button.textContent === "保存 *")).toBe(true);
  });

  it("marks edits dirty and persists the complete graph", async () => {
    const incremental = [...host.querySelectorAll("button")].find((button) => button.textContent === "增量")!;
    await act(async () => incremental.click());
    const save = [...host.querySelectorAll("button")].find((button) => button.textContent === "保存 *")!;
    expect(save).toBeTruthy();
    await act(async () => save.click());
    expect(mocks.apiPut).toHaveBeenCalledWith(
      "/v1/pipelines/pipe-align-04/graph",
      expect.objectContaining({
        pipeline_type: "ETL",
        write_mode: "SNAPSHOT",
        nodes: expect.arrayContaining([expect.objectContaining({ id: "source-1" })]),
        edges: expect.arrayContaining([expect.objectContaining({ id: "edge-1" })]),
      }),
    );
    expect(host.textContent).toContain("已保存 · 3 个节点 · 2 条连接");
  });

  it("collapses the inspector without taking canvas width", async () => {
    const collapse = host.querySelector<HTMLButtonElement>('[aria-label="折叠属性面板"]')!;
    await act(async () => collapse.click());
    expect(host.querySelector(".bp-pipe-canvas-shell")?.classList.contains("is-inspector-collapsed")).toBe(true);
    expect(host.querySelector('[aria-label="展开属性面板"]')).toBeTruthy();
  });
});
