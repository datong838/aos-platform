import { parseEvalRunAuthority, type EvalRunAuthority } from "../aipEvidence";
import type { ModelEvalCandidate } from "./contracts";
import { parseModelEvalCandidate } from "./parser";

export type RouteEvalContextSnapshot = {
  snapshotReadAt: string;
  runId: string;
  runVersion: number;
  runStatus: "queued" | "running";
  suiteId: string;
  suiteRevision: number;
  datasetId: string;
  datasetRevision: number;
  judgeId: string;
  judgeRevision: number;
  contractId: string;
  contractRevision: number;
  executionAllowed: false;
};

function record(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new TypeError(`${label} 格式无效`);
  return value as Record<string, unknown>;
}

function text(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new TypeError(`${label} 缺失`);
  return value;
}

function positiveInt(value: unknown, label: string): number {
  if (!Number.isSafeInteger(value) || (value as number) < 1) throw new TypeError(`${label} 无效`);
  return value as number;
}

function sha(value: unknown, label: string): string {
  const result = text(value, label).toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(result)) throw new TypeError(`${label} 不是 sha256`);
  return result;
}

function timestamp(value: unknown, label: string): string {
  const result = text(value, label);
  if (!/(?:Z|[+-]\d{2}:\d{2})$/.test(result) || !Number.isFinite(Date.parse(result))) {
    throw new TypeError(`${label} 必须是带时区时间戳`);
  }
  return result;
}

function sameRef(left: { assetType: string; assetId: string; revision: number; contentHash: string }, right: typeof left) {
  return left.assetType === right.assetType && left.assetId === right.assetId
    && left.revision === right.revision && left.contentHash === right.contentHash;
}

function sameRunRef(left: EvalRunAuthority["target"], right: EvalRunAuthority["target"]) {
  return left.assetType === right.assetType && left.assetId === right.assetId
    && left.revision === right.revision && left.contentHash === right.contentHash;
}

function sameDataset(left: EvalRunAuthority["dataset"], right: EvalRunAuthority["dataset"]) {
  return left.datasetId === right.datasetId && left.revision === right.revision
    && left.contentHash === right.contentHash && left.sourceHash === right.sourceHash
    && sameRunRef(left.redactionPolicy, right.redactionPolicy);
}

function sameJudge(left: EvalRunAuthority["judge"], right: EvalRunAuthority["judge"]) {
  const modelsMatch = left.modelRoute === null && right.modelRoute === null
    || Boolean(left.modelRoute && right.modelRoute && sameRunRef(left.modelRoute, right.modelRoute));
  return left.judgeId === right.judgeId && left.revision === right.revision
    && left.contentHash === right.contentHash && modelsMatch;
}

