import type { EvalRunAuthority } from "../aipEvidence";
import type { ModelEvalCandidate } from "./contracts";

export type MatchedRouteEvalRunHandoff = {
  runId: string;
  version: number;
  status: "queued" | "running";
  suiteRef: EvalRunAuthority["suiteRef"];
  target: EvalRunAuthority["target"];
  dataset: EvalRunAuthority["dataset"];
  judge: EvalRunAuthority["judge"];
  evalContractRef: NonNullable<EvalRunAuthority["evalContractRef"]>;
  executionAllowed: false;
};

const QYH_TENANT = { orgId: "org-org", projectId: "dev-project" } as const;

function sameTarget(candidate: ModelEvalCandidate, run: EvalRunAuthority) {
  return run.target.assetType === "model_route"
    && run.target.assetId === candidate.targetRef.assetId
    && run.target.revision === String(candidate.targetRef.revision)
    && run.target.contentHash === candidate.targetRef.contentHash;
}

export function inspectRouteEvalRunHandoff(
  candidate: ModelEvalCandidate,
  run: EvalRunAuthority,
): MatchedRouteEvalRunHandoff {
  if (candidate.executionAllowed !== false
    || candidate.sourceLifecycle !== "draft"
    || candidate.sourceRef.assetType !== "ModelRouteRevision"
    || candidate.targetRef.assetType !== "ModelRouteRevision"
    || candidate.sourceRef.assetId !== candidate.targetRef.assetId
    || candidate.targetRef.revision !== candidate.sourceRef.revision + 1) {
    throw new Error("当前候选不是不可执行的模型路由候选");
  }
  if (run.tenant.orgId !== QYH_TENANT.orgId || run.tenant.projectId !== QYH_TENANT.projectId) {
    throw new Error("EvalRun 不属于栖月汇正向租户");
  }
  if (!sameTarget(candidate, run)) throw new Error("EvalRun 目标与当前路由候选不一致");
  if (run.status !== "queued" && run.status !== "running") throw new Error("EvalRun 不是当前可办理状态");
  if (!run.evalContractRef) throw new Error("EvalRun 缺少冻结的 EvalContractRevision");
  if (!run.judge.modelRoute
    || run.judge.modelRoute.assetType !== "registered_model"
    || !/^[1-9]\d*$/.test(run.judge.modelRoute.revision)) {
    throw new Error("EvalRun 裁判缺少精确注册模型路由");
  }
  return {
    runId: run.runId,
    version: run.version,
    status: run.status,
    suiteRef: run.suiteRef,
    target: run.target,
    dataset: run.dataset,
    judge: run.judge,
    evalContractRef: run.evalContractRef,
    executionAllowed: false,
  };
}
