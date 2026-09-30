import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { RuntimeInstallation, RuntimeConfigurationCandidates } from "../../../api/assetControl/types";
import { RuntimeInstallationPanel } from "./RuntimeInstallationPanel";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const runtime: RuntimeInstallation = {
  installationId: "22222222-2222-4222-8222-222222222222",
  installationRevision: 5,
  installationEtag: 5,
  installationState: "active",
  effectiveState: "disabled",
  binding: {
    generation: "44444444-4444-4444-8444-444444444444",
    installationRevision: 5,
    profileRef: "runtime-profile/python-v1",
    configRef: null,
    executionEpoch: 2,
    desiredState: "disabled",
    observedState: "disabled",
    enabled: false,
    operationFence: false,
    revision: 2,
  },
  currentOperation: null,
  ui: null,
  allowedActions: ["configure", "disable"],
  reasons: ["运行实例已停用。"],
};

describe("RuntimeInstallationPanel", () => {
  let host: HTMLDivElement;
  let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("renders only server-allowed actions and locks disable to the current binding", async () => {
    const execute = vi.fn();
    await act(async () => root.render(<RuntimeInstallationPanel state={{ data: runtime, status: "ready", error: null, refreshing: false, stale: false, reload: vi.fn() }} offline={false} pending={null} error={null} receipt={null} hasRetrySameCommand={false} canRetrySameCommand={false} onRetrySameCommand={vi.fn()} onExecute={execute} />));
    expect(host.textContent).toContain("更新运行配置");
    expect(host.textContent).toContain("停用运行实例");
    expect(host.textContent).not.toContain("启用运行实例");
    const disable = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "停用运行实例")!;
    await act(async () => disable.click());
    const confirm = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "确认停用运行实例")!;
    await act(async () => confirm.click());
    expect(execute).toHaveBeenCalledWith("disable", { generation: runtime.binding?.generation, bindingRevision: 2 });
  });

  it("shows eight current tenant candidate blockers without claiming runtime readiness", async () => {
    const counts = { responsibility_plans: 0, runtime_policies: 0, data_policies: 0, egress_policies: 0, network_policies: 0, quota_policies: 0, budget_policies: 0, budgets: 0 };
    const data: RuntimeConfigurationCandidates = { installationId: runtime.installationId, installationRevision: 5, installationEtag: 5, counts, missing: Object.keys(counts), allPresent: false, authorityKind: "tenant_candidates_not_installation_binding" };
    const candidates = { data, status: "ready" as const, error: null, refreshing: false, stale: false, reload: vi.fn(), isCurrent: () => true };
    const props = { state: { data: runtime, status: "ready" as const, error: null, refreshing: false, stale: false, reload: vi.fn() }, candidates, offline: false, pending: null, error: null, receipt: null, hasRetrySameCommand: false, canRetrySameCommand: false, onRetrySameCommand: vi.fn(), onExecute: vi.fn() };
    await act(async () => root.render(<MemoryRouter><RuntimeInstallationPanel {...props} /></MemoryRouter>));
    expect(host.querySelectorAll('[aria-label="当前配置权威候选"] li')).toHaveLength(8);
    expect(host.textContent).toContain("缺少当前候选");
    expect(host.textContent).toContain("不代表可以启用");
    expect(host.textContent).toContain("签名 BI 职责准备需核验当前安装、正式 OIDC 身份、六个 active 数字同事及当前权限");
    const rows = Array.from(host.querySelectorAll<HTMLLIElement>('[aria-label="当前配置权威候选"] li'));
    expect(rows.find(row => row.textContent?.startsWith("职责计划"))?.querySelector("a")?.getAttribute("href")).toBe(`/aip/production-contracts?installationId=${runtime.installationId}&installationRevision=5&installationEtag=5`);
    const budgetRow = rows.find(row => row.textContent?.startsWith("预算修订"));
    expect(budgetRow?.querySelector("a")?.getAttribute("href")).toBe("/aip/capacity");
    expect(budgetRow?.textContent).toContain("创建预算草稿（不生效）");
    const runtimePolicyRow = rows.find(row => row.textContent?.startsWith("运行策略"));
    expect(runtimePolicyRow?.querySelector("a")?.getAttribute("href")).toBe("/aip/model-runtime");
    expect(runtimePolicyRow?.textContent).toContain("查看当前运行策略");
    expect(rows.find(row => row.textContent?.startsWith("数据分类策略"))?.textContent).toContain("创建草稿（不生效）");
    expect(rows.find(row => row.textContent?.startsWith("出站策略"))?.textContent).toContain("创建草稿（不生效）");
    const networkRow = rows.find(row => row.textContent?.startsWith("网络策略"));
    expect(networkRow?.querySelector("a")?.getAttribute("href")).toBe("/aip/model-runtime");
    expect(networkRow?.textContent).toContain("先准备出站策略草稿（不生效）");
    const budgetPolicyRow = rows.find(row => row.textContent?.startsWith("预算策略"));
    expect(budgetPolicyRow?.querySelector("a")?.getAttribute("href")).toBe("/aip/capacity");
    expect(budgetPolicyRow?.textContent).toContain("先准备预算修订草稿（不生效）");
    expect(host.querySelectorAll('[aria-label="当前配置权威候选"] a')).toHaveLength(8);
    await act(async () => root.render(<MemoryRouter><RuntimeInstallationPanel {...props} candidates={{ ...candidates, data: { ...data, installationEtag: 4 } }} /></MemoryRouter>));
    expect(host.textContent).toContain("未核验或读回已过期");
    expect(host.querySelectorAll('[aria-label="当前配置权威候选"] li')).toHaveLength(0);
    expect(host.textContent).not.toContain("个当前候选，尚需安装绑定核验");
  });

  it("disables every mutation while offline", async () => {
    await act(async () => root.render(<RuntimeInstallationPanel state={{ data: runtime, status: "ready", error: null, refreshing: false, stale: false, reload: vi.fn() }} offline pending={null} error={null} receipt={null} hasRetrySameCommand={false} canRetrySameCommand={false} onRetrySameCommand={vi.fn()} onExecute={vi.fn()} />));
    expect(Array.from(host.querySelectorAll<HTMLButtonElement>("button")).filter((button) => button.textContent?.includes("运行")).every((button) => button.disabled)).toBe(true);
  });

  it("does not offer preparation when the current Host has no assignment", async () => {
    const apply = { ...runtime, installationState: "approved" as const, effectiveState: "not_prepared", binding: null, allowedActions: ["runtime-apply" as const], preparationExecutable: false };
    const execute = vi.fn();
    await act(async () => root.render(<RuntimeInstallationPanel state={{ data: apply, status: "ready", error: null, refreshing: false, stale: false, reload: vi.fn() }} offline={false} pending={null} error={null} receipt={null} hasRetrySameCommand={false} canRetrySameCommand={false} onRetrySameCommand={vi.fn()} onExecute={execute} />));
    const prepare = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find(button => button.textContent === "准备运行资源")!;
    expect(prepare.disabled).toBe(true);
    expect(host.textContent).toContain("Host");
    expect(execute).not.toHaveBeenCalled();
  });

  it("在断网、过期、刷新或服务端撤回动作时关闭已打开的确认框", async () => {
    const baseState = { data: runtime, status: "ready" as const, error: null, refreshing: false, stale: false, reload: vi.fn() };
    const props = { state: baseState, offline: false, pending: null, error: null, receipt: null, hasRetrySameCommand: false, canRetrySameCommand: true, onRetrySameCommand: vi.fn(), onExecute: vi.fn() };
    await act(async () => root.render(<RuntimeInstallationPanel {...props} />));
    await act(async () => Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "停用运行实例")!.click());
    expect(host.querySelector('[role="dialog"]')).not.toBeNull();
    await act(async () => root.render(<RuntimeInstallationPanel {...props} offline />));
    expect(host.querySelector('[role="dialog"]')).toBeNull();
    const retry = () => Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent?.includes("原幂等命令"));
    expect(retry()).toBeUndefined();
    await act(async () => root.render(<RuntimeInstallationPanel {...props} hasRetrySameCommand />));
    expect(host.textContent).toContain("结果未知：已冻结重发");
    expect(Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find(button => button.textContent === "停用运行实例")?.disabled).toBe(true);

    await act(async () => root.render(<RuntimeInstallationPanel {...props} />));
    expect(retry()).toBeUndefined();
    expect(props.onRetrySameCommand).not.toHaveBeenCalled();

    await act(async () => Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "停用运行实例")!.click());
    await act(async () => root.render(<RuntimeInstallationPanel {...props} state={{ ...baseState, stale: true }} />));
    expect(host.querySelector('[role="dialog"]')).toBeNull();

    await act(async () => root.render(<RuntimeInstallationPanel {...props} />));
    await act(async () => Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "停用运行实例")!.click());
    await act(async () => root.render(<RuntimeInstallationPanel {...props} state={{ ...baseState, refreshing: true }} />));
    expect(host.querySelector('[role="dialog"]')).toBeNull();

    await act(async () => root.render(<RuntimeInstallationPanel {...props} />));
    await act(async () => Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "停用运行实例")!.click());
    await act(async () => root.render(<RuntimeInstallationPanel {...props} state={{ ...baseState, data: { ...runtime, allowedActions: ["configure"] } }} />));
    expect(host.querySelector('[role="dialog"]')).toBeNull();
    await act(async () => root.render(<RuntimeInstallationPanel {...props} canRetrySameCommand={false} state={{ ...baseState, data: { ...runtime, allowedActions: ["configure"] } }} />));
    expect(retry()).toBeUndefined();
  });

  it("在 binding 身份变化时关闭确认框且不把目标改绑到新代次", async () => {
    const execute = vi.fn();
    const baseState = { data: runtime, status: "ready" as const, error: null, refreshing: false, stale: false, reload: vi.fn() };
    const props = { state: baseState, offline: false, pending: null, error: null, receipt: null, hasRetrySameCommand: false, canRetrySameCommand: true, onRetrySameCommand: vi.fn(), onExecute: execute };
    await act(async () => root.render(<RuntimeInstallationPanel {...props} />));
    await act(async () => Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "停用运行实例")!.click());
    expect(host.querySelector('[role="dialog"]')).not.toBeNull();

    const nextRuntime: RuntimeInstallation = {
      ...runtime,
      binding: runtime.binding ? { ...runtime.binding, generation: "66666666-6666-4666-8666-666666666666", revision: 3, executionEpoch: 3 } : null,
    };
    await act(async () => root.render(<RuntimeInstallationPanel {...props} canRetrySameCommand={false} state={{ ...baseState, data: nextRuntime }} />));
    expect(host.querySelector('[role="dialog"]')).toBeNull();
    expect(Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent?.includes("原幂等命令"))).toBeUndefined();
    expect(execute).not.toHaveBeenCalled();
  });

  it("renders a fixed Chinese failure explanation and audit events without raw codes", async () => {
    const failed: RuntimeInstallation = {
      ...runtime,
      allowedActions: [],
      currentOperation: {
        operationId: "55555555-5555-4555-8555-555555555555",
        installationId: runtime.installationId,
        kind: "runtime-apply",
        phase: "failed",
        status: "failed",
        revision: 3,
        requestedBy: "operator",
        approvedBy: null,
        expectedInstallationEtag: 5,
        expectedBindingRevision: null,
        deadline: "2026-09-07T10:00:00Z",
        failureCode: "PREPARATION_EXECUTION_FAILED",
        createdAt: "2026-09-07T09:00:00Z",
        events: [{ sequence: 1, type: "preparation_failed", payloadHash: `sha256:${"a".repeat(64)}`, occurredAt: "2026-09-07T09:01:00Z" }],
      },
    };
    await act(async () => root.render(<RuntimeInstallationPanel state={{ data: failed, status: "ready", error: null, refreshing: false, stale: false, reload: vi.fn() }} offline={false} pending={null} error={null} receipt={null} hasRetrySameCommand={false} canRetrySameCommand={false} onRetrySameCommand={vi.fn()} onExecute={vi.fn()} />));
    expect(host.textContent).toContain("运行资源准备失败");
    expect(host.textContent).toContain("合法下一步以服务端允许动作区为准");
    expect(host.textContent).toContain("查看运行审计事件（1）");
    expect(host.textContent).not.toContain("PREPARATION_EXECUTION_FAILED");
    expect(host.textContent).not.toContain("sha256:");
  });

  it("mounts the isolated host only from a ready server UI session", async () => {
    const hash = `sha256:${"a".repeat(64)}` as const;
    const ready: RuntimeInstallation = {
      ...runtime,
      effectiveState: "ready",
      ui: {
        title: "隔离测试扩展",
        signedResourceUrl: `http://127.0.0.1:18182/extensions/test/index.html?contentHash=${encodeURIComponent(hash)}`,
        resourceHash: hash,
        initialRoute: "/test",
        routeClaims: ["/test"],
        readOperationClaims: [],
        commandOperationClaims: [],
      },
    };
    await act(async () => root.render(<RuntimeInstallationPanel state={{ data: ready, status: "ready", error: null, refreshing: false, stale: false, reload: vi.fn() }} offline={false} pending={null} error={null} receipt={null} hasRetrySameCommand={false} canRetrySameCommand={false} onRetrySameCommand={vi.fn()} onExecute={vi.fn()} />));
    expect(host.querySelector('iframe[title="隔离测试扩展"]')).not.toBeNull();
    expect(host.textContent).toContain("隔离测试扩展");
  });
  it("选择已登记配置提交exact引用且失效后不能复用", async () => {
    const execute = vi.fn();
    const ref = { configurationId: "77777777-7777-4777-8777-777777777777", revision: 1, hash: "sha256:" + "a".repeat(64) };
    const catalog = { installationId: runtime.installationId, installationRevision: 5, installationEtag: 5,
      generation: runtime.binding!.generation, bindingRevision: 2, items: [{ ref, isCurrent: false }], hasMore: false };
    const configurations = { data: catalog, status: "ready" as const, error: null, refreshing: false, stale: false, reload: vi.fn(), isCurrent: () => true };
    const props = { state: { data: runtime, status: "ready" as const, error: null, refreshing: false, stale: false, reload: vi.fn() }, configurations,
      offline: false, pending: null, error: null, receipt: null, hasRetrySameCommand: false, canRetrySameCommand: false, onRetrySameCommand: vi.fn(), onExecute: execute };
    await act(async () => root.render(<RuntimeInstallationPanel {...props} />));
    const open = async () => act(async () => Array.from(host.querySelectorAll("button")).find(b => b.textContent === "更新运行配置")!.click());
    await open();
    expect(host.querySelector('input[aria-label="配置 Hash"]')).toBeNull();
    const select = host.querySelector('select')!;
    await act(async () => { select.value = JSON.stringify(ref); select.dispatchEvent(new Event("change", { bubbles: true })); });
    await act(async () => Array.from(host.querySelectorAll("button")).find(b => b.textContent === "确认更新运行配置")!.click());
    expect(execute).toHaveBeenCalledWith("configure", { generation: runtime.binding!.generation, bindingRevision: 2, configRef: ref });
    await open();
    await act(async () => root.render(<RuntimeInstallationPanel {...props} configurations={{ ...configurations, stale: true }} />));
    expect(host.querySelector('[role="dialog"]')).toBeNull();
    expect(execute).toHaveBeenCalledTimes(1);
  });

});
