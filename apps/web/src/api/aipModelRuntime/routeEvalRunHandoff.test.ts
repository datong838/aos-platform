import { describe, expect, it } from "vitest";

import type { EvalRunAuthority } from "../aipEvidence";
import type { ModelEvalCandidate } from "./contracts";
import { inspectRouteEvalRunHandoff } from "./routeEvalRunHandoff";

const candidate: ModelEvalCandidate = {
  sourceRef: { assetType: "ModelRouteRevision", assetId: "route-1", revision: 8, contentHash: "a".repeat(64) },
  targetRef: { assetType: "ModelRouteRevision", assetId: "route-1", revision: 9, contentHash: "b".repeat(64) },
  expectedHeadVersion: 8,
  sourceLifecycle: "draft",
  executionAllowed: false,
};

const run: EvalRunAuthority = {
  tenant: { orgId: "org-org", projectId: "dev-project" },
  runId: "run-1",
  suiteRef: { assetType: "eval_suite", assetId: "suite-1", revision: "1", contentHash: "c".repeat(64) },
  target: { assetType: "model_route", assetId: "route-1", revision: "9", contentHash: "b".repeat(64) },
  dataset: {
    datasetId: "dataset-1", revision: 1, contentHash: "d".repeat(64), sourceHash: "e".repeat(64),
    redactionPolicy: { assetType: "redaction_policy", assetId: "redact-1", revision: "1", contentHash: "f".repeat(64) },
  },
  judge: {
    judgeId: "judge-1", revision: 1, contentHash: "1".repeat(64),
    modelRoute: { assetType: "registered_model", assetId: "judge-model-1", revision: "2", contentHash: "2".repeat(64) },
  },
  evalContractRef: { resourceType: "EvalContractRevision", resourceId: "contract-1", revision: 3, contentHash: "3".repeat(64) },
  status: "queued", idempotencyKey: "once", createdBy: "user", createdAt: "2026-10-31T08:00:00Z",
  startedAt: null, finishedAt: null, version: 1,
};

describe("路由候选与权威 EvalRun 只读绑定", () => {
  it("只接受栖月汇、精确目标、办理中且冻结 Contract 的运行", () => {
    expect(inspectRouteEvalRunHandoff(candidate, run)).toMatchObject({
      runId: "run-1",
      status: "queued",
      evalContractRef: { resourceId: "contract-1", revision: 3 },
      executionAllowed: false,
    });
  });

  it.each([
    ["租户漂移", { ...run, tenant: { orgId: "dev-org", projectId: "dev-project" } }],
    ["目标摘要漂移", { ...run, target: { ...run.target, contentHash: "9".repeat(64) } }],
    ["终态运行", { ...run, status: "succeeded" as const, finishedAt: "2026-10-31T08:01:00Z" }],
    ["缺少 Contract", { ...run, evalContractRef: null }],
    ["缺少裁判模型路由", { ...run, judge: { ...run.judge, modelRoute: null } }],
  ])("%s 时失败关闭", (_label, malformed) => {
    expect(() => inspectRouteEvalRunHandoff(candidate, malformed)).toThrow();
  });

  it("拒绝模型候选、非连续目标或非草稿来源", () => {
    expect(() => inspectRouteEvalRunHandoff({ ...candidate, sourceRef: { ...candidate.sourceRef, assetType: "RegisteredModelRevision" } }, run)).toThrow();
    expect(() => inspectRouteEvalRunHandoff({ ...candidate, targetRef: { ...candidate.targetRef, revision: 10 } }, run)).toThrow();
    expect(() => inspectRouteEvalRunHandoff({ ...candidate, sourceLifecycle: "validated" }, run)).toThrow();
  });
});
