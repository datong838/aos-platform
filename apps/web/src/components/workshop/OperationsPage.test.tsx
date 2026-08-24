import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationsPage } from "./OperationsPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const ids = ["orders", "orderLines", "inventory", "shipments", "payments", "aftersaleEvents", "operationCases"] as const;
const response = { schemaVersion: "aos.ecommerce-workshop.operations-view/v1" as const, tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-24T08:00:00Z", dataCutoff: "2026-08-24T08:00:00Z", readiness: "degraded" as const, slices: ids.map((sliceId, index) => ({ sliceId, status: (index === 5 ? "blocked" : "ready") as "ready" | "blocked", dataCutoff: "2026-08-24T08:00:00Z", authorityRefs: index === 5 ? [] : [{ resourceType: "ReadAuthority", resourceId: sliceId, revision: 1, contentHash: `sha256:${"a".repeat(64)}`, receiptId: "receipt-1" }], blockers: index === 5 ? [{ code: "AFTERSALE_EVENTS_READ_FAILED_CLOSED", dependency: "data.aftersale", requiredAction: "检查 canonical reader" }] : [], countLedger: { sourceTotal: index === 5 ? 0 : 1, attached: index === 5 ? 0 : 1, unmatched: 0, conflicted: 0 } })), page: { limit: 50, count: 6, hasMore: false, nextCursor: null } };

describe("OperationsPage", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); vi.restoreAllMocks(); });
  it("按视觉稿三栏呈现七切片，并把 blocked 与合格 0 区分", async () => {
    const client = { getOperationsView: vi.fn().mockResolvedValue(response) };
    await act(async () => root.render(<OperationsPage client={client} />));
    expect(host.querySelectorAll(".operations-slice-card")).toHaveLength(7);
    expect(host.textContent).toContain("统一待办 · 权威切片");
    expect(host.textContent).toContain("AFTERSALE_EVENTS_READ_FAILED_CLOSED");
    expect(host.textContent).toContain("只读分诊");
    expect(host.textContent).not.toContain("批准退款");
  });
});
