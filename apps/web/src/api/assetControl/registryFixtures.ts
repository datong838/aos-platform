import type {
  RegistryBundleDetail,
  RegistryBundleSummary,
  RegistryVersionDetail,
} from "./registry";

const CONTENT_HASH = `sha256:${"c".repeat(64)}`;
const ARTIFACT_HASH = `sha256:${"a".repeat(64)}`;
const EVIDENCE_HASH = `sha256:${"b".repeat(64)}`;
const EVIDENCE_REVISION = `sha256:${"e".repeat(64)}`;

// D2.6: ecommerce.core 独立 hash 占位（与 solution.example 区分，便于后续注册脚本对账）
const ECOMMERCE_CONTENT_HASH = `sha256:${"d".repeat(64)}`;
const ECOMMERCE_ARTIFACT_HASH = `sha256:${"f".repeat(64)}`;
const ECOMMERCE_EVIDENCE_HASH = `sha256:${"1".repeat(64)}`;
const ECOMMERCE_EVIDENCE_REVISION = `sha256:${"2".repeat(64)}`;

const SIGNATURE = {
  algorithm: "Ed25519" as const,
  keyId: "test-key",
  signature: "base64-signature",
  signedAt: "2026-08-03T12:00:00+00:00",
};

const VERSION_SUMMARY = {
  version: "1.0.0",
  contentHash: CONTENT_HASH,
  signature: SIGNATURE,
  status: "published" as const,
  createdBy: "publisher:test",
  createdAt: "2026-08-03T12:00:00+00:00",
  updatedAt: "2026-08-03T12:02:00+00:00",
};

export const REGISTRY_BUNDLE_LIST_FIXTURE: RegistryBundleSummary[] = [
  {
    publisher: "aos",
    bundleId: "solution.example",
    kind: "SolutionPack",
    displayName: "Example Solution",
    createdAt: "2026-08-03T12:00:00+00:00",
  },
  // D2.6: 电商核心本体包（从 bundles/domains/ecommerce-core/bundle.yaml 镜像）
  {
    publisher: "aos",
    bundleId: "domain.ecommerce.core",
    kind: "DomainPack",
    displayName: "电商核心本体包",
    createdAt: "2026-08-06T10:00:00+00:00",
  },
];

export const REGISTRY_BUNDLE_DETAIL_FIXTURE: RegistryBundleDetail = {
  ...REGISTRY_BUNDLE_LIST_FIXTURE[0],
  versions: [VERSION_SUMMARY],
};

/**
 * Mirrors GET /v1/asset-bundles/{bundleId}/versions/{version} after
 * RegistryService._public_version_projection has removed internal audit data.
 */
export const REGISTRY_VERSION_DETAIL_FIXTURE: RegistryVersionDetail = {
  publisher: "aos",
  bundleId: "solution.example",
  kind: "SolutionPack",
  displayName: "Example Solution",
  version: "1.0.0",
  manifest: {
    apiVersion: "aos.dev/v1alpha1",
    kind: "SolutionPack",
    metadata: {
      id: "solution.example",
      version: "1.0.0",
      displayName: "Example Solution",
      publisher: "aos",
      license: "internal",
    },
    spec: {
      platformApi: ">=1.7.0 <2.0.0",
      dependencies: [
        { id: "domain.orders", version: ">=1.0.0 <2.0.0", publisher: null },
      ],
      optionalDependencies: [
        { id: "plugin.insights", version: "^1.1.0", publisher: "partner" },
      ],
      conflicts: [],
      exports: {
        ontology: [], links: [], metrics: [], agents: [], logic: [], workshops: [],
        evals: [], policies: [], connectors: [], schemas: [], mappings: [], backend: [], ui: [],
      },
      capabilities: { provides: [], requires: [] },
      permissions: { roles: [], markings: [], dataScopes: [], actionTypes: [] },
      migrations: { plan: null, downgradePolicy: "retain-canonical" },
      preflight: null,
      regression: null,
      rollback: null,
    },
  },
  contentHash: CONTENT_HASH,
  signature: SIGNATURE,
  status: "published",
  createdBy: "publisher:test",
  createdAt: "2026-08-03T12:00:00+00:00",
  updatedAt: "2026-08-03T12:02:00+00:00",
  dependencies: [
    { publisher: null, id: "domain.orders", versionRange: ">=1.0.0 <2.0.0", optional: false, ordinal: 0 },
    { publisher: "partner", id: "plugin.insights", versionRange: "^1.1.0", optional: true, ordinal: 0 },
  ],
  artifacts: [
    {
      relativePath: "bundle.yaml",
      artifactRef: "bundle://fixtures/aos/solution.example/bundle.yaml",
      digest: ARTIFACT_HASH,
      size: 128,
      mediaType: "application/yaml",
    },
  ],
  evidence: [
    {
      type: "manifest_validation",
      artifactHash: EVIDENCE_HASH,
      status: "valid",
      observedAt: "2026-08-03T12:00:00+00:00",
      expiresAt: "2026-08-03T13:00:00+00:00",
      revokedAt: null,
    },
  ],
  lifecycleEvents: [
    {
      sequence: 1,
      fromStatus: "draft",
      toStatus: "validated",
      evidenceRevision: EVIDENCE_REVISION,
      createdAt: "2026-08-03T12:01:00+00:00",
    },
    {
      sequence: 2,
      fromStatus: "validated",
      toStatus: "published",
      evidenceRevision: EVIDENCE_REVISION,
      createdAt: "2026-08-03T12:02:00+00:00",
    },
  ],
};

