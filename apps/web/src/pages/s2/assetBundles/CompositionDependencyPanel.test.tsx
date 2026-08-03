import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import type { StoredCompositionLock } from "../../../api/assetControl/types";
import { CompositionDependencyPanel } from "./CompositionDependencyPanel";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const HASH = `sha256:${"b".repeat(64)}` as const;
const PERMISSIONS = { roles: ["reader"], markings: ["public"], dataScopes: ["orders:read"], actionTypes: [] };
const LOCK = {
  compositionId: "11111111-1111-4111-8111-111111111111", revision: 1,
  payload: {
    lockSchemaVersion: "aos.dev/composition-lock/v1alpha1", resolverVersion: "aos-resolver/1.0.0",
    request: { requested: [{ publisher: "aos", id: "commerce", version: "^1.0.0" }], platformApiVersion: "1.0.0", platformRelease: "2026.08", environment: "dev" },
    registrySnapshotHash: HASH,
    resolved: [{
      publisher: "aos", id: "commerce", version: "1.2.0", kind: "DomainPack", contentHash: HASH,
      signatureFingerprint: HASH, releaseEvidenceRevision: HASH,
      dependencies: [{ publisher: "aos", id: "orders", version: ">=1.0.0" }],
      optionalDependencies: [{ publisher: "partner", id: "insights", version: "^2.0.0" }],
      conflicts: [{ publisher: "legacy", id: "commerce", version: null }],
      capabilities: { provides: ["commerce.core"], requires: ["orders.core"] }, permissions: PERMISSIONS,
      migration: { planRef: "migration://commerce/1.2.0", downgradePolicy: "retain-canonical" },
      contributions: [{ kind: "api", method: "GET", path: "/v1/orders", operationId: "list_orders", mode: "exclusive" }],
      selectionReason: "requested",
    }],
    edges: [{ fromPublisher: "aos", fromId: "commerce", fromVersion: "1.2.0", toPublisher: "aos", toId: "orders", toVersion: "1.1.0", constraint: ">=1.0.0", optional: false }],
    capabilityProviders: [{ capability: "orders.core", publisher: "aos", id: "orders", version: "1.1.0" }],
    permissionDiff: { baseline: PERMISSIONS, target: PERMISSIONS, added: PERMISSIONS, removed: PERMISSIONS, unchanged: PERMISSIONS },
    migrationPlan: { baseline: [], target: [], added: [], removed: [], changed: [] }, contributionDiff: { baseline: [], target: [], added: [], removed: [], unchanged: [] }, currentInstallationRef: null,
  }, lockHash: HASH, permissionDiffHash: HASH, migrationPlanHash: HASH, contributionDiffHash: HASH, createdAt: "2026-08-03T08:00:00Z",
} satisfies StoredCompositionLock;

describe("CompositionDependencyPanel", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("展示 resolved、事实依赖边、providers 和贡献而不绘制推断图", async () => {
    await act(async () => root.render(<CompositionDependencyPanel lock={LOCK} />));
    expect(host.textContent).toContain("aos/commerce@1.2.0");
    expect(host.textContent).toContain("requested");
    expect(host.textContent).toContain("commerce.core");
    expect(host.textContent).toContain("partner/insights ^2.0.0");
    expect(host.textContent).toContain("legacy/commerce 任意版本");
    expect(host.textContent).toContain("GET /v1/orders · list_orders");
    expect(host.textContent).toContain("aos/orders@1.1.0");
    expect(host.textContent).toContain(">=1.0.0");
    expect(host.textContent).toContain("必需");
    expect(host.querySelector("svg")).toBeNull();
    expect(host.querySelectorAll("input")).toHaveLength(0);
  });

  it("空边和 provider 使用真实空态", async () => {
    const empty = { ...LOCK, payload: { ...LOCK.payload, edges: [], capabilityProviders: [] } };
    await act(async () => root.render(<CompositionDependencyPanel lock={empty} />));
    expect(host.textContent).toContain("无依赖边");
    expect(host.textContent).toContain("无 capability provider");
  });
});
