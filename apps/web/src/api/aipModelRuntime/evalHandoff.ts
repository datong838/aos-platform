import type { ExactRuntimeRef, ModelEvalCandidate } from "./contracts";
import { QYH_RUNTIME_SUCCESSOR } from "./qyhSuccessorPreflight";

export type ModelRuntimeEvalHandoff = {
  model: ExactRuntimeRef;
  route: ExactRuntimeRef;
};

export type MatchedModelRuntimeEvalHandoff = {
  model: ModelEvalCandidate;
  route: ModelEvalCandidate;
};

const HANDOFF_MARKER = "qyh-successor";
const SHA256 = /^[a-f0-9]{64}$/;

function appendRef(params: URLSearchParams, prefix: "model" | "route", ref: ExactRuntimeRef) {
  params.set(`${prefix}Id`, ref.assetId);
  params.set(`${prefix}Revision`, String(ref.revision));
  params.set(`${prefix}Hash`, ref.contentHash);
}

function readRef(params: URLSearchParams, prefix: "model" | "route", assetType: string): ExactRuntimeRef {
  const assetId = String(params.get(`${prefix}Id`) || "").trim();
  const revisionText = String(params.get(`${prefix}Revision`) || "").trim();
  const contentHash = String(params.get(`${prefix}Hash`) || "").trim().toLowerCase();
  const revision = Number(revisionText);
  if (!assetId || !/^\d+$/.test(revisionText) || !Number.isSafeInteger(revision) || revision < 1 || !SHA256.test(contentHash)) {
    throw new Error("Eval 交接参数不完整或格式错误");
  }
  return { assetType, assetId, revision, contentHash };
}

function sameRef(left: ExactRuntimeRef, right: ExactRuntimeRef) {
  return left.assetType === right.assetType
    && left.assetId === right.assetId
    && left.revision === right.revision
    && left.contentHash === right.contentHash;
}

function validateCandidate(label: string, expected: ExactRuntimeRef, candidate: ModelEvalCandidate) {
  if (candidate.executionAllowed !== false) throw new Error(`${label}候选不得携带执行权`);
  if (candidate.sourceLifecycle !== "draft") throw new Error(`${label}候选来源不是待评测草稿`);
  if (!Number.isSafeInteger(candidate.expectedHeadVersion) || candidate.expectedHeadVersion < 1) {
    throw new Error(`${label}候选缺少有效当前头版本`);
  }
  if (candidate.targetRef.assetType !== expected.assetType || candidate.targetRef.assetId !== expected.assetId) {
    throw new Error(`${label}候选目标资产漂移`);
  }
  if (candidate.targetRef.revision !== expected.revision + 1) throw new Error(`${label}候选目标修订不连续`);
  if (!SHA256.test(candidate.targetRef.contentHash)) throw new Error(`${label}候选目标摘要无效`);
}

export function buildModelRuntimeEvalHandoffHref(model: ExactRuntimeRef, route: ExactRuntimeRef) {
  const params = new URLSearchParams({ runtimeHandoff: HANDOFF_MARKER });
  appendRef(params, "model", model);
  appendRef(params, "route", route);
  return `/aip/evals?${params.toString()}`;
}

export function parseModelRuntimeEvalHandoff(params: URLSearchParams): ModelRuntimeEvalHandoff | null {
  const marker = String(params.get("runtimeHandoff") || "").trim();
  if (!marker) return null;
  if (marker !== HANDOFF_MARKER) throw new Error("Eval 交接类型不受支持");
  const handoff = {
    model: readRef(params, "model", "RegisteredModelRevision"),
    route: readRef(params, "route", "ModelRouteRevision"),
  };
  if (handoff.model.assetId !== QYH_RUNTIME_SUCCESSOR.modelId || handoff.route.assetId !== QYH_RUNTIME_SUCCESSOR.routeId) {
    throw new Error("栖月汇模型或路由身份漂移");
  }
  return handoff;
}

export function inspectModelRuntimeEvalHandoff(
  expected: ModelRuntimeEvalHandoff,
  candidates: ModelEvalCandidate[],
): MatchedModelRuntimeEvalHandoff {
  const exact = (ref: ExactRuntimeRef) => candidates.filter((item) => sameRef(item.sourceRef, ref));
  const models = exact(expected.model);
  const routes = exact(expected.route);
  if (models.length !== 1) throw new Error("模型候选未精确匹配当前权威");
  if (routes.length !== 1) throw new Error("路由候选未精确匹配当前权威");
  validateCandidate("模型", expected.model, models[0]);
  validateCandidate("路由", expected.route, routes[0]);
  return { model: models[0], route: routes[0] };
}
