import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { LogicGraphSnapshot } from "./logicCanvasGraph";
import { LogicCanvasPage } from "./LogicCanvasPage";
import type { LogicDryRun, LogicRunSummary } from "./logicRunContracts";
import type { LogicPublication } from "./logicPublicationContracts";

const graphApi = vi.hoisted(() => ({
  getLogicGraph: vi.fn(),
  createLogicGraph: vi.fn(),
  replaceLogicGraph: vi.fn(),
}));

vi.mock("./logicGraphApi", () => graphApi);

const runApi = vi.hoisted(() => ({
  dryRunLogicGraph: vi.fn(),
  getLogicRun: vi.fn(),
  listLogicRuns: vi.fn(),
}));

vi.mock("./logicRunApi", () => runApi);

const publicationApi = vi.hoisted(() => ({
  getLogicPublication: vi.fn(),
  listLogicPublications: vi.fn(),
  publishLogicGraph: vi.fn(),
}));

vi.mock("./logicPublicationApi", () => publicationApi);

const clientApi = vi.hoisted(() => ({ apiGet: vi.fn() }));

vi.mock("../../api/client", () => clientApi);

const productionContracts = vi.hoisted(() => ({
  listStageTemplates: vi.fn(async () => ({ tenant: { orgId: "org-org", projectId: "dev-project" }, items: [], count: 0 })),
  listResponsibilityPlans: vi.fn(async () => ({ tenant: { orgId: "org-org", projectId: "dev-project" }, items: [], count: 0 })),
}));
vi.mock("../../api/aipProductionContracts", () => ({ aipProductionContracts: productionContracts }));

const agentControl = vi.hoisted(() => ({
  runtimeReadiness: vi.fn(async () => ({
    tenant: { orgId: "org-org", projectId: "dev-project" },
    catalog: { tenant: { orgId: "org-org", projectId: "dev-project" }, stats: { definitionCount: 6, installedCount: 1, runnableCount: 0, skillDefinitionCount: 0, capabilityDefinitionCount: 0 }, items: [] },
    capabilityBindings: [],
    skillBindings: [],
    bindingStats: { capabilityBindingCount: 0, skillBindingCount: 0, activeCapabilityBindingCount: 0, activeSkillBindingCount: 0 },
    evaluatedAt: "2026-08-20T00:00:00Z",
  })),
}));
vi.mock("../../api/aipAgentControl", () => ({ aipAgentControl: agentControl }));

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
    graph_hash: ((id.length + revision) % 16).toString(16).repeat(64),
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

function dryRunResult(graph: LogicGraphSnapshot, runId = `run-${graph.id}`, failed = false): LogicDryRun {
  const second = graph.nodes[1];
  return {
    run_id: runId,
    graph_id: graph.id,
    mode: "dry_run",
    status: failed ? "failed" : "succeeded",
    evaluated_revision: graph.revision,
    graph_hash: graph.graph_hash,
    production_written: false,
    started_at: "2026-08-02T08:00:00Z",
    finished_at: "2026-08-02T08:00:01Z",
    elapsed_ms: 1000,
    total_tokens: null,
    node_results: graph.nodes.map((node, index) => ({
      node_id: node.id,
      kind: node.kind,
      status: failed && index === 1 ? "failed" : "executed",
      started_at: "2026-08-02T08:00:00Z",
      finished_at: "2026-08-02T08:00:01Z",
      elapsed_ms: 10,
      summary: failed && index === 1 ? "安全执行失败" : "安全执行完成",
      output: { node: node.id },
      usage: null,
      tool_call: null,
      selected_branch_path: null,
      proposed_edits: [],
      error: failed && index === 1
        ? { code: "SAFE_TOOL_FAILED", message: "只读适配器失败", node_id: node.id, reason: null }
        : null,
      truncated: false,
    })),
    proposed_edits: [],
    error: failed
      ? { code: "SAFE_TOOL_FAILED", message: "只读适配器失败", node_id: second.id, reason: null }
      : null,
  };
}

