import { describe, expect, it } from "vitest";
import { buildGovernedQuery } from "./AipAnalystPage";

const exact = { resourceType: "Task", resourceId: "task-1", revision: "1", authority: "aip-task" };

describe("AipAnalystPage governed query", () => {
  it("builds semantic query without SQL or client tenant", () => {
    const query = buildGovernedQuery({ kind: "semantic", objectType: "Order", prompt: "", cutoffAt: "2026-08-16T00:00:00Z", taskRef: null, skillRef: null, metricRef: null });
    expect(query).toEqual(expect.objectContaining({ kind: "semantic", objectType: "Order" }));
    expect(JSON.stringify(query)).not.toMatch(/sql|orgId|projectId|Northampton/i);
  });

  it("fails closed when knowledge or metric exact refs are absent", () => {
    expect(buildGovernedQuery({ kind: "knowledge", objectType: "", prompt: "核查", cutoffAt: "2026-08-16T00:00:00Z", taskRef: null, skillRef: null, metricRef: null })).toBeNull();
    expect(buildGovernedQuery({ kind: "metric", objectType: "", prompt: "", cutoffAt: "2026-08-16T00:00:00Z", taskRef: null, skillRef: null, metricRef: null })).toBeNull();
    expect(exact.revision).toBe("1");
  });

  it("builds knowledge and metric queries only from exact upstream refs", () => {
    expect(buildGovernedQuery({ kind: "knowledge", objectType: "", prompt: "核查订单风险", cutoffAt: "2026-08-16T00:00:00Z", taskRef: exact, skillRef: { ...exact, resourceType: "Skill", resourceId: "skill-1" }, metricRef: null })).toEqual(expect.objectContaining({ kind: "knowledge", taskRef: exact }));
    expect(buildGovernedQuery({ kind: "metric", objectType: "", prompt: "", cutoffAt: "2026-08-16T00:00:00Z", taskRef: null, skillRef: null, metricRef: { ...exact, resourceType: "Metric", resourceId: "gmv" } })).toEqual(expect.objectContaining({ kind: "metric", dimensions: [] }));
  });
});
