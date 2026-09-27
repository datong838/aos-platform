import { afterEach, describe, expect, it, vi } from "vitest";
import * as offlineQueue from "../lib/offlineQueue";
import { apiGetAuthoritative, apiPostImmediate, apiPostUnqueued, formatNetworkError } from "./client";
import { setConnectivity } from "../lib/offlineStore";

describe("api client network errors", () => {
  afterEach(() => setConnectivity("unknown", "test-reset"));

  it("rewrites Failed to fetch", () => {
    const err = formatNetworkError(new Error("Failed to fetch"), "GET", "/v1/datasets");
    expect(err.message).toMatch(/aos-api/);
    expect(err.message).toMatch(/API 已启动|网络/);
  });

  it("never serves an authoritative permission read from an offline snapshot", async () => {
    setConnectivity("offline", "test");
    await expect(apiGetAuthoritative("/v1/ontology/exploration-share-grants/ref/exploration"))
      .rejects.toMatchObject({
        body: { code: "OFFLINE_AUTHORITATIVE_READ_REQUIRED" },
      });
  });

  it("blocks immediate recovery writes while offline", async () => {
    setConnectivity("offline", "test");
    const enqueue = vi.spyOn(offlineQueue, "enqueueOfflineWrite");
    try {
      await expect(apiPostImmediate("/v1/schedules/s/runs/r/recover", { claimId: "same" }))
        .rejects.toMatchObject({ body: { code: "OFFLINE_WRITE_BLOCKED" } });
      expect(enqueue).not.toHaveBeenCalled();
    } finally { enqueue.mockRestore(); }
  });

  it("never queues a budget authority command and preserves exact headers", async () => {
    const enqueue = vi.spyOn(offlineQueue, "enqueueOfflineWrite");
    const headers = { "Idempotency-Key": "budget-one-intent", "If-Match": "0" };
    try {
      setConnectivity("offline", "test");
      await expect(apiPostUnqueued("/v1/aip/budgets", { lifecycle: "draft" }, headers))
        .rejects.toMatchObject({ body: { code: "OFFLINE_READ_ONLY" } });
      expect(enqueue).not.toHaveBeenCalled();
      setConnectivity("online", "test");
      const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ lifecycle: "draft" }) });
      vi.stubGlobal("fetch", fetchMock);
      await expect(apiPostUnqueued("/v1/aip/budgets", { lifecycle: "draft" }, headers))
        .resolves.toEqual({ lifecycle: "draft" });
      expect(fetchMock).toHaveBeenCalledTimes(1);
      expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST", headers: expect.objectContaining(headers) });
      expect(enqueue).not.toHaveBeenCalled();
    } finally { vi.unstubAllGlobals(); enqueue.mockRestore(); }
  });
});
