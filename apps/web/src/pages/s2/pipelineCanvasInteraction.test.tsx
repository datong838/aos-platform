import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
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
    data: { items: [
      { id: "pipe-align-04", sourceId: "src-align-04", datasetRid: "ri.dataset.align" },
      { id: "pipe-second", sourceId: "src-second", datasetRid: "ri.dataset.second" },
    ] },
    err: null,
    reload: mocks.reload,
  }),
}));

import { PipelineCanvasPage, moveCanvasPosition } from "./pipelineCanvas";

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

const secondGraph = {
  ...graph,
  pipeline_id: "pipe-second",
  nodes: graph.nodes.map((node) => ({ ...node, id: `${node.id}-second`, name: `${node.name}-second` })),
  edges: [
    { id: "edge-1-second", source_node_id: "source-1-second", target_node_id: "transform-1-second" },
    { id: "edge-2-second", source_node_id: "transform-1-second", target_node_id: "output-1-second" },
  ],
};

function TestRoutes() {
  const navigate = useNavigate();
  return (
    <>
      <button type="button" data-testid="to-first" onClick={() => navigate("/data/pipelines/pipe-align-04")}>first</button>
      <button type="button" data-testid="to-second" onClick={() => navigate("/data/pipelines/pipe-second")}>second</button>
      <Routes>
        <Route path="/data/pipelines/:pipelineId" element={<PipelineCanvasPage />} />
      </Routes>
    </>
  );
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

describe("PipelineCanvasPage real interactions", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(async () => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    mocks.apiGet.mockReset().mockImplementation(async (path: string) =>
      path.includes("pipe-second") ? secondGraph : graph,
    );
    mocks.apiPut.mockReset().mockImplementation(async (path: string, body: Record<string, unknown>) =>
      path.endsWith("/graph")
        ? {
            ...body,
            pipeline_id: path.includes("pipe-second") ? "pipe-second" : "pipe-align-04",
            persisted: true,
            demo: false,
          }
        : { demo: false },
    );
    mocks.apiPost.mockReset().mockResolvedValue({ columns: [], rows: [], total: 0 });
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    await act(async () => {
      root.render(
        <MemoryRouter initialEntries={["/data/pipelines/pipe-align-04"]}>
          <TestRoutes />
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

    const source = [...host.querySelectorAll<HTMLButtonElement>("button")].find((button) =>
      button.textContent?.includes("src-align-04"),
    )!;
    await act(async () => source.click());
    expect(host.querySelector(".bp-pipe-canvas-shell")?.classList.contains("is-inspector-collapsed")).toBe(false);
  });

  it("keeps later edits dirty when an older save response completes", async () => {
    const pending = deferred<Record<string, unknown>>();
    let requestBody: Record<string, unknown> | undefined;
    mocks.apiPut.mockImplementation(async (_path: string, body: Record<string, unknown>) => {
      requestBody = body;
      return pending.promise;
    });
    const incremental = [...host.querySelectorAll<HTMLButtonElement>("button")].find((button) => button.textContent === "增量")!;
    await act(async () => incremental.click());
    const save = [...host.querySelectorAll<HTMLButtonElement>("button")].find((button) => button.textContent === "保存 *")!;
    await act(async () => save.click());
    const jdbc = [...host.querySelectorAll<HTMLButtonElement>("button")].find((button) => button.textContent === "JDBC 源")!;
    await act(async () => jdbc.click());
    await act(async () => pending.resolve({
      ...requestBody,
      pipeline_id: "pipe-align-04",
      persisted: true,
      demo: false,
    }));

    expect(host.textContent).toContain("此前版本已保存，仍有未保存更改");
    expect([...host.querySelectorAll("button")].some((button) => button.textContent === "保存 *")).toBe(true);
  });

  it("rejects mismatched save responses and keeps dirty", async () => {
    mocks.apiPut.mockImplementation(async (_path: string, body: Record<string, unknown>) => ({
      ...body,
      pipeline_id: "wrong-pipeline",
      persisted: true,
      demo: false,
    }));
    const incremental = [...host.querySelectorAll<HTMLButtonElement>("button")].find((button) => button.textContent === "增量")!;
    await act(async () => incremental.click());
    const save = [...host.querySelectorAll<HTMLButtonElement>("button")].find((button) => button.textContent === "保存 *")!;
    await act(async () => save.click());

    expect(host.textContent).toContain("保存失败 · 保存响应管道不匹配");
    expect([...host.querySelectorAll("button")].some((button) => button.textContent === "保存 *")).toBe(true);
  });

  it("keeps dirty when the save request fails", async () => {
    mocks.apiPut.mockRejectedValue(new Error("database unavailable"));
    const incremental = [...host.querySelectorAll<HTMLButtonElement>("button")].find((button) => button.textContent === "增量")!;
    await act(async () => incremental.click());
    const save = [...host.querySelectorAll<HTMLButtonElement>("button")].find((button) => button.textContent === "保存 *")!;
    await act(async () => save.click());

    expect(host.textContent).toContain("保存失败 · database unavailable");
    expect([...host.querySelectorAll("button")].some((button) => button.textContent === "保存 *")).toBe(true);
  });

  it("clears the prior graph on pipeline switch and ignores a late GET", async () => {
    const lateSecond = deferred<typeof secondGraph>();
    mocks.apiGet.mockImplementation(async (path: string) => {
      if (path.includes("pipe-second")) return lateSecond.promise;
      return graph;
    });
    const toSecond = host.querySelector<HTMLButtonElement>('[data-testid="to-second"]')!;
    await act(async () => toSecond.click());
    const saveWhileLoading = [...host.querySelectorAll<HTMLButtonElement>("button")].find((button) =>
      button.textContent === "保存",
    )!;
    expect(saveWhileLoading.disabled).toBe(true);

    const toFirst = host.querySelector<HTMLButtonElement>('[data-testid="to-first"]')!;
    await act(async () => toFirst.click());
    await act(async () => lateSecond.resolve(secondGraph));
    expect(host.textContent).toContain("src-align-04");
    expect(host.textContent).not.toContain("src-second");
    expect([...host.querySelectorAll<HTMLButtonElement>("button")].find((button) => button.textContent === "保存")?.disabled).toBe(false);
  });

  it("hydrates the committed graph after a component reload", async () => {
    let stored = graph;
    mocks.apiGet.mockImplementation(async () => stored);
    mocks.apiPut.mockImplementation(async (_path: string, body: Record<string, unknown>) => {
      stored = {
        ...graph,
        ...body,
        pipeline_id: "pipe-align-04",
        persisted: true,
        demo: false,
      } as typeof graph;
      return stored;
    });
    const incremental = [...host.querySelectorAll<HTMLButtonElement>("button")].find((button) => button.textContent === "增量")!;
    await act(async () => incremental.click());
    const save = [...host.querySelectorAll<HTMLButtonElement>("button")].find((button) => button.textContent === "保存 *")!;
    await act(async () => save.click());

    await act(async () => root.unmount());
    root = createRoot(host);
    await act(async () => {
      root.render(
        <MemoryRouter initialEntries={["/data/pipelines/pipe-align-04"]}>
          <TestRoutes />
        </MemoryRouter>,
      );
    });
    const incrementalAfterReload = [...host.querySelectorAll<HTMLButtonElement>("button")].find((button) => button.textContent === "增量")!;
    expect(incrementalAfterReload.getAttribute("aria-checked")).toBe("true");
    expect([...host.querySelectorAll("button")].some((button) => button.textContent === "保存 *")).toBe(false);
  });

  it("applies DnD handler deltas with zoom normalization and canvas bounds", () => {
    expect(moveCanvasPosition({ x: 60, y: 40 }, { x: 50, y: 20 }, 2)).toEqual({ x: 85, y: 50 });
    expect(moveCanvasPosition({ x: 10, y: 10 }, { x: -100, y: -100 }, 1)).toEqual({ x: 0, y: 0 });
  });
});
