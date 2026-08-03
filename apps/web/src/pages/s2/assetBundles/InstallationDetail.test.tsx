import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { InstallationResponse } from "../../../api/assetControl/types";
import type { AssetReadState } from "./model";
import { InstallationDetail } from "./InstallationDetail";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const HASH = `sha256:${"a".repeat(64)}` as const;
const INSTALLATION: InstallationResponse = {
  installationId: "22222222-2222-4222-8222-222222222222",
  displayName: "Commerce installation",
  state: "active",
  currentRevision: 5,
  activeRevision: 5,
  previousActiveRevision: 4,
  etagVersion: 5,
  createdAt: "2026-08-03T08:00:00Z",
  updatedAt: "2026-08-03T09:00:00Z",
  current: {
    installationId: "22222222-2222-4222-8222-222222222222",
    revision: 5,
    parentRevision: 4,
    state: "active",
    compositionId: "11111111-1111-4111-8111-111111111111",
    lockRevision: 1,
    lockHash: HASH,
    permissionDiffHash: HASH,
    migrationPlanHash: HASH,
    contributionDiffHash: HASH,
    overlayRevision: "overlay-v1",
    requestedBy: "maker@example.test",
    decisionId: "33333333-3333-4333-8333-333333333333",
    createdAt: "2026-08-03T09:00:00Z",
  },
  decision: {
    decisionId: "33333333-3333-4333-8333-333333333333",
    installationId: "22222222-2222-4222-8222-222222222222",
    submittedRevision: 2,
    decision: "approved",
    actor: "approver@example.test",
    lockHash: HASH,
    permissionDiffHash: HASH,
    migrationPlanHash: HASH,
    contributionDiffHash: HASH,
    reason: null,
    createdAt: "2026-08-03T08:30:00Z",
  },
  events: [{
    sequence: 5,
    fromRevision: 4,
    toRevision: 5,
    fromState: "applied",
    toState: "active",
    actor: "installer@example.test",
    reason: null,
    evidence: {
      type: "verification",
      evidenceRef: "evidence://verification/5",
      evidenceHash: HASH,
      status: "valid",
      observedAt: "2026-08-03T09:00:00Z",
    },
    createdAt: "2026-08-03T09:00:00Z",
  }],
};

function readState(overrides: Partial<AssetReadState<InstallationResponse>> = {}): AssetReadState<InstallationResponse> {
  return { data: INSTALLATION, status: "ready", error: null, refreshing: false, stale: false, reload: vi.fn(), ...overrides };
}

describe("InstallationDetail", () => {
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

  async function render(state = readState()) {
    await act(async () => root.render(<InstallationDetail state={state} />));
  }

  it("只展示 current、decision、pointers 与带 evidence 的事件时间线", async () => {
    await render();
    expect(host.textContent).toContain("当前 revision / ETag version5 / 5");
    expect(host.textContent).toContain("Active revision5");
    expect(host.textContent).toContain("Previous active revision4");
    expect(host.textContent).toContain("approved");
    expect(host.textContent).toContain("approver@example.test");
    expect(host.textContent).toContain("applied → active");
    expect(host.textContent).toContain("verification");
    expect(host.textContent).toContain("evidence://verification/5");
    expect(host.textContent).toContain(HASH);
  });

  it("明确声明事件不是完整 revision 快照且不存在 mutation 按钮", async () => {
    await render();
    expect(host.textContent).toContain("事件不等同于每个历史 revision 的完整快照");
    expect(host.textContent).toContain("不提供历史 revision 完整快照");
    expect(host.querySelectorAll("button")).toHaveLength(0);
  });

  it("对 idle、403、404 和 stale 使用不泄漏的只读状态", async () => {
    await render(readState({ data: null, status: "idle" }));
    expect(host.textContent).toContain("请选择一条安装记录");
    await render(readState({ status: "forbidden" }));
    expect(host.textContent).toContain("无权查看安装详情");
    expect(host.textContent).not.toContain("Commerce installation");
    await render(readState({ status: "not_visible_or_missing" }));
    expect(host.textContent).toContain("安装不可见或不存在");
    expect(host.textContent).toContain("不区分不存在与标记不可见");
    expect(host.textContent).not.toContain("Commerce installation");
    await render(readState({ stale: true }));
    expect(host.textContent).toContain("当前详情是旧数据");
  });
});
