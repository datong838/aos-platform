import { beforeEach, describe, expect, it, vi } from "vitest";
import { setConnectivity } from "./offlineStore";
import {
  enqueueOfflineWrite,
  listOfflineQueue,
  clearAllOfflineQueues,
} from "./offlineQueue";
import {
  saveOfflineSnapshot,
  readOfflineSnapshot,
  clearAllOfflineSnapshots,
} from "./offlineSnapshot";
import { setTenant, DEFAULT_TENANT } from "../api/tenant";
import { clearWorkspaceLocalCache } from "./workspaceCache";
import { OfflineQueuedError } from "./offlineQueuedError";

describe("TWC.8 offline queue & snapshot", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    setTenant({ ...DEFAULT_TENANT });
    setConnectivity("online", "test");
    clearAllOfflineQueues();
    clearAllOfflineSnapshots();
  });

  it("enqueues write when offline via client guard", async () => {
    setConnectivity("offline", "test");
    const { apiPost } = await import("../api/client");
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    await expect(apiPost("/v1/demo", { a: 1 })).rejects.toBeInstanceOf(
      OfflineQueuedError,
    );
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(listOfflineQueue()).toHaveLength(1);
    expect(listOfflineQueue()[0].path).toBe("/v1/demo");
    fetchSpy.mockRestore();
  });

  it("isolates queue by workspace", () => {
    setConnectivity("offline", "test");
    enqueueOfflineWrite({ method: "POST", path: "/v1/a", body: {} });
    expect(listOfflineQueue()).toHaveLength(1);
    setTenant({
      orgId: "dev-org",
      projectId: "prj-ops",
      workspaceName: "生产运营工作区",
    });
    expect(listOfflineQueue()).toHaveLength(0);
    enqueueOfflineWrite({ method: "PUT", path: "/v1/b", body: {} });
    expect(listOfflineQueue()).toHaveLength(1);
    expect(listOfflineQueue()[0].path).toBe("/v1/b");
  });

  it("snapshot hit when offline", async () => {
    saveOfflineSnapshot("/v1/modules", { items: [1] });
    setConnectivity("offline", "test");
    const { apiGet } = await import("../api/client");
    const data = await apiGet<{ items: number[] }>("/v1/modules");
    expect(data.items).toEqual([1]);
    expect(readOfflineSnapshot("/v1/modules")).toEqual({ items: [1] });
  });

  it("workspace switch clears offline keys", () => {
    enqueueOfflineWrite({ method: "POST", path: "/v1/x", body: {} });
    saveOfflineSnapshot("/v1/y", { ok: true });
    const r = clearWorkspaceLocalCache("test");
    expect(r.offlineRemoved).toBeGreaterThan(0);
    expect(listOfflineQueue()).toHaveLength(0);
    expect(readOfflineSnapshot("/v1/y")).toBeNull();
  });
});