export function parseRouteEvalContextSnapshot(
  value: unknown,
  candidate: ModelEvalCandidate,
  expectedRun: EvalRunAuthority,
): RouteEvalContextSnapshot {
  const root = record(value, "RouteEvalContextSnapshot");
  if (root.schemaVersion !== "aos.model-route-eval-context/v1" || root.executionAllowed !== false) {
    throw new TypeError("路由 Eval 上下文不得授予执行权");
  }
  const subject = record(root.subject, "RouteEvalContextSnapshot.subject");
  const tenant = record(subject.tenant, "RouteEvalContextSnapshot.subject.tenant");
  if (subject.schemaVersion !== "aos.model-route-eval-subject-binding/v1"
    || subject.executionAllowed !== false
    || tenant.orgId !== "org-org" || tenant.projectId !== "dev-project") {
    throw new TypeError("路由 Eval subject 租户或只读边界漂移");
  }
  const actualCandidate = parseModelEvalCandidate(subject.candidate);
  if (!sameRef(actualCandidate.sourceRef, candidate.sourceRef)
    || !sameRef(actualCandidate.targetRef, candidate.targetRef)
    || actualCandidate.expectedHeadVersion !== candidate.expectedHeadVersion
    || actualCandidate.sourceLifecycle !== candidate.sourceLifecycle
    || actualCandidate.executionAllowed !== false) {
    throw new TypeError("路由 Eval subject candidate 漂移");
  }
  const run = parseEvalRunAuthority(root.run, expectedRun.runId);
  if (run.tenant.orgId !== "org-org" || run.tenant.projectId !== "dev-project"
    || run.version !== expectedRun.version || run.status !== expectedRun.status
    || (run.status !== "queued" && run.status !== "running")
    || !sameRunRef(run.target, expectedRun.target)
    || run.suiteRef.assetId !== expectedRun.suiteRef.assetId
    || run.suiteRef.revision !== expectedRun.suiteRef.revision
    || run.suiteRef.contentHash !== expectedRun.suiteRef.contentHash
    || !sameDataset(run.dataset, expectedRun.dataset) || !sameJudge(run.judge, expectedRun.judge)
    || !run.evalContractRef || !expectedRun.evalContractRef
    || run.evalContractRef.resourceId !== expectedRun.evalContractRef.resourceId
    || run.evalContractRef.revision !== expectedRun.evalContractRef.revision
    || run.evalContractRef.contentHash !== expectedRun.evalContractRef.contentHash) {
    throw new TypeError("路由 Eval Run 精确引用漂移");
  }

  const suite = record(root.suite, "RouteEvalContextSnapshot.suite");
  const suiteTarget = record(suite.target, "RouteEvalContextSnapshot.suite.target");
  const suiteDataset = record(suite.dataset, "RouteEvalContextSnapshot.suite.dataset");
  const suiteJudge = record(suite.judge, "RouteEvalContextSnapshot.suite.judge");
  const suiteRevision = positiveInt(suite.revision, "RouteEvalContextSnapshot.suite.revision");
  if (suite.suiteId !== run.suiteRef.assetId || String(suiteRevision) !== run.suiteRef.revision
    || sha(suite.contentHash, "RouteEvalContextSnapshot.suite.contentHash") !== run.suiteRef.contentHash
    || suiteTarget.assetType !== run.target.assetType || suiteTarget.assetId !== run.target.assetId
    || suiteTarget.revision !== run.target.revision || suiteTarget.contentHash !== run.target.contentHash
    || suiteDataset.datasetId !== run.dataset.datasetId || suiteDataset.revision !== run.dataset.revision
    || suiteDataset.contentHash !== run.dataset.contentHash || suiteDataset.sourceHash !== run.dataset.sourceHash
    || suiteJudge.judgeId !== run.judge.judgeId || suiteJudge.revision !== run.judge.revision
    || suiteJudge.contentHash !== run.judge.contentHash) {
    throw new TypeError("路由 Eval Suite 与 Run 漂移");
  }

  const dataset = record(root.dataset, "RouteEvalContextSnapshot.dataset");
  if (dataset.datasetId !== run.dataset.datasetId || dataset.revision !== run.dataset.revision
    || dataset.contentHash !== run.dataset.contentHash || dataset.sourceHash !== run.dataset.sourceHash) {
    throw new TypeError("路由 Eval Dataset 漂移");
  }
  const contract = record(root.contract, "RouteEvalContextSnapshot.contract");
  const contractTenant = record(contract.tenant, "RouteEvalContextSnapshot.contract.tenant");
  const contractSuite = record(contract.suiteRef, "RouteEvalContextSnapshot.contract.suiteRef");
  if (contractTenant.orgId !== "org-org" || contractTenant.projectId !== "dev-project"
    || contract.contractId !== run.evalContractRef.resourceId
    || contract.revision !== run.evalContractRef.revision
    || contract.contentHash !== run.evalContractRef.contentHash
    || contract.lifecycle !== "frozen" || contract.readiness !== "ready"
    || !Array.isArray(contract.blockers) || contract.blockers.length !== 0
    || contractSuite.resourceType !== "EvalSuiteRevision"
    || contractSuite.resourceId !== run.suiteRef.assetId
    || contractSuite.revision !== suiteRevision
    || contractSuite.contentHash !== run.suiteRef.contentHash) {
    throw new TypeError("路由 Eval Contract 未冻结就绪或引用漂移");
  }
  return {
    snapshotReadAt: timestamp(root.snapshotReadAt, "RouteEvalContextSnapshot.snapshotReadAt"),
    runId: run.runId, runVersion: run.version, runStatus: run.status,
    suiteId: run.suiteRef.assetId, suiteRevision,
    datasetId: run.dataset.datasetId, datasetRevision: run.dataset.revision,
    judgeId: run.judge.judgeId, judgeRevision: run.judge.revision,
    contractId: run.evalContractRef.resourceId, contractRevision: run.evalContractRef.revision,
    executionAllowed: false,
  };
}
