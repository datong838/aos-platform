import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { assetControlClient } from "../../../api/assetControl/client";
import { setTenant } from "../../../api/tenant";
import { STORED_COMPOSITION_LOCK_FIXTURE } from "../../../api/assetControl/compositionFixtures";
import {
  INSTALLATION_ACTIVE_FIXTURE,
  INSTALLATION_APPLIED_FIXTURE,
  INSTALLATION_APPROVED_FIXTURE,
  INSTALLATION_REJECTED_FIXTURE,
  INSTALLATION_ROLLED_BACK_FIXTURE,
  INSTALLATION_SUBMITTED_FIXTURE,
} from "../../../api/assetControl/installationActionFixtures";
import { INSTALLATION_DETAIL_FIXTURE, INSTALLATION_DRAFT_FIXTURE, INSTALLATION_LIST_FIXTURE } from "../../../api/assetControl/installationFixtures";
import { REGISTRY_BUNDLE_DETAIL_FIXTURE, REGISTRY_BUNDLE_LIST_FIXTURE, REGISTRY_VERSION_DETAIL_FIXTURE } from "../../../api/assetControl/registryFixtures";
import { setConnectivity } from "../../../lib/offlineStore";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const hooks = vi.hoisted(() => ({
  registryStatus: "ready" as const,
  installationData: null as unknown,
}));

const reload = vi.fn();

vi.mock("../assetBundles/readHooks", () => ({
  useRegistryBundles: () => ({
    data: hooks.registryStatus === "ready" ? REGISTRY_BUNDLE_LIST_FIXTURE : [],
    status: hooks.registryStatus,
    error: null,
    refreshing: false,
    stale: false,
    reload,
  }),
  useRegistryBundle: (selection: unknown) => ({
    data: selection ? REGISTRY_BUNDLE_DETAIL_FIXTURE : null,
    status: selection ? "ready" : "idle",
    error: null,
    refreshing: false,
    stale: false,
    reload,
  }),
  useRegistryVersion: (selection: unknown) => ({
    data: selection ? REGISTRY_VERSION_DETAIL_FIXTURE : null,
    status: selection ? "ready" : "idle",
    error: null,
    refreshing: false,
    stale: false,
    reload,
  }),
  useInstallations: () => ({
    data: INSTALLATION_LIST_FIXTURE,
    status: "ready",
    error: null,
    refreshing: false,
    stale: false,
    reload,
  }),
  useInstallation: (installationId: string | null) => ({
    data: installationId
      ? (hooks.installationData ?? INSTALLATION_DETAIL_FIXTURE)
      : null,
    status: installationId ? "ready" : "idle",
    error: null,
    refreshing: false,
    stale: false,
    reload,
  }),
}));

