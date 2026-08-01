import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { LogicGraphSnapshot } from "./logicCanvasGraph";
import { LogicCanvasPage } from "./LogicCanvasPage";

const graphApi = vi.hoisted(() => ({
  getLogicGraph: vi.fn(),
  createLogicGraph: vi.fn(),
  replaceLogicGraph: vi.fn(),
}));

vi.mock("./logicGraphApi", () => graphApi);

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((ok, fail) => {
    resolve = ok;
    reject = fail;
  });
  return { promise, resolve, reject };
}

function graphSnapshot(id: string, revision = 1, label = `${id} 输入`): LogicGraphSnapshot {
  return {
    id,
    name: `Logic ${id}`,
    description: "",
    status: "draft",
    schema_version: 1,
    revision,
    published_version: null,
    graph_hash: `hash-${id}-${revision}`,
    persisted: true,
    nodes: [
      { id: `${id}-input`, kind: "input", label, position_x: 80, position_y: 120, config: {} },
      { id: `${id}-llm`, kind: "use_llm", label: `${id} LLM`, position_x: 340, position_y: 120, config: { prompt: "分析" } },
    ],
    edges: [{
      id: `${id}-edge`,
      source_node_id: `${id}-input`,
      source_port: "out",
      target_node_id: `${id}-llm`,
      target_port: "in",
      branch_path: "",
      order: 0,
    }],
    entry_node_ids: [`${id}-input`],
  };
}

