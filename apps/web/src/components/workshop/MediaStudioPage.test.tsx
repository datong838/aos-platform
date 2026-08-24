import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MediaStudioViewResponse } from "../../api/ecommerceWorkshop";
import { MediaStudioPage } from "./MediaStudioPage";

const response = (): MediaStudioViewResponse => ({ schemaVersion: "aos.ecommerce-workshop.media-studio-view/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-24T08:00:00Z", dataCutoff: "2026-08-24T08:00:00Z", readiness: "degraded", slices: ["context", "execution", "delivery"].map((sliceId) => ({ sliceId: sliceId as "context" | "execution" | "delivery", status: "blocked", dataCutoff: "2026-08-24T08:00:00Z", readinessAxes: ["module", "capability", "assignee", "provider", "budget", "publication"].map((axis) => ({ axis: axis as "module", status: "target", exactRef: null, targetContractRef: `ADR-86#${axis}`, gaps: ["missing authority"], blockers: [{ code: "MEDIA_AUTHORITY_NOT_AVAILABLE", dependency: axis, requiredAction: "attach exact ref" }] })), authorityRefs: [], blockers: [{ code: `MEDIA_${sliceId.toUpperCase()}_AUTHORITY_NOT_AVAILABLE`, dependency: sliceId, requiredAction: "attach exact refs" }], countLedger: { denominator: 6, ready: 0, target: 6, blocked: 0, unknown: 0, conflict: 0, notApplicable: 0 } })), page: { limit: 100, count: 0, hasMore: false, nextCursor: null } });

describe("MediaStudioPage", () => {
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

  it("展示三切片 target 边界且没有媒体写入口", async () => {
    await act(async () => { root.render(<MediaStudioPage client={{ getMediaStudioView: vi.fn().mockResolvedValue(response()) }} />); });
    expect(host.querySelectorAll('[role="tab"]')).toHaveLength(3);
    expect(host.textContent).toContain("target ≠ achieved；Provider submitted ≠ delivered；published、settled 与 effect-reviewed 分轴。");
    expect(host.textContent).not.toMatch(/开始|发布|取消|批准|结算|对账/);
  });

  it("切换 Tab 不制造业务事实", async () => {
    await act(async () => { root.render(<MediaStudioPage client={{ getMediaStudioView: vi.fn().mockResolvedValue(response()) }} />); });
    const tab = Array.from(host.querySelectorAll<HTMLButtonElement>('[role="tab"]')).find((item) => item.textContent?.includes("职责与执行"));
    expect(tab).toBeTruthy();
    act(() => tab?.click());
    expect(host.querySelector('[role="tabpanel"]')?.textContent).toContain("当前没有可挂接的媒体 authority");
  });
});
