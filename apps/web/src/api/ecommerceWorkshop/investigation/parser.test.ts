import { describe, expect, it } from "vitest";

import {
  parseBusinessInvestigationSharedEnvelope,
  parseDataFulfillmentReceipt,
  parseDataRequirement,
  parseAdaptiveProfile,
  parsePlatformObservation,
  parseSemanticHydrationReceipt,
  parseSourceMapping,
} from "./parser";

const hash = `sha256:${"a".repeat(64)}`;
const tenant = { orgId: "org-org", projectId: "dev-project" };
const now = "2026-08-26T03:00:00Z";
const ref = (resourceType: string, resourceId: string, receiptId?: string) => ({
  resourceType, resourceId, revision: 1, contentHash: hash, ...(receiptId ? { receiptId } : {}),
});

const envelope = () => {
  const channelRef = ref("ChannelRevision", "channel-niushop");
  return {
    schemaVersion: "aos.business-investigation.shared/v1",
    tenant,
    channel: { channelId: "channel-niushop", platform: "niushop", displayName: "栖月汇微商城", channelRef },
    businessEntity: { businessEntityId: "shop-qyh", entityType: "shop", displayName: "栖月汇", channelRef },
    caseRef: ref("BusinessInvestigationCaseRevision", "case-1"),
    runRef: ref("BusinessInvestigationRun", "run-1"),
    readiness: {
      status: "ready",
      sourceReadinessRef: ref("SourceReadinessEnvelope", "readiness-1", "receipt-ready-1"),
      coverage: { required: 3, fulfilled: 3, unknown: 0 },
      freshness: { status: "fresh", dataCutoff: now, expiresAt: "2026-08-26T04:00:00Z" },
      blockers: [],
    },
    artifactRefs: [ref("BusinessDossierRevision", "dossier-1"), ref("InsightRevision", "insight-1")],
  };
};

describe("business investigation shared parser", () => {
  it("接受 tenant-bound exact 共享信封", () => {
    expect(parseBusinessInvestigationSharedEnvelope(envelope())).toMatchObject({
      tenant, readiness: { status: "ready" }, caseRef: { contentHash: hash },
    });
  });

  it("拒绝 extra、坏 hash、未知枚举和伪 ready", () => {
    expect(() => parseBusinessInvestigationSharedEnvelope({ ...envelope(), rawPayload: { mobile: "masked" } })).toThrow(/字段/);
    expect(() => parseBusinessInvestigationSharedEnvelope({ ...envelope(), caseRef: { ...envelope().caseRef, contentHash: "a".repeat(64) } })).toThrow(/SHA-256/);
    expect(() => parseBusinessInvestigationSharedEnvelope({ ...envelope(), readiness: { ...envelope().readiness, status: "mystery" } })).toThrow(/status/);
    expect(() => parseBusinessInvestigationSharedEnvelope({ ...envelope(), readiness: { ...envelope().readiness, coverage: { required: 3, fulfilled: 2, unknown: 1 } } })).toThrow(/伪 ready/);
  });

  it("严格解析 Data、Observation 与 Hydration 合同且保留 unknown", () => {
    expect(parseDataRequirement({ schemaVersion: "aos.data-requirement/v1", tenant, requirementId: "requirement-1", caseRef: ref("BusinessInvestigationCaseRevision", "case-1"), runRef: ref("BusinessInvestigationRun", "run-1"), purpose: "经营画像缺口", factTypes: ["Order"], status: "requested", requestedAt: now, blockers: [] }).status).toBe("requested");
    expect(parseDataFulfillmentReceipt({ schemaVersion: "aos.data-fulfillment-receipt/v1", tenant, fulfillmentId: "fulfillment-1", requirementRef: ref("DataRequirementRevision", "requirement-1"), status: "unknown", artifactRefs: [], fulfilledAt: now, blockers: [{ code: "SOURCE_READINESS_STALE", severity: "blocking", dependency: "P01", requiredAction: "等待新鲜履行" }] }).status).toBe("unknown");
    expect(parsePlatformObservation({ schemaVersion: "aos.platform-observation/v1", tenant, observationId: "observation-1", status: "blocked", observedAt: now, sourceRef: ref("PlatformSourceRevision", "source-1"), evidenceRefs: [], blockers: [{ code: "PLATFORM_PERMISSION_REQUIRED", severity: "blocking", dependency: "platform", requiredAction: "补齐只读权限" }] }).status).toBe("blocked");
    expect(parseSemanticHydrationReceipt({ schemaVersion: "aos.semantic-hydration-receipt/v1", tenant, hydrationId: "hydration-1", status: "unknown", observationRef: ref("PlatformObservation", "observation-1"), mappingRef: ref("SourceMappingRevision", "mapping-1"), outputRefs: [], hydratedAt: now, blockers: [{ code: "MAPPING_CONFLICT", severity: "blocking", dependency: "mapping", requiredAction: "人工确认映射" }] }).outputRefs).toEqual([]);
  });

  it("严格解析 SourceMapping 与 AdaptiveProfile 的 owner exact refs", () => {
    expect(parseSourceMapping({ schemaVersion: "aos.source-mapping/v1", tenant, mappingId: "mapping-1", observationRef: ref("PlatformObservation", "observation-1"), sourceField: "order.pay_amount", canonicalField: "Order.paidAmount", confidence: 0.93, confirmedBy: null, blockers: [] }).confidence).toBe(0.93);
    expect(parseAdaptiveProfile({ schemaVersion: "aos.adaptive-profile/v1", tenant, profileId: "profile-1", sourceRef: ref("PlatformSourceRevision", "source-1"), hypothesisRefs: [ref("SemanticHypothesisRevision", "hypothesis-1")], coverage: { required: 2, fulfilled: 1, unknown: 1 }, blockers: [{ code: "FIELD_MAPPING_UNKNOWN", severity: "warning", dependency: "order.discount", requiredAction: "人工确认字段语义" }] }).coverage.unknown).toBe(1);
    expect(() => parseAdaptiveProfile({ schemaVersion: "aos.adaptive-profile/v1", tenant, profileId: "profile-1", sourceRef: ref("PlatformObservation", "observation-1"), hypothesisRefs: [], coverage: { required: 0, fulfilled: 0, unknown: 0 }, blockers: [] })).toThrow(/PlatformSourceRevision/);
  });
});
