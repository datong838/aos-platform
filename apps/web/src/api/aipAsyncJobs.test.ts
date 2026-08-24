import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGetAuthoritative } from "./client";
import { listAsyncJobs, parseAsyncJobProjection } from "./aipAsyncJobs";

vi.mock("./client", () => ({ apiGetAuthoritative: vi.fn() }));
vi.mock("./tenant", () => ({ getTenant: () => ({ orgId: "org-org", projectId: "dev-project" }) }));

const ref = { resourceType: "aip.receipt", resourceId: "receipt-1", revision: "1", authority: "aos.research_job" };
const item = {
  jobRef: { authority: "aos.research_job", authorityType: "research_job", jobId: "job-1", version: "2" },
  taskRef: null, subjectRefs: [], status: "running", displayStatus: "partial",
  progress: { state: "partial", completedUnits: null, totalUnits: null }, partialRefs: [ref],
  cancelability: "cancelable", resumability: "unsupported", reconcileRequired: false, cancelRequested: false,
  checkpointRef: null, receiptRefs: [ref], lineageRef: "aip.lineage/l-1@1",
  startedAt: "2026-08-25T01:00:00Z", updatedAt: "2026-08-25T01:01:00Z", deadline: null, nextPollAt: null,
  owner: "tester", blockedReasons: ["research_job_not_resumable"],
  permissions: { canCancel: true, canRetry: false, canReconcile: false },
};
const sample = { tenant: { orgId: "org-org", projectId: "dev-project" }, items: [item], count: 1 };

describe("AsyncJobProjection strict SDK", () => {
  beforeEach(() => vi.clearAllMocks());
  it("接受三 authority 共享字段且保留原 authority", () => {
    const parsed = parseAsyncJobProjection(sample);
    expect(parsed.items[0]?.jobRef.authority).toBe("aos.research_job");
    expect(parsed.items[0]?.displayStatus).toBe("partial");
  });
  it("拒绝额外字段、未知 authority 和数量漂移", () => {
    expect(() => parseAsyncJobProjection({ ...sample, unexpected: true })).toThrow(/字段集/);
    expect(() => parseAsyncJobProjection({ ...sample, items: [{ ...item, jobRef: { ...item.jobRef, authorityType: "fourth_authority" } }] })).toThrow(/authorityType/);
    expect(() => parseAsyncJobProjection({ ...sample, count: 2 })).toThrow(/count/);
  });
  it("使用 authority-aware GET 并拒绝跨租户响应", async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValue(sample);
    await expect(listAsyncJobs()).resolves.toMatchObject({ count: 1 });
    expect(apiGetAuthoritative).toHaveBeenCalledWith("/v1/aip/async-jobs?limit=50");
    vi.mocked(apiGetAuthoritative).mockResolvedValue({ ...sample, tenant: { orgId: "other", projectId: "dev-project" } });
    await expect(listAsyncJobs()).rejects.toThrow(/租户/);
  });
});
