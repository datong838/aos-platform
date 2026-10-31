import { describe, expect, it } from "vitest";

import type { EvalRunAuthority } from "../aipEvidence";
import type { ModelEvalCandidate } from "./contracts";
import { parseRouteEvalRunOptions, routeEvalRunOptionsPath } from "./routeEvalRunOptions";

const candidate: ModelEvalCandidate = {
  sourceRef: { assetType: "ModelRouteRevision", assetId: "qyh-route", revision: 8, contentHash: "a".repeat(64) },
  targetRef: { assetType: "ModelRouteRevision", assetId: "qyh-route", revision: 9, contentHash: "b".repeat(64) },
  expectedHeadVersion: 8, sourceLifecycle: "draft", executionAllowed: false,
};

const run: EvalRunAuthority = {
  tenant: { orgId: "org-org", projectId: "dev-project" }, runId: "run-1",
  suiteRef: { assetType: "eval_suite", assetId: "suite-1", revision: "1", contentHash: "c".repeat(64) },
  target: { assetType: "model_route", assetId: "qyh-route", revision: "9", contentHash: "b".repeat(64) },
  dataset: { datasetId: "dataset-1", revision: 1, contentHash: "d".repeat(64), sourceHash: "e".repeat(64), redactionPolicy: { assetType: "policy", assetId: "redact-1", revision: "1", contentHash: "f".repeat(64) } },
  judge: { judgeId: "judge-1", revision: 1, contentHash: "1".repeat(64), modelRoute: { assetType: "registered_model", assetId: "judge-model", revision: "2", contentHash: "2".repeat(64) } },
  evalContractRef: { resourceType: "EvalContractRevision", resourceId: "contract-1", revision: 3, contentHash: "3".repeat(64) },
  status: "queued", idempotencyKey: "once", createdBy: "human", createdAt: "2026-10-31T08:00:00Z",
  startedAt: null, finishedAt: null, version: 1,
};

describe("当前路由可选 EvalRun", () => {
  it("生成完整编码的只读 GET 查询", () => {
    const path = routeEvalRunOptionsPath(candidate);
    expect(path).toContain("routeId=qyh-route");
    expect(path).toContain("sourceRevision=8");
    expect(path).toContain(`sourceHash=${"a".repeat(64)}`);
    expect(path).toContain("targetRevision=9");
    expect(path).toContain(`targetHash=${"b".repeat(64)}`);
    expect(path).toContain("expectedHeadVersion=8");
  });

  it("只接受与当前路由精确绑定的办理中权威 Run", () => {
    expect(parseRouteEvalRunOptions([run], candidate)).toEqual([run]);
    expect(parseRouteEvalRunOptions([], candidate)).toEqual([]);
  });

  it.each([
    ["目标漂移", [{ ...run, target: { ...run.target, contentHash: "9".repeat(64) } }]],
    ["终态", [{ ...run, status: "succeeded", finishedAt: "2026-10-31T08:01:00Z" }]],
    ["无 Contract", [{ ...run, evalContractRef: null }]],
    ["重复", [run, run]],
    ["无时区", [{ ...run, createdAt: "2026-10-31T08:00:00" }]],
  ])("%s 时失败关闭", (_label, value) => {
    expect(() => parseRouteEvalRunOptions(value, candidate)).toThrow();
  });
});
