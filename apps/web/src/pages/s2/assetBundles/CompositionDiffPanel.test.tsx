import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import type { StoredCompositionLock } from "../../../api/assetControl/types";
import { CompositionDiffPanel } from "./CompositionDiffPanel";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const HASH = `sha256:${"c".repeat(64)}` as const;
const EMPTY = { roles: [], markings: [], dataScopes: [], actionTypes: [] };
const TARGET = { roles: ["operator"], markings: ["public"], dataScopes: ["orders:read"], actionTypes: ["Order.review"] };
const BEFORE = { publisher: "aos", id: "commerce", version: "1.0.0", planRef: "migration://v1", downgradePolicy: "retain-canonical" as const };
const AFTER = { ...BEFORE, version: "1.1.0", planRef: "migration://v2" };
const API = { publisher: "aos", id: "commerce", version: "1.1.0", claim: { kind: "api" as const, method: "GET", path: "/v1/orders", operationId: "list_orders", mode: "exclusive" as const } };
const NAV = { publisher: "aos", id: "commerce", version: "1.1.0", claim: { kind: "navigation" as const, route: "/orders", mode: "shared" as const } };
const UI = { publisher: "aos", id: "commerce", version: "1.1.0", claim: { kind: "ui" as const, slot: "workspace", id: "orders", mode: "shared" as const } };
const LOCK = {
  compositionId: "11111111-1111-4111-8111-111111111111", revision: 1,
  payload: {
    lockSchemaVersion: "aos.dev/composition-lock/v1alpha1", resolverVersion: "aos-resolver/1.0.0",
    request: { requested: [], platformApiVersion: "1.0.0", platformRelease: "2026.08", environment: "dev" }, registrySnapshotHash: HASH,
    resolved: [], edges: [], capabilityProviders: [],
    permissionDiff: { baseline: EMPTY, target: TARGET, added: TARGET, removed: EMPTY, unchanged: EMPTY },
    migrationPlan: { baseline: [BEFORE], target: [AFTER], added: [], removed: [], changed: [{ publisher: "aos", id: "commerce", before: BEFORE, after: AFTER }] },
    contributionDiff: { baseline: [API], target: [API, NAV, UI], added: [NAV, UI], removed: [], unchanged: [API] }, currentInstallationRef: null,
  }, lockHash: HASH, permissionDiffHash: HASH, migrationPlanHash: HASH, contributionDiffHash: HASH, createdAt: "2026-08-03T08:00:00Z",
} satisfies StoredCompositionLock;

describe("CompositionDiffPanel", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("展示 Permission 五组与服务端 hash，不提供可编辑 hash", async () => {
    await act(async () => root.render(<CompositionDiffPanel lock={LOCK} />));
    expect(host.textContent).toContain("Permission Diff");
    for (const group of ["baseline", "target", "added", "removed", "unchanged"]) expect(host.textContent).toContain(group);
    expect(host.textContent).toContain("orders:read");
    expect(host.textContent).toContain("Order.review");
    expect(host.textContent?.match(new RegExp(HASH, "g"))?.length).toBeGreaterThanOrEqual(3);
    expect(host.querySelectorAll("input")).toHaveLength(0);
  });

  it("展示 migration before/after 与 contribution 三种 claim", async () => {
    await act(async () => root.render(<CompositionDiffPanel lock={LOCK} />));
    expect(host.textContent).toContain("before:");
    expect(host.textContent).toContain("aos/commerce@1.0.0");
    expect(host.textContent).toContain("migration://v1");
    expect(host.textContent).toContain("after:");
    expect(host.textContent).toContain("aos/commerce@1.1.0");
    expect(host.textContent).toContain("migration://v2");
    expect(host.textContent).toContain("api · GET /v1/orders · list_orders · exclusive");
    expect(host.textContent).toContain("navigation · /orders · shared");
    expect(host.textContent).toContain("ui · workspace/orders · shared");
  });
});
