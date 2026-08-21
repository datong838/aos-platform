import { describe, expect, it } from "vitest";
import { parseEcommerceWorkshopModuleList, parseEcommerceWorkshopModuleReadiness, parseTaskCockpitCheckpoints, parseTaskCockpitCore, parseTaskCockpitSteps } from "./parser";

const hash = (value: string) => `sha256:${value.repeat(64)}`;
const blocker = { dependencyType: "aip_feature", dependencyId: "aip.task-runtime", state: "unknown", reasonCode: "AIP_FEATURE_UNVERIFIED", recoverable: true, requiredAction: "等待 canonical reader 回读", ref: null };
const module = {
  moduleId: "ecommerce.operations", displayName: "统一运营驾驶舱", menuLabel: "统一运营驾驶舱", route: "/workshop/operations", slot: "workshop.primary.ecommerce", order: 30,
  installationRef: { installationId: "11111111-1111-4111-8111-111111111111", revision: 5, compositionId: "22222222-2222-4222-8222-222222222222", lockRevision: 1, lockHash: hash("a"), overlayRevision: "overlay-5" },
  moduleRef: { publisher: "aos", bundleId: "solution.ecommerce.operations-base", version: "1.1.0", bundleContentHash: hash("b"), moduleArtifactRef: "bundle://catalog/solutions/ecommerce-operations-base/content/workshops/ecommerce.operations.json", moduleArtifactHash: hash("c") },
  readiness: "unknown", blockers: [blocker], permissions: { roles: [], markings: [], dataScopes: ["ecommerce.workshop.read"], actionTypes: [] },
  requiredObjects: ["Order"], requiredCapabilities: ["performance.review"], requiredAipFeatures: ["aip.task-runtime"], viewRefs: [], evalPackRefs: [], productionContractRefs: [], responsibilityTemplateRefs: [], impactCalculatorRefs: [], legacyAssetRefs: [], legacyRoutes: ["/workshop/orders"], minimumRuntimeVersion: "1.7.0", lastReceiptRef: null,
};
const list = { schemaVersion: "aos.ecommerce-workshop/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-14T00:00:00Z", dataCutoff: null, items: [module], count: 1 };

describe("ecommerceWorkshop strict parser", () => {
  it("解析 exact module list/readiness 并保留 blocked 证据", () => {
    expect(parseEcommerceWorkshopModuleList(list)).toMatchObject({ count: 1, items: [{ moduleId: "ecommerce.operations", readiness: "unknown" }] });
    expect(parseEcommerceWorkshopModuleReadiness({ schemaVersion: list.schemaVersion, tenant: list.tenant, evaluatedAt: list.evaluatedAt, dataCutoff: null, item: module }).item.blockers).toHaveLength(1);
  });
  it("extra、unknown enum、hash/ref 漂移全部失败关闭", () => {
    expect(() => parseEcommerceWorkshopModuleList({ ...list, extra: true })).toThrow("字段漂移");
    expect(() => parseEcommerceWorkshopModuleList({ ...list, items: [{ ...module, readiness: "future" }] })).toThrow("未知枚举");
    expect(() => parseEcommerceWorkshopModuleList({ ...list, items: [{ ...module, moduleRef: { ...module.moduleRef, moduleArtifactHash: "bad" } }] })).toThrow("SHA-256");
    expect(() => parseEcommerceWorkshopModuleList({ ...list, items: [{ ...module, moduleRef: { ...module.moduleRef, version: "01.2.3" } }] })).toThrow("SemVer");
    expect(() => parseEcommerceWorkshopModuleList({ ...list, items: [{ ...module, minimumRuntimeVersion: "v1.7" }] })).toThrow("SemVer");
    expect(() => parseEcommerceWorkshopModuleList({ ...list, items: [{ ...module, installationRef: { ...module.installationRef, installationId: "NOT-UUID" } }] })).toThrow("UUID");
  });
  it("readiness/blocker、排序和 count 不一致失败关闭", () => {
    expect(() => parseEcommerceWorkshopModuleList({ ...list, items: [{ ...module, readiness: "available" }] })).toThrow("不一致");
    expect(() => parseEcommerceWorkshopModuleList({ ...list, count: 2 })).toThrow("count");
    expect(() => parseEcommerceWorkshopModuleList({ ...list, items: [{ ...module, requiredObjects: ["Z", "A"] }] })).toThrow("排序");
  });
});

