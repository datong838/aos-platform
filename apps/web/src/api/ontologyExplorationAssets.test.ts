import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiGet, apiGetAuthoritative, apiPost } from "./client";
import { createExploration, createObjectSet, resolveSharedExploration } from "./ontologyExplorationAssets";

vi.mock("./client", () => ({ apiGet: vi.fn(), apiGetAuthoritative: vi.fn(), apiPost: vi.fn() }));

const exploration = {
  kind: "exploration" as const,
  id: "exp-1",
  owner: "user:dev",
  revision: 1,
  payload: {
    name: "支付探索",
    objectType: "Payment",
    viewMode: "table" as const,
    visibility: "private" as const,
    query: {},
    columns: [],
    graph: {},
  },
  payloadHash: "a".repeat(64),
  archived: false,
};

const opaqueRef = "opaque_share_ref_1234567890";
const grant = {
  tenant: { orgId: "org-org", projectId: "dev-project" },
  grantId: "grant-1",
  opaqueRef,
  assetId: exploration.id,
  assetRevision: exploration.revision,
  assetPayloadHash: exploration.payloadHash,
  grantorSubject: exploration.owner,
  granteeScope: "link",
  purpose: "exploration_read",
  markings: [],
  status: "active",
  issuedAt: "2026-08-25T00:00:00Z",
  expiresAt: "2099-08-25T00:00:00Z",
  revokedAt: null,
  revokeReason: null,
  version: 1,
  blocker: null,
};

describe("O1-UX2 exploration asset client", () => {
  beforeEach(() => vi.clearAllMocks());

  it("confirms create only after a matching server reread", async () => {
    vi.mocked(apiPost).mockResolvedValue(exploration);
    vi.mocked(apiGet).mockResolvedValue(exploration);
    await expect(createExploration(exploration.payload)).resolves.toEqual(exploration);
    expect(apiPost).toHaveBeenCalledWith(
      "/v1/ontology/explorations",
      exploration.payload,
      expect.objectContaining({ "Idempotency-Key": expect.stringContaining("exploration-") }),
    );
    expect(apiGet).toHaveBeenCalledWith("/v1/ontology/explorations/exp-1");
  });

  it("rejects a mismatching reread instead of reporting false success", async () => {
    vi.mocked(apiPost).mockResolvedValue(exploration);
    vi.mocked(apiGet).mockResolvedValue({ ...exploration, payloadHash: "b".repeat(64) });
    await expect(createExploration(exploration.payload)).rejects.toThrow("重读不一致");
  });

  it("creates object sets with a server idempotency key", async () => {
    vi.mocked(apiPost).mockResolvedValue({ kind: "object_set", id: "set-1" } as never);
    await createObjectSet({
      name: "订单集",
      objectType: "Order",
      visibility: "private",
      items: [{ objectType: "Order", objectId: "niushop:1:1" }],
    });
    expect(apiPost).toHaveBeenCalledWith(
      "/v1/ontology/object-sets",
      expect.objectContaining({ objectType: "Order" }),
      expect.objectContaining({ "Idempotency-Key": expect.stringContaining("object-set-") }),
    );
  });

  it("resolves an active share only through a fresh authoritative read", async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValue({ grant, exploration });
    await expect(resolveSharedExploration(opaqueRef)).resolves.toEqual({ grant, exploration });
    expect(apiGetAuthoritative).toHaveBeenCalledWith(
      `/v1/ontology/exploration-share-grants/${opaqueRef}/exploration`,
    );
  });

  it("rejects stale, malformed, or drifted shared exploration responses", async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce({ grant: { ...grant, status: "revoked", blocker: "share_grant_revoked" }, exploration });
    await expect(resolveSharedExploration(opaqueRef)).rejects.toThrow("已失效");

    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce({ grant: { ...grant, unexpected: true }, exploration });
    await expect(resolveSharedExploration(opaqueRef)).rejects.toThrow("字段合同不一致");

    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce({ grant, exploration: { ...exploration, payloadHash: "b".repeat(64) } });
    await expect(resolveSharedExploration(opaqueRef)).rejects.toThrow("exact exploration");
  });
});
