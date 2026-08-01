import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  LogicRunPanel,
  type LogicRunNodeView,
  type LogicRunPanelProps,
  type LogicRunSummaryView,
  type LogicRunView,
} from "./LogicRunPanel";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const HASH = "a".repeat(64);

function nodeView(overrides: Partial<LogicRunNodeView> = {}): LogicRunNodeView {
  return {
    node_id: "input-1",
    kind: "input",
    status: "executed",
    started_at: "2026-08-01T08:00:00Z",
    finished_at: "2026-08-01T08:00:00.003Z",
    elapsed_ms: 3,
    summary: "输入校验通过",
    output: { accepted: true },
    usage: null,
    tool_call: null,
    selected_branch_path: null,
    proposed_edits: [],
    error: null,
    truncated: false,
    ...overrides,
  };
}

function runView(overrides: Partial<LogicRunView> = {}): LogicRunView {
  return {
    run_id: "run-001",
    graph_id: "logic-001",
    mode: "dry_run",
    status: "failed",
    evaluated_revision: 7,
    graph_hash: HASH,
    production_written: false,
    started_at: "2026-08-01T08:00:00Z",
    finished_at: "2026-08-01T08:00:01Z",
    elapsed_ms: 812,
    total_tokens: null,
    proposed_edits: [{
      action: "WorkOrder.updateNote",
      object_id: "wo-1",
      field: "note",
      value: "建议人工复核",
      source_node_id: "tool-1",
      applied: false,
    }],
    error: { code: "TOOL_UNAVAILABLE", message: "安全工具适配器不可用", node_id: "tool-1", reason: null },
    node_results: [
      nodeView(),
      nodeView({
        node_id: "branch-1",
        kind: "branch",
        summary: "选择高风险路径",
        elapsed_ms: 4,
        selected_branch_path: "high-risk",
        output: { selected: "high-risk" },
      }),
      nodeView({
        node_id: "low-1",
        kind: "transform",
        status: "skipped",
        summary: "分支未选中",
        started_at: null,
        finished_at: null,
        elapsed_ms: null,
        error: { code: "NODE_SKIPPED", message: "分支未选中", node_id: "low-1", reason: "branch_not_selected" },
      }),
      nodeView({
        node_id: "tool-1",
        kind: "use_tool",
        status: "failed",
        summary: "工具调用失败",
        elapsed_ms: 16,
        truncated: true,
        output: { records: ["wo-1"], safe: true },
        tool_call: { tool: "work-order-reader", adapter: "readonly-v1", read_only: true, dry_run_safe: true },
        proposed_edits: [{
          action: "WorkOrder.updateNote",
          object_id: "wo-1",
          field: "note",
          value: { recommendation: "人工复核" },
          source_node_id: "tool-1",
          applied: false,
        }],
        error: { code: "TOOL_UNAVAILABLE", message: "安全工具适配器不可用", node_id: "tool-1", reason: null },
      }),
      nodeView({
        node_id: "action-1",
        kind: "apply_action",
        status: "canceled",
        summary: "因前序失败取消",
        started_at: null,
        finished_at: null,
        elapsed_ms: null,
        error: { code: "NODE_CANCELED", message: "因前序失败取消", node_id: "action-1", reason: "fail_fast" },
      }),
    ],
    ...overrides,
  };
}

function historySummary(overrides: Partial<LogicRunSummaryView> = {}): LogicRunSummaryView {
  return {
    run_id: "run-001",
    graph_id: "logic-001",
    mode: "dry_run",
    status: "failed",
    evaluated_revision: 7,
    graph_hash: HASH,
    production_written: false,
    started_at: "2026-08-01T08:00:00Z",
    finished_at: "2026-08-01T08:00:01Z",
    elapsed_ms: 812,
    total_tokens: null,
    node_counts: { executed: 2, skipped: 1, failed: 1, canceled: 1 },
    error_code: "TOOL_UNAVAILABLE",
    ...overrides,
  };
}

function props(overrides: Partial<LogicRunPanelProps> = {}): LogicRunPanelProps {
  return {
    run: runView(),
    runState: "ready",
    history: [historySummary()],
    historyState: "ready",
    selectedRunId: "run-001",
    onSelectRun: vi.fn(),
    ...overrides,
  };
}

function findButton(host: HTMLElement, label: string): HTMLButtonElement {
  const found = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((item) =>
    item.textContent?.includes(label) || item.getAttribute("aria-label")?.includes(label),
  );
  if (!found) throw new Error(`button not found: ${label}`);
  return found;
}