let currentPath = "";
function LocationProbe() {
  currentPath = useLocation().pathname;
  return null;
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("AIP Logic Stage A2 · canonical graph 页面集成", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    currentPath = "";
    Object.values(graphApi).forEach((mock) => mock.mockReset());
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  async function renderPage(flowId?: string) {
    await act(async () => root.render(
      <MemoryRouter initialEntries={[flowId ? `/aip/logic/${flowId}` : "/aip/logic"]}>
        <LogicCanvasPage flowId={flowId} />
        <LocationProbe />
      </MemoryRouter>,
    ));
    await flush();
  }

  function button(label: string): HTMLButtonElement {
    const found = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((item) =>
      item.textContent?.includes(label) || item.getAttribute("aria-label")?.includes(label),
    );
    if (!found) throw new Error(`button not found: ${label}`);
    return found;
  }

  function setNativeInput(input: HTMLInputElement, value: string) {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  it("无 flowId 显示带 4 节点 3 连接的明确未保存模板，显式 POST 后 replace 导航", async () => {
    await renderPage();
    expect(host.textContent).toContain("未保存模板");
    expect(host.textContent).toContain("节点 4 · 连接 3");
    expect(host.textContent).toContain("未保存更改");

    graphApi.createLogicGraph.mockImplementation(async (draft) => ({
      ...draft,
      revision: 1,
      published_version: null,
      graph_hash: "hash-created",
      persisted: true,
    }));
    await act(async () => button("保存").click());
    await flush();

    expect(graphApi.createLogicGraph).toHaveBeenCalledTimes(1);
    expect(graphApi.createLogicGraph.mock.calls[0][0]).toMatchObject({
      nodes: expect.arrayContaining([expect.objectContaining({ kind: "input", position_x: expect.any(Number) })]),
      edges: expect.arrayContaining([expect.objectContaining({ source_port: "out", target_port: "in" })]),
    });
    const createdId = graphApi.createLogicGraph.mock.calls[0][0].id;
    expect(currentPath).toBe(`/aip/logic/${createdId}`);
    expect(host.textContent).toContain("已保存并回读确认");
  });

  it("flowId 切换立即隔离旧图，迟到的旧 GET 不得覆盖新图", async () => {
    const oldRequest = deferred<LogicGraphSnapshot>();
    const newRequest = deferred<LogicGraphSnapshot>();
    graphApi.getLogicGraph.mockImplementation((id: string) => id === "old" ? oldRequest.promise : newRequest.promise);

    await act(async () => root.render(
      <MemoryRouter><LogicCanvasPage flowId="old" /></MemoryRouter>,
    ));
    expect(host.textContent).not.toContain("old 输入");
    await act(async () => root.render(
      <MemoryRouter><LogicCanvasPage flowId="new" /></MemoryRouter>,
    ));

    newRequest.resolve(graphSnapshot("new"));
    await flush();
    expect(host.textContent).toContain("new 输入");

    oldRequest.resolve(graphSnapshot("old"));
    await flush();
    expect(host.textContent).toContain("new 输入");
    expect(host.textContent).not.toContain("old 输入");
  });

  it("节点属性、添加和删边均标 dirty，PUT 使用加载 revision，成功后才清 dirty", async () => {
    graphApi.getLogicGraph.mockResolvedValue(graphSnapshot("saved", 4));
    graphApi.replaceLogicGraph.mockImplementation(async (draft) => ({
      ...draft,
      revision: 5,
      published_version: null,
      graph_hash: "hash-saved-5",
      persisted: true,
    }));
    await renderPage("saved");
    expect(host.textContent).not.toContain("未保存更改");

    await act(async () => button("从 saved-input 的 out 端口建立连接").click());
    await act(async () => button("连接到 saved-llm 的 in 端口").click());
    expect(host.textContent).toContain("重复连接");
    await act(async () => button("添加 分支").click());
    expect(host.textContent).not.toContain("重复连接");

    await act(async () => button("拖动 saved-input").click());
    const labelInput = host.querySelector<HTMLInputElement>('input[aria-label="Block 标签"]')!;
    await act(async () => setNativeInput(labelInput, "已编辑输入"));
    await act(async () => button("应用标签").click());
    expect(host.textContent).toContain("未保存更改");
    expect(host.textContent).toContain("已编辑输入");

    await act(async () => button("删除连接 saved-edge").click());
    await act(async () => button("保存").click());
    await flush();

    expect(graphApi.replaceLogicGraph).toHaveBeenCalledWith(expect.objectContaining({
      id: "saved",
      nodes: expect.arrayContaining([expect.objectContaining({ label: "已编辑输入" }), expect.objectContaining({ kind: "branch" })]),
      edges: [],
    }), 4);
    expect(host.textContent).not.toContain("未保存更改");
    expect(host.textContent).toContain("revision 5");
  });

  it("删除入口节点同步清理 entry_node_ids，保存草稿不产生悬空入口", async () => {
    graphApi.getLogicGraph.mockResolvedValue(graphSnapshot("entry", 3));
    graphApi.replaceLogicGraph.mockImplementation(async (draft) => ({
      ...draft,
      revision: 4,
      published_version: null,
      graph_hash: "hash-entry-4",
      persisted: true,
    }));
    await renderPage("entry");

    await act(async () => button("删除节点 entry-input").click());
    await act(async () => button("保存").click());
    await flush();

    expect(graphApi.replaceLogicGraph).toHaveBeenCalledWith(expect.objectContaining({
      nodes: [expect.objectContaining({ id: "entry-llm" })],
      edges: [],
      entry_node_ids: [],
    }), 3);
  });

  it("409 或保存后回读失败可见且保留 dirty 草稿", async () => {
    graphApi.getLogicGraph.mockResolvedValue(graphSnapshot("conflict", 2));
    graphApi.replaceLogicGraph.mockRejectedValue(Object.assign(new Error("版本冲突，请刷新"), { status: 409 }));
    await renderPage("conflict");
    await act(async () => button("添加 汇聚").click());
    await act(async () => button("保存").click());
    await flush();

    expect(host.textContent).toContain("版本冲突，请刷新");
    expect(host.textContent).toContain("未保存更改");
    expect(host.textContent).not.toContain("已保存并回读确认");
  });

  it("adapter 报告保存后严格回读不一致时不清 dirty、不显示成功", async () => {
    graphApi.getLogicGraph.mockResolvedValue(graphSnapshot("verify", 6));
    graphApi.replaceLogicGraph.mockRejectedValue(new Error("保存后重新读取的图快照不一致"));
    await renderPage("verify");
    await act(async () => button("添加 数据变换").click());
    await act(async () => button("保存").click());
    await flush();

    expect(host.textContent).toContain("保存后重新读取的图快照不一致");
    expect(host.textContent).toContain("未保存更改");
    expect(host.textContent).not.toContain("已保存并回读确认");
  });

  it("刷新成功才丢弃本地改动；GET 失败保留 dirty 和本地图", async () => {
    graphApi.getLogicGraph
      .mockResolvedValueOnce(graphSnapshot("refresh", 1, "服务端 v1"))
      .mockRejectedValueOnce(new Error("刷新读取失败"))
      .mockResolvedValueOnce(graphSnapshot("refresh", 2, "服务端 v2"));
    await renderPage("refresh");
    await act(async () => button("拖动 refresh-input").click());
    const labelInput = host.querySelector<HTMLInputElement>('input[aria-label="Block 标签"]')!;
    await act(async () => setNativeInput(labelInput, "本地草稿"));
    await act(async () => button("应用标签").click());

    await act(async () => button("刷新").click());
    await flush();
    expect(host.textContent).toContain("刷新读取失败");
    expect(host.textContent).toContain("本地草稿");
    expect(host.textContent).toContain("未保存更改");

    await act(async () => button("刷新").click());
    await flush();
    expect(host.textContent).toContain("服务端 v2");
    expect(host.textContent).not.toContain("本地草稿");
    expect(host.textContent).not.toContain("未保存更改");
  });

  it("可信 dry-run、历史和自动化在 Stage B 前保持禁用且不调用旧安全门卫", async () => {
    graphApi.getLogicGraph.mockResolvedValue(graphSnapshot("gated"));
    await renderPage("gated");

    const dryRun = button("canonical dry-run");
    expect(dryRun.disabled).toBe(true);
    expect(host.textContent).toContain("Stage B 尚未开放");
    expect(host.textContent).toContain("运行历史尚未接入 canonical API");
    expect(host.textContent).toContain("自动化尚未接入发布版本契约");
  });
});