function runWithNodeStates(
  graph: LogicGraphSnapshot,
  runId: string,
  statuses: LogicDryRun["node_results"][number]["status"][],
): LogicDryRun {
  const failedIndex = statuses.indexOf("failed");
  const failedNode = failedIndex >= 0 ? graph.nodes[failedIndex] : null;
  return {
    ...dryRunResult(graph, runId, failedIndex >= 0),
    status: failedNode ? "failed" : "succeeded",
    node_results: graph.nodes.map((node, index) => {
      const status = statuses[index] ?? "executed";
      const error = status === "failed"
        ? { code: "NODE_FAILED", message: "节点失败", node_id: node.id, reason: null }
        : status === "skipped" || status === "canceled"
          ? { code: `NODE_${status.toUpperCase()}`, message: `节点${status}`, node_id: node.id, reason: `${status}_reason` }
          : null;
      return {
        node_id: node.id,
        kind: node.kind,
        status,
        started_at: status === "skipped" || status === "canceled" ? null : "2026-08-02T08:00:00Z",
        finished_at: status === "skipped" || status === "canceled" ? null : "2026-08-02T08:00:01Z",
        elapsed_ms: status === "skipped" || status === "canceled" ? null : 10,
        summary: `节点状态 ${status}`,
        output: { state: status },
        usage: null,
        tool_call: null,
        selected_branch_path: null,
        proposed_edits: [],
        error,
        truncated: false,
      };
    }),
    error: failedNode
      ? { code: "NODE_FAILED", message: "节点失败", node_id: failedNode.id, reason: null }
      : null,
  };
}

