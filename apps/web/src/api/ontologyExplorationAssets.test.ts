import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiGet, apiPost } from "./client";
import { createExploration, createObjectSet } from "./ontologyExplorationAssets";

vi.mock("./client", () => ({ apiGet: vi.fn(), apiPost: vi.fn() }));

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
});
