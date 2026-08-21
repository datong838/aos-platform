import { describe, expect, it } from "vitest";
import { parseAipOperationalProjection } from "./parser";

const H = "a".repeat(64);
const counts = { definition: 6, bound: 6, enabled: 6, runnable: 6 };
const sample = {
  tenant: { orgId: "org-org", projectId: "dev-project" },
  roles: counts,
  capabilities: { definition: 10, bound: 10, enabled: 10, runnable: 10 },
  tools: { definition: 30, bound: 12, enabled: 10, runnable: 8 },
  evalGates: { definition: 3, bound: 3, enabled: 3, runnable: 3 },
  routes: { definition: 3, bound: 3, enabled: 3, runnable: 3 },
  overallReadiness: "ready",
  blockerCodes: [],
  sources: { agentReadinessAt: "2026-08-21T01:00:00Z", modelRuntimeAt: "2026-08-21T01:00:01Z" },
  snapshotHash: H,
  generatedAt: "2026-08-21T01:00:02Z",
};

describe("AIP 跨页运行投影 parser", () => {
  it("接受严格的同租户四态投影", () => {
    expect(parseAipOperationalProjection(sample).tools.runnable).toBe(8);
  });
  it("拒绝把异步未知写成负数", () => {
    expect(() => parseAipOperationalProjection({ ...sample, roles: { ...counts, runnable: -1 } })).toThrow(/\u975e\u8d1f/);
  });
  it("拒绝非单调四态计数", () => {
    expect(() => parseAipOperationalProjection({ ...sample, tools: { definition: 2, bound: 3, enabled: 1, runnable: 1 } })).toThrow(/\u975e\u5355\u8c03/);
  });
  it("拒绝快照 hash 和阻断语义漂移", () => {
    expect(() => parseAipOperationalProjection({ ...sample, snapshotHash: "masked" })).toThrow(/SHA-256/);
    expect(() => parseAipOperationalProjection({ ...sample, overallReadiness: "blocked" })).toThrow(/\u4e0d一致/);
  });
  it("拒绝未冻结的额外字段", () => {
    expect(() => parseAipOperationalProjection({ ...sample, runnable: true })).toThrow(/\u5b57段集/);
  });
});