function historySummary(run: LogicDryRun): LogicRunSummary {
  return {
    run_id: run.run_id,
    graph_id: run.graph_id,
    mode: "dry_run",
    status: run.status,
    evaluated_revision: run.evaluated_revision,
    graph_hash: run.graph_hash,
    production_written: false,
    started_at: run.started_at,
    finished_at: run.finished_at,
    elapsed_ms: run.elapsed_ms,
    total_tokens: run.total_tokens,
    node_counts: {
      executed: run.node_results.filter((node) => node.status === "executed").length,
      skipped: run.node_results.filter((node) => node.status === "skipped").length,
      failed: run.node_results.filter((node) => node.status === "failed").length,
      canceled: run.node_results.filter((node) => node.status === "canceled").length,
    },
    error_code: run.error?.code ?? null,
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
    Object.values(runApi).forEach((mock) => mock.mockReset());
    Object.values(publicationApi).forEach((mock) => mock.mockReset());
    clientApi.apiGet.mockReset();
    productionContracts.listStageTemplates.mockClear();
    productionContracts.listResponsibilityPlans.mockClear();
    agentControl.runtimeReadiness.mockClear();
    runApi.listLogicRuns.mockResolvedValue({ items: [], count: 0, next_cursor: null });
    publicationApi.listLogicPublications.mockResolvedValue({ items: [], count: 0 });
    clientApi.apiGet.mockResolvedValue({ items: [] });
    productionContracts.listStageTemplates.mockResolvedValue({ tenant: { orgId: "org-org", projectId: "dev-project" }, items: [], count: 0 });
    productionContracts.listResponsibilityPlans.mockResolvedValue({ tenant: { orgId: "org-org", projectId: "dev-project" }, items: [], count: 0 });
    agentControl.runtimeReadiness.mockResolvedValue({
      tenant: { orgId: "org-org", projectId: "dev-project" },
      catalog: { tenant: { orgId: "org-org", projectId: "dev-project" }, stats: { definitionCount: 6, installedCount: 1, runnableCount: 0, skillDefinitionCount: 0, capabilityDefinitionCount: 0 }, items: [] },
      capabilityBindings: [],
      skillBindings: [],
      bindingStats: { capabilityBindingCount: 0, skillBindingCount: 0, activeCapabilityBindingCount: 0, activeSkillBindingCount: 0 },
      evaluatedAt: "2026-08-20T00:00:00Z",
    });
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

  async function openHistoryTab() {
    await act(async () => button("运行历史").click());
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

  function setNativeTextarea(input: HTMLTextAreaElement, value: string) {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set?.call(input, value);
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

  it("删除唯一入口节点后选择剩余节点为入口，保存草稿不产生悬空或空入口", async () => {
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
      entry_node_ids: ["entry-llm"],
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

  it("安全试跑按钮始终可见，并按未保存、loading、dirty、saving、Inputs 与 running 严格门禁", async () => {
    await renderPage();
    expect(button("安全试跑").disabled).toBe(true);
    expect(host.textContent).toContain("请先保存 Logic Graph");

    const loadingGraph = deferred<LogicGraphSnapshot>();
    graphApi.getLogicGraph.mockReturnValueOnce(loadingGraph.promise);
    await act(async () => root.render(<MemoryRouter><LogicCanvasPage flowId="gates" /></MemoryRouter>));
    expect(button("安全试跑").disabled).toBe(true);
    expect(host.textContent).toContain("Logic Graph 正在加载");
    const cleanGraph = graphSnapshot("gates", 3);
    loadingGraph.resolve(cleanGraph);
    await flush();
    expect(button("安全试跑").disabled).toBe(true);
    expect(host.textContent).toContain("请先显式应用 Dry-Run Inputs");

    await act(async () => button("应用 Inputs").click());
    expect(button("安全试跑").disabled).toBe(false);
    expect(host.textContent).toContain("已满足可信试跑门禁");

    await act(async () => button("添加 汇聚").click());
    expect(button("安全试跑").disabled).toBe(true);
    expect(host.textContent).toContain("存在未保存更改");

    const save = deferred<LogicGraphSnapshot>();
    graphApi.replaceLogicGraph.mockReturnValueOnce(save.promise);
    await act(async () => button("保存").click());
    expect(host.textContent).toContain("请等待保存与回读完成");
    save.resolve({ ...cleanGraph, revision: 4, graph_hash: "f".repeat(64), nodes: [...cleanGraph.nodes, {
      id: "saved-handoff",
      kind: "handoff",
      label: "汇聚",
      position_x: 600,
      position_y: 180,
      config: {},
    }] });
    await flush();
    expect(button("安全试跑").disabled).toBe(false);
    await act(async () => button("拖动 saved-handoff").click());

    const runningRequest = deferred<LogicDryRun>();
    runApi.dryRunLogicGraph.mockReturnValueOnce(runningRequest.promise);
    await act(async () => {
      const dryRun = button("安全试跑");
      dryRun.click();
      dryRun.click();
    });
    expect(button("安全试跑中").disabled).toBe(true);
    expect(host.textContent).toContain("安全试跑正在运行");
    expect(button("保存").disabled).toBe(true);
    expect(button("刷新").disabled).toBe(true);
    expect(button("应用 Inputs").disabled).toBe(true);
    expect(button("添加 汇聚").disabled).toBe(true);
    expect(host.querySelector<HTMLInputElement>('input[aria-label="Logic 名称"]')?.disabled).toBe(true);
    expect(host.querySelector<HTMLInputElement>('input[aria-label="Logic 描述"]')?.disabled).toBe(true);
    expect(host.querySelector<HTMLTextAreaElement>('textarea[aria-label="Dry-Run Inputs JSON"]')?.disabled).toBe(true);
    expect(host.querySelector<HTMLInputElement>('input[aria-label="Block 标签"]')?.disabled).toBe(true);
    expect(host.textContent).not.toContain("Dry-Run Inputs 已显式应用；未写入 Logic Graph");
    expect(runApi.dryRunLogicGraph).toHaveBeenCalledTimes(1);
    runningRequest.resolve(dryRunResult({ ...cleanGraph, revision: 4, graph_hash: "f".repeat(64), nodes: [...cleanGraph.nodes, {
      id: "saved-handoff",
      kind: "handoff",
      label: "汇聚",
      position_x: 600,
      position_y: 180,
      config: {},
    }] }));
    await flush();
  });

  it("Inputs 只接受显式应用的 JSON 对象，不修改画布 dirty；成功试跑绑定 revision/hash 并回读历史", async () => {
    const loaded = graphSnapshot("trusted", 7);
    const result = dryRunResult(loaded);
    runApi.listLogicRuns
      .mockResolvedValueOnce({ items: [], count: 0, next_cursor: null })
      .mockResolvedValueOnce({ items: [historySummary(result)], count: 1, next_cursor: null });
    graphApi.getLogicGraph.mockResolvedValue(loaded);
    runApi.dryRunLogicGraph.mockResolvedValue(result);
    await renderPage("trusted");

    const editor = host.querySelector<HTMLTextAreaElement>('textarea[aria-label="Dry-Run Inputs JSON"]')!;
    await act(async () => setNativeTextarea(editor, "[]"));
    await act(async () => button("应用 Inputs").click());
    expect(host.textContent).toContain("Inputs 必须是 JSON 对象");
    expect(button("安全试跑").disabled).toBe(true);

    await act(async () => setNativeTextarea(editor, '{"objectId":"wo-7"}'));
    await act(async () => button("应用 Inputs").click());
    expect(host.textContent).not.toContain("未保存更改");
    expect(button("安全试跑").disabled).toBe(false);
    await act(async () => button("安全试跑").click());
    await flush();

    expect(runApi.dryRunLogicGraph).toHaveBeenCalledWith("trusted", {
      expected_revision: 7,
      dry_run: true,
      expected_graph_hash: loaded.graph_hash,
      inputs: { objectId: "wo-7" },
    }, ["trusted-input", "trusted-llm"]);
    await openHistoryTab();
    expect(host.textContent).toContain("服务端运行证据");
    expect(host.textContent).toContain("revision 7");
    expect(host.textContent).toContain(loaded.graph_hash);
    expect(host.textContent).toContain("不写生产");
    expect(host.textContent).toContain("run-trusted");
    expect(runApi.listLogicRuns).toHaveBeenCalledTimes(2);
    expect(host.textContent).not.toContain("Stage B 尚未开放");
  });

  it("409、普通失败与 POST 后历史回读失败均保留当前图和 clean 状态，不伪造结果", async () => {
    const loaded = graphSnapshot("failure", 5, "仍在画布");
    graphApi.getLogicGraph.mockResolvedValue(loaded);
    await renderPage("failure");
    await act(async () => button("应用 Inputs").click());

    runApi.dryRunLogicGraph.mockRejectedValueOnce(Object.assign(new Error("revision 已变化"), { status: 409 }));
    await act(async () => button("安全试跑").click());
    await flush();
    await openHistoryTab();
    expect(host.textContent).toContain("版本冲突：revision 已变化");
    await act(async () => button("编辑").click());
    await flush();
    expect(host.textContent).toContain("仍在画布");
    expect(host.textContent).not.toContain("未保存更改");

    runApi.dryRunLogicGraph.mockRejectedValueOnce(new Error("只读执行器不可用"));
    await act(async () => button("安全试跑").click());
    await flush();
    await openHistoryTab();
    expect(host.textContent).toContain("只读执行器不可用");
    await act(async () => button("编辑").click());
    await flush();
    expect(host.textContent).toContain("仍在画布");

    runApi.dryRunLogicGraph.mockRejectedValueOnce(new Error("响应已收到，但历史持久化核验失败：detail 不一致"));
    await act(async () => button("安全试跑").click());
    await flush();
    await openHistoryTab();
    expect(host.textContent).toContain("历史持久化核验失败");
    expect(host.textContent).not.toContain("服务端运行证据");
    expect(runApi.dryRunLogicGraph).toHaveBeenCalledTimes(3);
  });

  it("服务端历史支持选择详情、分页、失败重试；历史下钻和错误定位不改变 dirty", async () => {
    const loaded = graphSnapshot("history", 8);
    const failed = dryRunResult(loaded, "run-history-failed", true);
    const older = dryRunResult({ ...loaded, revision: 7 }, "run-history-older");
    runApi.listLogicRuns
      .mockRejectedValueOnce(new Error("历史暂时不可用"))
      .mockResolvedValueOnce({ items: [historySummary(failed)], count: 1, next_cursor: "cursor-1" })
      .mockResolvedValueOnce({ items: [historySummary(older)], count: 1, next_cursor: null });
    graphApi.getLogicGraph.mockResolvedValue(loaded);
    runApi.getLogicRun.mockResolvedValue(failed);
    await renderPage("history");
    await openHistoryTab();

    expect(host.textContent).toContain("历史暂时不可用");
    await act(async () => button("重试").click());
    await flush();

    await act(async () => button("run-history-failed").click());
    await flush();
    expect(runApi.getLogicRun).toHaveBeenCalledWith("history", "run-history-failed");
    expect(host.textContent).toContain("SAFE_TOOL_FAILED");
    expect(host.textContent).not.toContain("未保存更改");
    await act(async () => button("定位节点 history-llm").click());
    await act(async () => button("编辑").click());
    await flush();
    expect(host.textContent).toContain("Block 属性use_llm");
    expect(host.textContent).not.toContain("未保存更改");

    await openHistoryTab();
    await act(async () => button("加载更多运行记录").click());
    await flush();
    expect(runApi.listLogicRuns).toHaveBeenLastCalledWith("history", { limit: 20, before: "cursor-1" });
    expect(host.textContent).toContain("run-history-older");
    expect(host.textContent).not.toContain("未保存更改");
  });

  it("历史详情只读映射四种节点状态，切换历史和新 run loading 时清空，flow 切换不残留", async () => {
    const loaded = graphSnapshot("states", 9);
    loaded.nodes.push(
      { id: "states-transform", kind: "transform", label: "Transform", position_x: 600, position_y: 120, config: {} },
      { id: "states-execute", kind: "execute", label: "Execute", position_x: 860, position_y: 120, config: {} },
    );
    const mixed = runWithNodeStates(loaded, "run-states-mixed", ["executed", "skipped", "failed", "canceled"]);
    mixed.node_results.push({
      ...mixed.node_results[0],
      node_id: "historical-removed-node",
      summary: "历史中存在但当前图已删除",
    });
    const allExecuted = runWithNodeStates(loaded, "run-states-executed", ["executed", "executed", "executed", "executed"]);
    const secondDetail = deferred<LogicDryRun>();
    const nextRun = deferred<LogicDryRun>();
    graphApi.getLogicGraph
      .mockResolvedValueOnce(loaded)
      .mockResolvedValueOnce(graphSnapshot("states-next", 1));
    runApi.listLogicRuns.mockImplementation(async (graphId: string) => graphId === loaded.id
      ? { items: [historySummary(mixed), historySummary(allExecuted)], count: 2, next_cursor: null }
      : { items: [], count: 0, next_cursor: null });
    runApi.getLogicRun
      .mockResolvedValueOnce(mixed)
      .mockReturnValueOnce(secondDetail.promise);
    runApi.dryRunLogicGraph.mockReturnValueOnce(nextRun.promise);
    await renderPage("states");
    await openHistoryTab();

    await act(async () => button("run-states-mixed").click());
    await flush();
    await act(async () => button("编辑").click());
    await flush();
    const expectedStates = new Map([
      ["states-input", "executed"],
      ["states-llm", "skipped"],
      ["states-transform", "failed"],
      ["states-execute", "canceled"],
    ]);
    expectedStates.forEach((state, nodeId) => {
      expect(host.querySelector<HTMLElement>(`[data-node-id="${nodeId}"]`)?.dataset.runState).toBe(state);
    });
    expect(host.querySelector('.bp-logic-canvas-node[data-node-id="historical-removed-node"]')).toBeNull();
    expect(host.querySelectorAll("[data-run-state]")).toHaveLength(4);
    expect(host.textContent).not.toContain("未保存更改");

    await openHistoryTab();
    await act(async () => button("run-states-executed").click());
    await flush();
    await act(async () => button("编辑").click());
    await flush();
    expect(host.querySelectorAll("[data-run-state]")).toHaveLength(0);
    secondDetail.resolve(allExecuted);
    await flush();
    expect(host.querySelectorAll('[data-run-state="executed"]')).toHaveLength(4);
    expect(host.textContent).not.toContain("未保存更改");

    await act(async () => button("应用 Inputs").click());
    await act(async () => button("安全试跑").click());
    expect(host.querySelectorAll("[data-run-state]")).toHaveLength(0);
    nextRun.resolve({ ...allExecuted, run_id: "run-states-new" });
    await flush();
    expect(host.querySelectorAll('[data-run-state="executed"]')).toHaveLength(4);

    await act(async () => root.render(<MemoryRouter><LogicCanvasPage flowId="states-next" /></MemoryRouter>));
    await flush();
    expect(host.textContent).toContain("states-next 输入");
    expect(host.querySelectorAll("[data-run-state]")).toHaveLength(0);
    expect(host.textContent).not.toContain("未保存更改");
  });

  it("flowId 切换隔离迟到的运行详情与历史响应", async () => {
    const oldGraph = graphSnapshot("old-run", 2);
    const newGraph = graphSnapshot("new-run", 3);
    const oldDetail = deferred<LogicDryRun>();
    const oldHistory = historySummary(dryRunResult(oldGraph, "run-old-late"));
    graphApi.getLogicGraph.mockImplementation(async (id: string) => id === "old-run" ? oldGraph : newGraph);
    runApi.listLogicRuns.mockImplementation(async (id: string) => ({
      items: id === "old-run" ? [oldHistory] : [],
      count: id === "old-run" ? 1 : 0,
      next_cursor: null,
    }));
    runApi.getLogicRun.mockReturnValueOnce(oldDetail.promise);

    await act(async () => root.render(<MemoryRouter><LogicCanvasPage key="old-run" flowId="old-run" /></MemoryRouter>));
    await flush();
    await openHistoryTab();
    await act(async () => button("run-old-late").click());
    await act(async () => root.render(<MemoryRouter><LogicCanvasPage key="new-run" flowId="new-run" /></MemoryRouter>));
    await flush();
    oldDetail.resolve(dryRunResult(oldGraph, "run-old-late"));
    await flush();

    expect(host.textContent).toContain("new-run 输入");
    expect(host.textContent).not.toContain("run-old-late");
  });

  it("同 revision 的真实 Eval 证据通过后才发布，并以 POST、publication GET 与 Graph GET 回读确认", async () => {
    const loaded = {
      ...graphSnapshot("publishable", 3),
      created_at: "2026-08-02T08:00:00Z",
      updated_at: "2026-08-02T08:00:00Z",
    };
    const reread = { ...loaded, published_version: 3, updated_at: "2026-08-02T08:10:00Z" };
    const report = {
      report_id: "eval-report-publishable",
      suite_id: "suite-publishable",
      target_type: "logic_graph",
      target_id: loaded.id,
      target_revision: loaded.revision,
      target_hash: loaded.graph_hash,
      gate_passed: true,
      pass_rate: 1,
      passed: 1,
      failed: 0,
      total: 1,
      run_at: "2026-08-02T08:05:00Z",
    };
    const publication: LogicPublication = {
      publication_id: "logic-pub-publishable",
      graph_id: loaded.id,
      graph_revision: loaded.revision,
      graph_hash: loaded.graph_hash,
      graph_snapshot: loaded,
      dry_run_id: "run-publishable",
      eval_suite_id: report.suite_id,
      eval_report_id: report.report_id,
      eval_gate: {
        gate_passed: true,
        pass_rate: 1,
        threshold: 1,
        passed: 1,
        failed: 0,
        total: 1,
        run_at: report.run_at,
      },
      actor: "dev-user",
      created_at: "2026-08-02T08:06:00Z",
    };
    graphApi.getLogicGraph.mockResolvedValueOnce(loaded).mockResolvedValueOnce(reread);
    clientApi.apiGet.mockImplementation((path: string) => Promise.resolve(
      path === "/v1/evals/suites"
        ? { items: [{ id: report.suite_id, name: "发布门", gate_threshold: 1 }] }
        : report,
    ));
    publicationApi.publishLogicGraph.mockResolvedValue(publication);

    await renderPage(loaded.id);
    expect(button("发布当前 revision").disabled).toBe(true);
    await act(async () => button("读取当前版本 Eval 证据").click());
    await flush();
    expect(button("发布当前 revision").disabled).toBe(false);

    await act(async () => button("发布当前 revision").click());
    await flush();

    expect(publicationApi.publishLogicGraph).toHaveBeenCalledWith(loaded.id, expect.objectContaining({
      expected_revision: loaded.revision,
      expected_graph_hash: loaded.graph_hash,
      eval_suite_id: report.suite_id,
      eval_report_id: report.report_id,
      idempotency_key: expect.stringContaining("logic-publish-3-"),
    }));
    expect(graphApi.getLogicGraph).toHaveBeenCalledTimes(2);
    expect(host.textContent).toContain("已发布并回读确认");
    expect(host.textContent).toContain(publication.publication_id);
    expect(button("绑定自动化（禁用）").disabled).toBe(true);
  });
});