describe("M3-4/M3-5 AssetBundlesPage integration", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    hooks.installationData = null;
    setTenant({
      orgId: "dev-org",
      projectId: "dev-project",
      workspaceName: "测试工作区",
      subject: "installer@example.test",
      roles: ["asset-installer"],
    });
    setConnectivity("online", "asset-bundles-page-test");
    vi.spyOn(assetControlClient, "resolveComposition").mockResolvedValue(
      STORED_COMPOSITION_LOCK_FIXTURE,
    );
    vi.spyOn(assetControlClient, "getCompositionLock").mockResolvedValue(
      STORED_COMPOSITION_LOCK_FIXTURE,
    );
    vi.spyOn(assetControlClient, "createInstallation").mockResolvedValue(
      INSTALLATION_DRAFT_FIXTURE,
    );
    vi.spyOn(assetControlClient, "getInstallation").mockResolvedValue(
      INSTALLATION_DETAIL_FIXTURE,
    );
    vi.spyOn(assetControlClient, "rollbackInstallation").mockResolvedValue(
      INSTALLATION_ROLLED_BACK_FIXTURE,
    );
    vi.spyOn(assetControlClient, "submitInstallation").mockResolvedValue(
      INSTALLATION_SUBMITTED_FIXTURE,
    );
    vi.spyOn(assetControlClient, "approveInstallation").mockResolvedValue(
      INSTALLATION_APPROVED_FIXTURE,
    );
    vi.spyOn(assetControlClient, "rejectInstallation").mockResolvedValue(
      INSTALLATION_REJECTED_FIXTURE,
    );
    vi.spyOn(assetControlClient, "applyInstallation").mockResolvedValue(
      INSTALLATION_APPLIED_FIXTURE,
    );
    vi.spyOn(assetControlClient, "verifyInstallation").mockResolvedValue(
      INSTALLATION_ACTIVE_FIXTURE,
    );
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
    vi.clearAllMocks();
  });

  async function renderPage() {
    const { AssetBundlesPage } = await import("../AssetBundlesPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(AssetBundlesPage)));
    });
  }

  function button(label: string): HTMLButtonElement {
    const match = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find(
      (node) => node.textContent === label,
    );
    if (!match) throw new Error(`button missing: ${label}`);
    return match;
  }

  async function openInstallation() {
    await act(async () => button("安装管理").click());
    await act(async () => button("查看事件").click());
  }

  async function confirmAction(
    actionLabel: string,
    options: { approve?: boolean; reasonLabel?: string; reason?: string } = {},
  ) {
    await act(async () => button(actionLabel).click());
    if (options.approve) {
      const acknowledgement = host.querySelector<HTMLInputElement>(
        'input[type="checkbox"]',
      );
      if (!acknowledgement) throw new Error("approval acknowledgement missing");
      await act(async () => acknowledgement.click());
    }
    if (options.reasonLabel) {
      const textarea = host.querySelector<HTMLTextAreaElement>(
        `textarea[aria-label="${options.reasonLabel}"]`,
      );
      if (!textarea) throw new Error(`reason missing: ${options.reasonLabel}`);
      await act(async () => {
        Object.getOwnPropertyDescriptor(
          HTMLTextAreaElement.prototype,
          "value",
        )?.set?.call(textarea, options.reason ?? "");
        textarea.dispatchEvent(new Event("input", { bubbles: true }));
      });
    }
    await act(async () => button(`确认${actionLabel}`).click());
  }

  it("renders canonical Registry facts without the legacy demo bundles", async () => {
    await renderPage();
    const text = host.textContent ?? "";

    expect(text).toContain("FDE 资产包");
    expect(text).toContain(REGISTRY_BUNDLE_LIST_FIXTURE[0].bundleId);
    expect(text).toContain("不使用演示数据兜底");
    expect(text).not.toContain("apollo-core");
    expect(text).not.toContain("fde-维修派单");
  });

  it("switches to server-paged installations and opens the event timeline", async () => {
    await renderPage();
    const installationTab = Array.from(host.querySelectorAll('[role="tab"]')).find(
      (node) => node.textContent === "安装管理",
    ) as HTMLButtonElement;
    await act(async () => installationTab.click());

    expect(host.textContent).toContain(INSTALLATION_LIST_FIXTURE.items[0].displayName);
    const open = Array.from(host.querySelectorAll("button")).find(
      (node) => node.textContent === "查看事件",
    ) as HTMLButtonElement;
    await act(async () => open.click());

    const text = host.textContent ?? "";
    expect(text).toContain("安装详情与事件时间线");
    expect(text).toContain(INSTALLATION_DETAIL_FIXTURE.installationId);
    expect(text).toContain("不提供历史 revision 完整快照");
    expect(text).not.toContain("批准安装");
  });

  it("executes rollback through the single action controller and rereads facts", async () => {
    const getInstallation = vi.mocked(assetControlClient.getInstallation);
    getInstallation
      .mockReset()
      .mockResolvedValueOnce(INSTALLATION_DETAIL_FIXTURE)
      .mockResolvedValueOnce(INSTALLATION_ROLLED_BACK_FIXTURE);

    await renderPage();
    const installationTab = Array.from(host.querySelectorAll('[role="tab"]')).find(
      (node) => node.textContent === "安装管理",
    ) as HTMLButtonElement;
    await act(async () => installationTab.click());
    const open = Array.from(host.querySelectorAll("button")).find(
      (node) => node.textContent === "查看事件",
    ) as HTMLButtonElement;
    await act(async () => open.click());

    const rollback = Array.from(host.querySelectorAll("button")).find(
      (node) => node.textContent === "回滚",
    ) as HTMLButtonElement;
    expect(rollback.disabled).toBe(false);
    await act(async () => rollback.click());

    const reason = host.querySelector(
      'textarea[aria-label="回滚原因"]',
    ) as HTMLTextAreaElement;
    await act(async () => {
      const setValue = Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype,
        "value",
      )?.set;
      setValue?.call(reason, "operator rollback");
      reason.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const confirm = Array.from(host.querySelectorAll("button")).find(
      (node) => node.textContent === "确认回滚",
    ) as HTMLButtonElement;
    await act(async () => confirm.click());

    expect(assetControlClient.rollbackInstallation).toHaveBeenCalledWith(
      INSTALLATION_DETAIL_FIXTURE.installationId,
      { reason: "operator rollback" },
      expect.objectContaining({
        idempotencyKey: expect.any(String),
        etagVersion: INSTALLATION_DETAIL_FIXTURE.etagVersion,
      }),
    );
    expect(getInstallation).toHaveBeenCalledTimes(2);
    expect(host.textContent).toContain("安装动作已完成，并已回读服务端最新状态");
  });

  it("builds approve only from the reread installation and canonical lock", async () => {
    hooks.installationData = INSTALLATION_SUBMITTED_FIXTURE;
    setTenant({
      subject: "approver@example.test",
      roles: ["asset-install-approver"],
    });
    const getInstallation = vi.mocked(assetControlClient.getInstallation);
    getInstallation
      .mockReset()
      .mockResolvedValueOnce(INSTALLATION_SUBMITTED_FIXTURE)
      .mockResolvedValueOnce(INSTALLATION_APPROVED_FIXTURE);

    await renderPage();
    const installationTab = Array.from(host.querySelectorAll('[role="tab"]')).find(
      (node) => node.textContent === "安装管理",
    ) as HTMLButtonElement;
    await act(async () => installationTab.click());
    const open = Array.from(host.querySelectorAll("button")).find(
      (node) => node.textContent === "查看事件",
    ) as HTMLButtonElement;
    await act(async () => open.click());
    const approve = Array.from(host.querySelectorAll("button")).find(
      (node) => node.textContent === "批准",
    ) as HTMLButtonElement;
    await act(async () => approve.click());

    const hashConfirmation = host.querySelector(
      'input[type="checkbox"]',
    ) as HTMLInputElement;
    expect(host.querySelectorAll('input[type="text"]')).toHaveLength(0);
    await act(async () => hashConfirmation.click());
    const confirm = Array.from(host.querySelectorAll("button")).find(
      (node) => node.textContent === "确认批准",
    ) as HTMLButtonElement;
    await act(async () => confirm.click());

    expect(assetControlClient.getCompositionLock).toHaveBeenCalledWith(
      INSTALLATION_SUBMITTED_FIXTURE.current.compositionId,
      INSTALLATION_SUBMITTED_FIXTURE.current.lockRevision,
    );
    expect(assetControlClient.approveInstallation).toHaveBeenCalledWith(
      INSTALLATION_SUBMITTED_FIXTURE.installationId,
      {
        lockHash: STORED_COMPOSITION_LOCK_FIXTURE.lockHash,
        permissionDiffHash: STORED_COMPOSITION_LOCK_FIXTURE.permissionDiffHash,
        migrationPlanHash: STORED_COMPOSITION_LOCK_FIXTURE.migrationPlanHash,
        contributionDiffHash: STORED_COMPOSITION_LOCK_FIXTURE.contributionDiffHash,
      },
      expect.objectContaining({
        idempotencyKey: expect.any(String),
        etagVersion: INSTALLATION_SUBMITTED_FIXTURE.etagVersion,
      }),
    );
  });

  it("runs the page-level maker/checker dry lifecycle through final rereads", async () => {
    hooks.installationData = INSTALLATION_DRAFT_FIXTURE;
    setTenant({
      subject: "maker@example.test",
      roles: ["asset-installer"],
    });
    const getInstallation = vi.mocked(assetControlClient.getInstallation);
    getInstallation.mockReset().mockImplementation(async () =>
      hooks.installationData as typeof INSTALLATION_DRAFT_FIXTURE
    );
    vi.mocked(assetControlClient.submitInstallation).mockImplementation(async () => {
      hooks.installationData = INSTALLATION_SUBMITTED_FIXTURE;
      return INSTALLATION_SUBMITTED_FIXTURE;
    });
    vi.mocked(assetControlClient.approveInstallation).mockImplementation(async () => {
      hooks.installationData = INSTALLATION_APPROVED_FIXTURE;
      return INSTALLATION_APPROVED_FIXTURE;
    });
    vi.mocked(assetControlClient.applyInstallation).mockImplementation(async () => {
      hooks.installationData = INSTALLATION_APPLIED_FIXTURE;
      return INSTALLATION_APPLIED_FIXTURE;
    });
    vi.mocked(assetControlClient.verifyInstallation).mockImplementation(async () => {
      hooks.installationData = INSTALLATION_ACTIVE_FIXTURE;
      return INSTALLATION_ACTIVE_FIXTURE;
    });
    vi.mocked(assetControlClient.rollbackInstallation).mockImplementation(async () => {
      hooks.installationData = INSTALLATION_ROLLED_BACK_FIXTURE;
      return INSTALLATION_ROLLED_BACK_FIXTURE;
    });

    await renderPage();
    await openInstallation();
    await confirmAction("提交审批");
    expect(assetControlClient.submitInstallation).toHaveBeenCalledWith(
      INSTALLATION_DRAFT_FIXTURE.installationId,
      expect.objectContaining({ etagVersion: 1 }),
    );

    await act(async () => setTenant({
      subject: "approver@example.test",
      roles: ["asset-install-approver"],
    }));
    await confirmAction("批准", { approve: true });
    expect(assetControlClient.approveInstallation).toHaveBeenCalledWith(
      INSTALLATION_SUBMITTED_FIXTURE.installationId,
      expect.objectContaining({
        lockHash: INSTALLATION_SUBMITTED_FIXTURE.current.lockHash,
        permissionDiffHash: INSTALLATION_SUBMITTED_FIXTURE.current.permissionDiffHash,
        migrationPlanHash: INSTALLATION_SUBMITTED_FIXTURE.current.migrationPlanHash,
        contributionDiffHash: INSTALLATION_SUBMITTED_FIXTURE.current.contributionDiffHash,
      }),
      expect.objectContaining({ etagVersion: 2 }),
    );

    await act(async () => setTenant({
      subject: "installer@example.test",
      roles: ["asset-installer"],
    }));
    await confirmAction("执行 Apply");
    expect(assetControlClient.applyInstallation).toHaveBeenCalledWith(
      INSTALLATION_APPROVED_FIXTURE.installationId,
      expect.objectContaining({ etagVersion: 3 }),
    );
    expect(host.textContent).toContain("dry_apply / valid");

    await confirmAction("验证并激活");
    expect(assetControlClient.verifyInstallation).toHaveBeenCalledWith(
      INSTALLATION_APPLIED_FIXTURE.installationId,
      expect.objectContaining({ etagVersion: 4 }),
    );
    expect(host.textContent).toContain("verification / valid");
    expect(host.textContent).toContain("Active revision");

    await confirmAction("回滚", {
      reasonLabel: "回滚原因",
      reason: "  operator rollback  ",
    });
    expect(assetControlClient.rollbackInstallation).toHaveBeenCalledWith(
      INSTALLATION_ACTIVE_FIXTURE.installationId,
      { reason: "operator rollback" },
      expect.objectContaining({ etagVersion: 5 }),
    );
    expect(host.textContent).toContain("rollback / valid");
    expect(host.textContent).toContain("当前状态是终态，没有可执行动作");
    expect(getInstallation).toHaveBeenCalledTimes(10);
  });

  it("executes the submitted reject branch with a normalized reason", async () => {
    hooks.installationData = INSTALLATION_SUBMITTED_FIXTURE;
    setTenant({
      subject: "approver@example.test",
      roles: ["asset-install-approver"],
    });
    vi.mocked(assetControlClient.getInstallation).mockReset().mockImplementation(
      async () => hooks.installationData as typeof INSTALLATION_SUBMITTED_FIXTURE,
    );
    vi.mocked(assetControlClient.rejectInstallation).mockImplementation(async () => {
      hooks.installationData = INSTALLATION_REJECTED_FIXTURE;
      return INSTALLATION_REJECTED_FIXTURE;
    });

    await renderPage();
    await openInstallation();
    await confirmAction("拒绝", {
      reasonLabel: "拒绝原因",
      reason: "  policy mismatch  ",
    });

    expect(assetControlClient.rejectInstallation).toHaveBeenCalledWith(
      INSTALLATION_SUBMITTED_FIXTURE.installationId,
      { reason: "policy mismatch" },
      expect.objectContaining({ etagVersion: 2 }),
    );
    expect(host.textContent).toContain("当前状态是终态，没有可执行动作");
  });

  it.each([409, 412])(
    "rereads after %s and never replays the stale approval confirmation",
    async (status) => {
      hooks.installationData = INSTALLATION_SUBMITTED_FIXTURE;
      setTenant({
        subject: "approver@example.test",
        roles: ["asset-install-approver"],
      });
      const refreshed = INSTALLATION_APPROVED_FIXTURE;
      const getInstallation = vi.mocked(assetControlClient.getInstallation);
      getInstallation
        .mockReset()
        .mockResolvedValueOnce(INSTALLATION_SUBMITTED_FIXTURE)
        .mockImplementationOnce(async () => {
          hooks.installationData = refreshed;
          return refreshed;
        });
      vi.mocked(assetControlClient.approveInstallation).mockRejectedValueOnce(
        Object.assign(new Error("conflict"), {
          status,
          body: {
            code: status === 409 ? "INSTALLATION_STATE_CONFLICT" : "ETAG_MISMATCH",
            message: "installation changed",
            details: null,
            traceId: `trace-${status}`,
          },
        }),
      );

      await renderPage();
      await openInstallation();
      await confirmAction("批准", { approve: true });

      expect(assetControlClient.approveInstallation).toHaveBeenCalledTimes(1);
      expect(getInstallation).toHaveBeenCalledTimes(2);
      expect(host.textContent).toContain("安装状态已经变化，已回读最新服务端详情");
      expect(host.textContent).not.toContain("确认批准");
      expect(host.textContent).not.toContain("使用原幂等命令恢复");
    },
  );

  it("fails closed for maker/admin and reacts to offline and role changes", async () => {
    hooks.installationData = INSTALLATION_SUBMITTED_FIXTURE;
    setTenant({
      subject: INSTALLATION_SUBMITTED_FIXTURE.current.requestedBy,
      roles: ["admin"],
    });
    await renderPage();
    await openInstallation();

    expect(button("批准").disabled).toBe(true);
    expect(button("拒绝").disabled).toBe(true);
    expect(assetControlClient.approveInstallation).not.toHaveBeenCalled();

    await act(async () => setTenant({
      subject: "checker@example.test",
      roles: ["viewer"],
    }));
    expect(button("批准").disabled).toBe(true);

    await act(async () => setTenant({ roles: ["asset-install-approver"] }));
    expect(button("批准").disabled).toBe(false);

    await act(async () => setConnectivity("offline", "asset-bundles-page-test"));
    expect(button("批准").disabled).toBe(true);
    await act(async () => setConnectivity("online", "asset-bundles-page-test"));
    expect(button("批准").disabled).toBe(false);
  });

  it("resolves, reconciles and creates only a draft from the selected published version", async () => {
    await renderPage();
    const buttons = () => Array.from(host.querySelectorAll("button"));
    const openBundle = buttons().find((node) => node.textContent === "查看详情") as HTMLButtonElement;
    await act(async () => openBundle.click());
    const openVersion = buttons().find((node) => node.textContent === "查看版本事实") as HTMLButtonElement;
    await act(async () => openVersion.click());
    const compositionTab = Array.from(host.querySelectorAll('[role="tab"]')).find(
      (node) => node.textContent === "组合预检与创建",
    ) as HTMLButtonElement;
    await act(async () => compositionTab.click());

    const resolve = buttons().find(
      (node) => node.textContent === "解析并生成不可变 Lock",
    ) as HTMLButtonElement;
    await act(async () => resolve.click());

    expect(assetControlClient.resolveComposition).toHaveBeenCalledTimes(1);
    expect(assetControlClient.getCompositionLock).toHaveBeenCalledWith(
      STORED_COMPOSITION_LOCK_FIXTURE.compositionId,
      STORED_COMPOSITION_LOCK_FIXTURE.revision,
    );
    expect(host.textContent).toContain("服务端 Diff（只读）");

    const displayName = host.querySelector(
      'input[aria-label="Installation display name"]',
    ) as HTMLInputElement;
    await act(async () => {
      const setValue = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      )?.set;
      setValue?.call(displayName, "Commerce draft");
      displayName.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const create = buttons().find((node) => node.textContent === "创建 Draft") as HTMLButtonElement;
    await act(async () => create.click());

    expect(assetControlClient.createInstallation).toHaveBeenCalledWith(
      {
        compositionId: STORED_COMPOSITION_LOCK_FIXTURE.compositionId,
        lockRevision: STORED_COMPOSITION_LOCK_FIXTURE.revision,
        overlayRevision: "overlay-1",
        displayName: "Commerce draft",
      },
      expect.objectContaining({ idempotencyKey: expect.any(String) }),
    );
    expect(host.textContent).not.toContain("批准安装");
    expect(host.textContent).not.toContain("Apply Installation");
  });
});
