import { describe, expect, it } from "vitest";
import { parseEcommerceWorkshopModuleList, parseEcommerceWorkshopModuleReadiness } from "./parser";

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