describe("LogicRunPanel", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  async function render(panelProps: LogicRunPanelProps) {
    await act(async () => root.render(<LogicRunPanel {...panelProps} />));
  }

  it("展示总体真实性字段、token null 和全部逐节点终态，并可定位错误节点", async () => {
    const onLocateNode = vi.fn();
    await render(props({ onLocateNode }));

    expect(host.textContent).toContain("服务端运行证据");
    expect(host.textContent).toContain("run-001");
    expect(host.textContent).toContain("dry_run");
    expect(host.textContent).toContain("revision 7");
    expect(host.textContent).toContain(HASH);
    expect(host.textContent).toContain("812 ms");
    expect(host.textContent).toContain("不写生产");
    expect(host.textContent).toContain("production_written=false");
    expect(host.textContent).toContain("总 Token未提供");
    expect(host.textContent).not.toContain("总 Token0");

    expect(host.textContent).toContain("已执行");
    expect(host.textContent).toContain("已跳过");
    expect(host.textContent).toContain("失败");
    expect(host.textContent).toContain("已取消");
    expect(host.textContent).toContain("high-risk");
    expect(host.textContent).toContain("branch_not_selected");
    expect(host.textContent).toContain("fail_fast");
    expect(host.textContent).toContain("TOOL_UNAVAILABLE");
    expect(host.textContent).toContain("安全工具调用");
    expect(host.textContent).toContain("work-order-reader");
    expect(host.textContent).toContain("read_only=true");
    expect(host.textContent).toContain("安全输出（已截断）");
    expect(host.textContent).toContain("服务端已按安全上限截断输出");
    expect(host.textContent).toContain("节点提议编辑（1）");
    expect(host.textContent).toContain("运行级提议编辑（1）");
    expect(host.textContent).toContain("applied=false");

    await act(async () => findButton(host, "定位节点 tool-1").click());
    expect(onLocateNode).toHaveBeenCalledWith("tool-1");
  });

  it("历史列表受控选择并支持下钻和加载更多，不自行改变选中记录", async () => {
    const onSelectRun = vi.fn();
    const onLoadMoreHistory = vi.fn();
    const history = [
      historySummary(),
      historySummary({
        run_id: "run-002",
        status: "succeeded",
        evaluated_revision: 6,
        started_at: "2026-08-01T07:00:00Z",
        elapsed_ms: 300,
        total_tokens: 24,
      }),
    ];
    await render(props({ history, onSelectRun, hasMoreHistory: true, onLoadMoreHistory }));

    const first = findButton(host, "run-001");
    const second = findButton(host, "run-002");
    expect(first.getAttribute("aria-pressed")).toBe("true");
    expect(second.getAttribute("aria-pressed")).toBe("false");
    expect(second.textContent).toContain("Token：24");
    expect(first.textContent).toContain("已执行 2");
    expect(first.textContent).toContain("错误：TOOL_UNAVAILABLE");

    await act(async () => second.click());
    expect(onSelectRun).toHaveBeenCalledWith("run-002");
    expect(first.getAttribute("aria-pressed")).toBe("true");
    expect(second.getAttribute("aria-pressed")).toBe("false");

    await act(async () => findButton(host, "加载更多运行记录").click());
    expect(onLoadMoreHistory).toHaveBeenCalledTimes(1);
  });

  it("展示真实空态、加载态和服务端错误，并仅通过回调重试", async () => {
    await render(props({ run: null, runState: "idle", history: [], historyState: "ready" }));
    expect(host.textContent).toContain("选择一条服务端运行记录");
    expect(host.textContent).toContain("暂无服务端运行记录");

    await render(props({ run: null, runState: "loading", history: [], historyState: "loading" }));
    expect(host.textContent).toContain("正在读取服务端运行详情");
    expect(host.textContent).toContain("读取中");

    const onRetryRun = vi.fn();
    const onRetryHistory = vi.fn();
    await render(props({
      run: null,
      runState: "error",
      runError: "详情网络中断",
      history: [],
      historyState: "error",
      historyError: "历史服务不可用",
      onRetryRun,
      onRetryHistory,
    }));
    expect(host.textContent).toContain("详情网络中断");
    expect(host.textContent).toContain("历史服务不可用");
    const retryButtons = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).filter((item) => item.textContent === "重试");
    expect(retryButtons).toHaveLength(2);
    await act(async () => retryButtons[0].click());
    await act(async () => retryButtons[1].click());
    expect(onRetryHistory).toHaveBeenCalledTimes(1);
    expect(onRetryRun).toHaveBeenCalledTimes(1);
  });

  it("production_written 不为 false 时拒绝把结果展示为安全试跑", async () => {
    const unsafeRun = { ...runView(), production_written: true } as unknown as LogicRunView;
    await render(props({ run: unsafeRun }));
    expect(host.textContent).toContain("拒绝展示为安全试跑");
    expect(host.textContent).toContain("production_written 不是 false");
    expect(host.textContent).not.toContain("不写生产 ·");
    expect(host.textContent).not.toContain("逐节点结果");
  });
});
