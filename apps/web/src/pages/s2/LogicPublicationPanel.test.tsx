import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  LogicPublicationPanel,
  type LogicPublicationPanelProps,
} from "./LogicPublicationPanel";
import type { LogicPublication } from "./logicPublicationContracts";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const HASH = "a".repeat(64);

function publication(overrides: Partial<LogicPublication> = {}): LogicPublication {
  return {
    publication_id: "pub-1",
    graph_id: "logic-1",
    graph_revision: 7,
    graph_hash: HASH,
    dry_run_id: "run-1",
    graph_snapshot: {
      id: "logic-1",
      name: "可信发布",
      description: "",
      status: "draft",
      schema_version: 1,
      revision: 7,
      published_version: null,
      graph_hash: HASH,
      persisted: true,
      nodes: [],
      edges: [],
      entry_node_ids: [],
      created_at: "2026-08-02T00:00:00Z",
      updated_at: "2026-08-02T00:01:00Z",
    },
    eval_suite_id: "suite-1",
    eval_report_id: "report-1",
    eval_gate: { gate_passed: true, pass_rate: 1, threshold: 0.92, passed: 10, failed: 0, total: 10, run_at: "2026-08-02T00:00:30Z" },
    actor: "user-1",
    created_at: "2026-08-02T00:02:00Z",
    ...overrides,
  };
}

function props(overrides: Partial<LogicPublicationPanelProps> = {}): LogicPublicationPanelProps {
  return {
    graphId: "logic-1",
    graphRevision: 7,
    graphHash: HASH,
    evalSuiteId: "suite-1",
    evalReportId: "report-1",
    evalGate: publication().eval_gate,
    publishDisabledReason: "",
    publishing: false,
    publication: publication(),
    publicationState: "ready",
    publications: [publication(), publication({ publication_id: "pub-older", graph_revision: 6, graph_hash: "b".repeat(64), graph_snapshot: { ...publication().graph_snapshot, revision: 6, graph_hash: "b".repeat(64) } })],
    publicationsState: "ready",
    selectedPublicationId: "pub-1",
    onPublish: vi.fn(),
    onSelectPublication: vi.fn(),
    ...overrides,
  };
}

function button(host: HTMLElement, label: string): HTMLButtonElement {
  const found = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((candidate) =>
    candidate.textContent?.includes(label) || candidate.getAttribute("aria-label")?.includes(label),
  );
  if (!found) throw new Error(`button not found: ${label}`);
  return found;
}

describe("LogicPublicationPanel", () => {
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

  async function render(panelProps: LogicPublicationPanelProps) {
    await act(async () => root.render(<LogicPublicationPanel {...panelProps} />));
  }

  it("展示精确 graph/Evals/publication 服务端证据并允许受控选择历史", async () => {
    const onSelectPublication = vi.fn();
    await render(props({ onSelectPublication }));

    expect(host.textContent).toContain("发布治理");
    expect(host.textContent).toContain("修订 7");
    expect(host.textContent).toContain(HASH);
    expect(host.textContent).toContain("suite-1");
    expect(host.textContent).toContain("report-1");
    expect(host.textContent).toContain("run-1");
    expect(host.textContent).toContain("100.0%");
    expect(host.textContent).toContain("pub-1");
    expect(host.textContent).toContain("user-1");

    const older = button(host, "正式发布记录 2");
    expect(older.getAttribute("aria-pressed")).toBe("false");
    await act(async () => older.click());
    expect(onSelectPublication).toHaveBeenCalledWith("pub-older");
    expect(older.getAttribute("aria-pressed")).toBe("false");
  });

  it("禁用原因可见，发布中阻止重复点击；满足门禁时只调用受控回调", async () => {
    const onPublish = vi.fn();
    await render(props({ publication: null, publicationState: "idle", publishDisabledReason: "存在未保存更改", onPublish }));
    expect(button(host, "发布当前修订").disabled).toBe(true);
    expect(host.textContent).toContain("存在未保存更改");

    await render(props({ publication: null, publicationState: "idle", onPublish }));
    await act(async () => button(host, "发布当前修订").click());
    expect(onPublish).toHaveBeenCalledTimes(1);

    await render(props({ publication: null, publicationState: "loading", publishing: true, onPublish }));
    expect(button(host, "发布中").disabled).toBe(true);
  });

  it("缺失报告、报告失败和目标错配均前置禁用并展示具体原因", async () => {
    await render(props({ evalReportId: null, evalGate: null, publishDisabledReason: "" }));
    expect(button(host, "发布当前修订").disabled).toBe(true);
    expect(host.textContent).toContain("请选择与当前修订绑定的评测报告");

    await render(props({ publishDisabledReason: "Eval report 门控未通过" }));
    expect(button(host, "发布当前修订").disabled).toBe(true);
    expect(host.textContent).toContain("门控未通过");

    await render(props({ publishDisabledReason: "Eval report 目标 revision/hash 与当前图不一致" }));
    expect(button(host, "发布当前修订").disabled).toBe(true);
    expect(host.textContent).toContain("目标 revision/hash 与当前图不一致");
  });

  it("展示列表/详情加载、空态、错误与受控重试", async () => {
    await render(props({ publication: null, publicationState: "loading", publications: [], publicationsState: "loading" }));
    expect(host.textContent).toContain("正在读取发布详情");
    expect(host.textContent).toContain("正在读取发布历史");

    await render(props({ publication: null, publicationState: "idle", publications: [], publicationsState: "ready" }));
    expect(host.textContent).toContain("暂无服务端发布记录");

    const onRetryPublication = vi.fn();
    const onRetryPublications = vi.fn();
    await render(props({
      publication: null,
      publicationState: "error",
      publicationError: "详情网络中断",
      publications: [],
      publicationsState: "error",
      publicationsError: "历史服务不可用",
      onRetryPublication,
      onRetryPublications,
    }));
    expect(host.textContent).toContain("详情网络中断");
    expect(host.textContent).toContain("历史服务不可用");
    await act(async () => button(host, "重试发布详情").click());
    await act(async () => button(host, "重试发布历史").click());
    expect(onRetryPublication).toHaveBeenCalledTimes(1);
    expect(onRetryPublications).toHaveBeenCalledTimes(1);
  });

  it("自动化条件未齐时提供上线执行审批入口，不触发本地绑定", async () => {
    await render(props());
    const automation = [...host.querySelectorAll<HTMLAnchorElement>("a")].find((item) => item.textContent?.includes("进入上线执行审批补齐自动化条件"));
    expect(automation?.getAttribute("href")).toBe("/aip/production-contracts");
    expect(automation?.title).toContain("生产调度");
    expect(host.textContent).toContain("仅可绑定不可变的正式发布版本");
  });
});