const cockpitBase = { schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-15T10:00:00Z", stateConsistency: "current_state_per_page" };
const page = { limit: 20, count: 1, hasMore: false, nextCursor: null };
const run = { runId: "run-1", planRevisionId: "plan-1", status: "running", version: 1, startedAt: null, finishedAt: null, createdAt: "2026-08-15T09:00:00Z", updatedAt: "2026-08-15T09:01:00Z" };
const task = { taskId: "task-1", taskType: "daily", title: "每日巡检", status: "executing", priority: 50, version: 1, currentPlanRevisionId: "plan-1", createdAt: "2026-08-15T08:00:00Z", updatedAt: "2026-08-15T09:01:00Z", run };
const cockpitCore = { ...cockpitBase, taskCutoff: "2026-08-15T10:00:00Z", readiness: "degraded", blockers: [
  { code: "TASK_COCKPIT_STAGE_MAPPING_UNAVAILABLE", severity: "warning", dependency: "stage", requiredAction: "等待映射" },
  { code: "TASK_COCKPIT_RESPONSIBILITY_HANDOFF_UNAVAILABLE", severity: "warning", dependency: "responsibility", requiredAction: "等待 reader" },
  { code: "TASK_COCKPIT_BUSINESS_CONTEXT_BLOCKED", severity: "blocking", dependency: "business", requiredAction: "等待 W2-00" },
], items: [task], page };
const step = { stepRunId: "step-1", stepKey: "collect", attempt: 1, status: "running", tokenCount: 12, costAmount: "0.0100", hasInputRefs: true, hasOutputRefs: false, hasError: false, createdAt: "2026-08-15T09:00:00Z", updatedAt: "2026-08-15T09:01:00Z" };
const checkpoint = { checkpointId: "checkpoint-1", sequence: 1, schemaVersion: 1, stepKey: "collect", stateHash: "state-1", artifactCount: 0, createdAt: "2026-08-15T09:02:00Z" };
const steps = { ...cockpitBase, runId: "run-1", membershipCutoff: "2026-08-15T10:00:00Z", items: [step], page };
const checkpoints = { ...cockpitBase, runId: "run-1", membershipCutoff: "2026-08-15T10:00:00Z", items: [checkpoint], page };

describe("task cockpit strict parser", () => {
  it("保留 Task/Run/Step/Checkpoint、decimal 与 current-state 语义", () => {
    expect(parseTaskCockpitCore(cockpitCore)).toMatchObject({ readiness: "degraded", items: [{ run: { runId: "run-1" } }] });
    expect(parseTaskCockpitSteps(steps).items[0]).toMatchObject({ costAmount: "0.0100", hasInputRefs: true });
    expect(parseTaskCockpitCheckpoints(checkpoints).items[0]).toMatchObject({ checkpointId: "checkpoint-1", artifactCount: 0 });
  });
  it("拒绝 extra、未知状态、坏 decimal、重复 identity 和 count/cursor 漂移", () => {
    expect(() => parseTaskCockpitCore({ ...cockpitCore, extra: true })).toThrow("字段漂移");
    expect(() => parseTaskCockpitCore({ ...cockpitCore, items: [{ ...task, status: "future" }] })).toThrow("未知枚举");
    expect(() => parseTaskCockpitSteps({ ...steps, items: [{ ...step, costAmount: "NaN" }] })).toThrow("decimal");
    expect(() => parseTaskCockpitSteps({ ...steps, items: [step, step], page: { ...page, count: 2 } })).toThrow("identity");
    expect(() => parseTaskCockpitCheckpoints({ ...checkpoints, page: { ...page, hasMore: true } })).toThrow("cursor");
    expect(() => parseTaskCockpitCore({ ...cockpitCore, blockers: cockpitCore.blockers.slice(0, 2) })).toThrow("数量");
  });
  it("只把 canonical 200 空页识别为空", () => {
    expect(parseTaskCockpitSteps({ ...steps, items: [], page: { limit: 20, count: 0, hasMore: false, nextCursor: null } }).items).toEqual([]);
  });
});
