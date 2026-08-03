import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { normalizeAssetControlError } from "../../../api/assetControl/errors";
import type { StoredCompositionLock } from "../../../api/assetControl/types";
import type { AssetReadState } from "./model";
import { CompositionLockDetail } from "./CompositionLockDetail";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const HASH = `sha256:${"a".repeat(64)}` as const;
const EMPTY_PERMISSIONS = { roles: [], markings: [], dataScopes: [], actionTypes: [] };
const LOCK: StoredCompositionLock = {
  compositionId: "11111111-1111-4111-8111-111111111111", revision: 2,
  payload: {
    lockSchemaVersion: "aos.dev/composition-lock/v1alpha1", resolverVersion: "aos-resolver/1.0.0",
    request: { requested: [{ publisher: "aos", id: "commerce", version: "^1.0.0" }], platformApiVersion: "1.0.0", platformRelease: "2026.08", environment: "prod" },
    registrySnapshotHash: HASH, resolved: [], edges: [], capabilityProviders: [],
    permissionDiff: { baseline: EMPTY_PERMISSIONS, target: EMPTY_PERMISSIONS, added: EMPTY_PERMISSIONS, removed: EMPTY_PERMISSIONS, unchanged: EMPTY_PERMISSIONS },
    migrationPlan: { baseline: [], target: [], added: [], removed: [], changed: [] },
    contributionDiff: { baseline: [], target: [], added: [], removed: [], unchanged: [] },
    currentInstallationRef: { installationId: "22222222-2222-4222-8222-222222222222", revision: 1, lockHash: HASH, overlayRevision: "overlay-v1" },
  },
  lockHash: HASH, permissionDiffHash: HASH, migrationPlanHash: HASH, contributionDiffHash: HASH,
  createdAt: "2026-08-03T08:00:00Z",
};

function state(overrides: Partial<AssetReadState<StoredCompositionLock>> = {}): AssetReadState<StoredCompositionLock> {
  return { data: LOCK, status: "ready", error: null, refreshing: false, stale: false, reload: vi.fn(), ...overrides };
}

describe("CompositionLockDetail", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });
  async function render(value: AssetReadState<StoredCompositionLock>) { await act(async () => root.render(<CompositionLockDetail state={value} />)); }

  it("展示服务端 lock、canonical request、四 hash 和当前安装引用且 hash 不可编辑", async () => {
    await render(state());
    expect(host.textContent).toContain(LOCK.compositionId);
    expect(host.textContent).toContain("aos-resolver/1.0.0");
    expect(host.textContent).toContain("aos/commerce@^1.0.0");
    expect(host.textContent).toContain("22222222-2222-4222-8222-222222222222");
    expect(host.textContent?.match(new RegExp(HASH, "g"))?.length).toBeGreaterThanOrEqual(5);
    expect(host.querySelectorAll("input")).toHaveLength(0);
  });

  it("覆盖状态并在 403/404 时不泄漏残留 lock，error+stale 可标旧展示", async () => {
    for (const status of ["idle", "loading", "empty", "forbidden", "not_visible_or_missing"] as const) {
      await render(state({ status }));
      if (status === "forbidden" || status === "not_visible_or_missing") expect(host.textContent).not.toContain(LOCK.compositionId);
    }
    const error = normalizeAssetControlError({ status: 500, body: { code: "INTERNAL_ERROR", message: "boom", details: null, traceId: "t" } });
    await render(state({ status: "error", error, stale: true }));
    expect(host.textContent).toContain("当前 Lock 是旧数据");
    expect(host.textContent).toContain(LOCK.compositionId);
  });
});
