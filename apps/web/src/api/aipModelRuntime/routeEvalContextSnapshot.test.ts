import { describe, expect, it } from "vitest";

import type { EvalRunAuthority } from "../aipEvidence";
import type { ModelEvalCandidate } from "./contracts";
import { parseRouteEvalContextSnapshot } from "./routeEvalContextSnapshot";

const candidate: ModelEvalCandidate = {
  sourceRef: { assetType: "ModelRouteRevision", assetId: "route-1", revision: 8, contentHash: "a".repeat(64) },
  targetRef: { assetType: "ModelRouteRevision", assetId: "route-1", revision: 9, contentHash: "b".repeat(64) },
  expectedHeadVersion: 8,
  sourceLifecycle: "draft",
  executionAllowed: false,
};

const run: EvalRunAuthority = {
  tenant: { orgId: "org-org", projectId: "dev-project" }, runId: "run-1",
  suiteRef: { assetType: "eval_suite", assetId: "suite-1", revision: "2", contentHash: "c".repeat(64) },
  target: { assetType: "model_route", assetId: "route-1", revision: "9", contentHash: "b".repeat(64) },
  dataset: { datasetId: "dataset-1", revision: 3, contentHash: "d".repeat(64), sourceHash: "e".repeat(64), redactionPolicy: { assetType: "policy", assetId: "redact-1", revision: "1", contentHash: "f".repeat(64) } },
  judge: { judgeId: "judge-1", revision: 4, contentHash: "1".repeat(64), modelRoute: { assetType: "registered_model", assetId: "judge-model", revision: "1", contentHash: "2".repeat(64) } },
  evalContractRef: { resourceType: "EvalContractRevision", resourceId: "contract-1", revision: 5, contentHash: "3".repeat(64) },
  status: "running", idempotencyKey: "once", createdBy: "user", createdAt: "2026-10-31T08:00:00Z", startedAt: "2026-10-31T08:01:00Z", finishedAt: null, version: 6,
};

const snapshot = {
  schemaVersion: "aos.model-route-eval-context/v1",
  subject: { schemaVersion: "aos.model-route-eval-subject-binding/v1", tenant: run.tenant, candidate, source: {}, models: [], runtimePolicy: {}, executionAllowed: false },
  run,
  suite: { suiteId: run.suiteRef.assetId, revision: Number(run.suiteRef.revision), contentHash: run.suiteRef.contentHash, target: run.target, dataset: run.dataset, judge: run.judge },
  dataset: run.dataset,
  contract: { tenant: run.tenant, contractId: run.evalContractRef!.resourceId, revision: run.evalContractRef!.revision, version: 2, contentHash: run.evalContractRef!.contentHash, lifecycle: "frozen", readiness: "ready", blockers: [], suiteRef: { resourceType: "EvalSuiteRevision", resourceId: run.suiteRef.assetId, revision: Number(run.suiteRef.revision), contentHash: run.suiteRef.contentHash } },
  snapshotReadAt: "2026-10-31T08:02:00+00:00",
  executionAllowed: false,
};

describe("路由 Eval 只读上下文 Snapshot", () => {
  it("严格对齐当前候选、Run、Suite、Dataset 与 frozen-ready Contract", () => {
    expect(parseRouteEvalContextSnapshot(snapshot, candidate, run)).toEqual({
      snapshotReadAt: snapshot.snapshotReadAt,
      runId: "run-1", runVersion: 6, runStatus: "running",
      suiteId: "suite-1", suiteRevision: 2,
      datasetId: "dataset-1", datasetRevision: 3,
      judgeId: "judge-1", judgeRevision: 4,
      contractId: "contract-1", contractRevision: 5,
      executionAllowed: false,
    });
  });

  it.each([
    ["可执行标志", { ...snapshot, executionAllowed: true }],
    ["外租户", { ...snapshot, subject: { ...snapshot.subject, tenant: { orgId: "dev-org", projectId: "dev-project" } } }],
    ["候选漂移", { ...snapshot, subject: { ...snapshot.subject, candidate: { ...candidate, expectedHeadVersion: 9 } } }],
    ["Run 版本漂移", { ...snapshot, run: { ...run, version: 7 } }],
    ["Suite 漂移", { ...snapshot, suite: { ...snapshot.suite, contentHash: "9".repeat(64) } }],
    ["Dataset 漂移", { ...snapshot, dataset: { ...snapshot.dataset, sourceHash: "9".repeat(64) } }],
    ["Contract 非冻结", { ...snapshot, contract: { ...snapshot.contract, lifecycle: "draft" } }],
    ["Contract 有阻断", { ...snapshot, contract: { ...snapshot.contract, blockers: [{ code: "missing" }] } }],
    ["快照时间无时区", { ...snapshot, snapshotReadAt: "2026-10-31T08:02:00" }],
  ])("%s 时拒绝整个回包", (_label, malformed) => {
    expect(() => parseRouteEvalContextSnapshot(malformed, candidate, run)).toThrow();
  });
});
