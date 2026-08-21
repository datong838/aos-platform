import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EcommerceWorkshopClientError, type SourceReadinessEnvelope } from "../../api/ecommerceWorkshop";
import { setTenant } from "../../api/tenant";
import { SourceReadinessPanel } from "./SourceReadinessPanel";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const pipelines = ["P01-shop-qyh", "P02-product-qyh", "P03-product-sku-qyh", "P04-category-qyh", "P05-order-qyh", "P06-order-line-qyh", "P07-shipment-qyh", "P08-customer-lite-qyh", "P09-weapp-qyh", "P10-system-config-qyh", "P11-product-review-qyh", "P12-payment-qyh"];
const checkedAt = "2026-08-21T14:00:00Z";
const blockers = ["FRESHNESS_POLICY_REF_MISSING", "QUALITY_POLICY_REF_MISSING", "QUERY_CAPABILITY_REF_MISSING", "RECONCILIATION_POLICY_REF_MISSING", "SOURCE_CONFIG_EXACT_REF_MISSING"];

function envelope(orgId = "org-org"): SourceReadinessEnvelope {
  return {
    schemaVersion: "aos.source-readiness/v1", tenant: { orgId, projectId: "dev-project" }, checkedAt, cutoffAt: checkedAt, status: "blocked", receiptRef: null,
    sources: pipelines.map((pipelineId, index) => ({ schemaVersion: "aos.source-readiness/v1", tenant: { orgId, projectId: "dev-project" }, sourceId: "niushop-qyh", pipelineId, objectType: "Object", status: "blocked", checkedAt, observedAt: checkedAt, sourceEventAt: null, projectedAt: checkedAt, dataCutoff: checkedAt, freshnessExpiresAt: null, sourceConfigRef: null, mappingRef: null, schemaRef: null, maskingPolicyRef: null, freshnessPolicyRef: null, qualityPolicyRef: null, reconciliationPolicyRef: null, queryCapabilityRef: null, latestRun: { runId: "run-1", status: "succeeded", scheduledFor: checkedAt, startedAt: checkedAt, finishedAt: checkedAt, rowsWritten: 1, errorCode: null }, counts: { sourceTotal: index === 0 ? null : 1, sourceActive: null, sourceDeleted: null, projectionTotal: index === 0 ? null : 1, unexplainedDelta: null }, quality: { status: "unknown", ruleRef: null, summary: null }, reconciliation: { status: "unknown", ruleRef: null, summary: null }, reasons: blockers, blockers })),
  };
}

function clientError(status: number): EcommerceWorkshopClientError {
  return new EcommerceWorkshopClientError("failed", { status, operationId: "ecommerceWorkshopSourceReadinessGet", body: { code: status === 403 ? "FORBIDDEN" : "FAILED", message: "failed", details: null, traceId: "trace" } });
}

describe("SourceReadinessPanel", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { sessionStorage.clear(); setTenant({ orgId: "org-org", projectId: "dev-project", workspaceName: "real" }); host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("展示 canonical 12 源 blocked、五项 blocker 与未知 count", async () => {
    const client = { getSourceReadiness: vi.fn().mockResolvedValue(envelope()) };
    await act(async () => root.render(<SourceReadinessPanel client={client} />));
    await act(async () => undefined);
    expect(host.querySelectorAll("tbody tr")).toHaveLength(12);
    expect(host.textContent).toContain("blocked");
    expect(host.textContent).toContain("SOURCE_CONFIG_EXACT_REF_MISSING");
    expect(host.textContent).toContain("未知 / 未知");
    expect(client.getSourceReadiness).toHaveBeenCalledTimes(1);
  });

  it("403 与 tenant mismatch 都失败关闭且不渲染源行", async () => {
    const forbidden = { getSourceReadiness: vi.fn().mockRejectedValue(clientError(403)) };
    await act(async () => root.render(<SourceReadinessPanel client={forbidden} />));
    await act(async () => undefined);
    expect(host.textContent).toContain("没有访问权限");
    expect(host.querySelector("tbody")).toBeNull();
    await act(async () => root.render(<SourceReadinessPanel key="mismatch" client={{ getSourceReadiness: vi.fn().mockResolvedValue(envelope("dev-org")) }} />));
    await act(async () => undefined);
    expect(host.textContent).toContain("读取失败");
    expect(host.querySelector("tbody")).toBeNull();
  });

  it("失败后只在显式点击时重读", async () => {
    const client = { getSourceReadiness: vi.fn().mockRejectedValueOnce(clientError(500)).mockResolvedValueOnce(envelope()) };
    await act(async () => root.render(<SourceReadinessPanel client={client} />));
    await act(async () => undefined);
    expect(host.textContent).toContain("读取失败");
    await act(async () => host.querySelector<HTMLButtonElement>("button")?.click());
    await act(async () => undefined);
    expect(host.querySelectorAll("tbody tr")).toHaveLength(12);
    expect(client.getSourceReadiness).toHaveBeenCalledTimes(2);
  });
});