/**
 * D2.6: 电商核心本体包版本详情 fixture。
 *
 * 内容镜像自 `bundles/domains/ecommerce-core/bundle.yaml`：
 * - 8 OT 数字孪生（Shop / Product / ProductSku / Category / Order / OrderLine / Shipment / CustomerLite）
 * - 7 Link 类型定义（含 placedByLite）
 * - 6 派生指标（quality_score / risk_score / overdue_hours / stock_health / order_count Δ / last_order_days Δ）
 * - PII 排除策略（ns_member 8 字段 drop）
 * - pipeline-skeleton.json（Source → TenantFilter → Normalize → Validate → Deduplicate）
 *
 * exports.ontology/schemas/policies 来自 bundle.yaml spec.exports。
 * 后续注册脚本（scripts/d2_6_register_ecommerce_bundle.py）会从此 fixture
 * 或直接从 bundles/ 目录读取真实文件清单注册到 Registry。
 */
export const REGISTRY_ECOMMERCE_VERSION_DETAIL_FIXTURE: RegistryVersionDetail = {
  publisher: "aos",
  bundleId: "domain.ecommerce.core",
  kind: "DomainPack",
  displayName: "电商核心本体包",
  version: "1.0.0",
  manifest: {
    apiVersion: "aos.dev/v1alpha1",
    kind: "DomainPack",
    metadata: {
      id: "domain.ecommerce.core",
      version: "1.0.0",
      displayName: "电商核心本体包",
      publisher: "aos",
      license: "internal",
    },
    spec: {
      platformApi: ">=1.7.0 <2.0.0",
      dependencies: [],
      optionalDependencies: [],
      conflicts: [],
      exports: {
        ontology: ["content/ontology/"],
        links: [],
        metrics: [],
        agents: [],
        logic: [],
        workshops: [],
        evals: [],
        policies: ["content/policies/"],
        connectors: [],
        schemas: ["content/schemas/"],
        mappings: [],
        backend: [],
        ui: [],
      },
      capabilities: { provides: [], requires: [] },
      permissions: { roles: [], markings: [], dataScopes: [], actionTypes: [] },
      migrations: { plan: null, downgradePolicy: "retain-canonical" },
      preflight: null,
      regression: null,
      rollback: null,
    },
  },
  contentHash: ECOMMERCE_CONTENT_HASH,
  signature: SIGNATURE,
  status: "published",
  createdBy: "publisher:test",
  createdAt: "2026-08-06T10:00:00+00:00",
  updatedAt: "2026-08-06T10:02:00+00:00",
  dependencies: [],
  artifacts: [
    {
      relativePath: "bundle.yaml",
      artifactRef: "bundle://fixtures/aos/domain.ecommerce.core/bundle.yaml",
      digest: ECOMMERCE_ARTIFACT_HASH,
      size: 256,
      mediaType: "application/yaml",
    },
    {
      relativePath: "content/ontology/object-types.json",
      artifactRef: "bundle://fixtures/aos/domain.ecommerce.core/content/ontology/object-types.json",
      digest: ECOMMERCE_ARTIFACT_HASH,
      size: 512,
      mediaType: "application/json",
    },
    {
      relativePath: "content/ontology/link-types.json",
      artifactRef: "bundle://fixtures/aos/domain.ecommerce.core/content/ontology/link-types.json",
      digest: ECOMMERCE_ARTIFACT_HASH,
      size: 384,
      mediaType: "application/json",
    },
    {
      relativePath: "content/ontology/derived-metrics.json",
      artifactRef: "bundle://fixtures/aos/domain.ecommerce.core/content/ontology/derived-metrics.json",
      digest: ECOMMERCE_ARTIFACT_HASH,
      size: 448,
      mediaType: "application/json",
    },
    {
      relativePath: "content/schemas/pipeline-skeleton.json",
      artifactRef: "bundle://fixtures/aos/domain.ecommerce.core/content/schemas/pipeline-skeleton.json",
      digest: ECOMMERCE_ARTIFACT_HASH,
      size: 320,
      mediaType: "application/json",
    },
    {
      relativePath: "content/policies/pii-exclusion.json",
      artifactRef: "bundle://fixtures/aos/domain.ecommerce.core/content/policies/pii-exclusion.json",
      digest: ECOMMERCE_ARTIFACT_HASH,
      size: 288,
      mediaType: "application/json",
    },
  ],
  evidence: [
    {
      type: "manifest_validation",
      artifactHash: ECOMMERCE_EVIDENCE_HASH,
      status: "valid",
      observedAt: "2026-08-06T10:00:00+00:00",
      expiresAt: "2026-08-06T11:00:00+00:00",
      revokedAt: null,
    },
  ],
  lifecycleEvents: [
    {
      sequence: 1,
      fromStatus: "draft",
      toStatus: "validated",
      evidenceRevision: ECOMMERCE_EVIDENCE_REVISION,
      createdAt: "2026-08-06T10:01:00+00:00",
    },
    {
      sequence: 2,
      fromStatus: "validated",
      toStatus: "published",
      evidenceRevision: ECOMMERCE_EVIDENCE_REVISION,
      createdAt: "2026-08-06T10:02:00+00:00",
    },
  ],
};
