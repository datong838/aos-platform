import { parseEvalRunAuthority, type EvalRunAuthority } from "../aipEvidence";
import type { ModelEvalCandidate } from "./contracts";
import { inspectRouteEvalRunHandoff } from "./routeEvalRunHandoff";

export function routeEvalRunOptionsPath(candidate: ModelEvalCandidate): string {
  if (candidate.sourceRef.assetType !== "ModelRouteRevision"
    || candidate.targetRef.assetType !== "ModelRouteRevision"
    || candidate.executionAllowed !== false
    || candidate.sourceLifecycle !== "draft") {
    throw new Error("当前候选不是可发现 EvalRun 的不可执行路由草稿");
  }
  const query = new URLSearchParams({
    routeId: candidate.sourceRef.assetId,
    sourceRevision: String(candidate.sourceRef.revision),
    sourceHash: candidate.sourceRef.contentHash,
    targetRevision: String(candidate.targetRef.revision),
    targetHash: candidate.targetRef.contentHash,
    expectedHeadVersion: String(candidate.expectedHeadVersion),
  });
  return `/v1/aip/model-runtime/route-eval-run-options?${query.toString()}`;
}

export function parseRouteEvalRunOptions(
  value: unknown,
  candidate: ModelEvalCandidate,
): EvalRunAuthority[] {
  if (!Array.isArray(value) || value.length > 20) throw new Error("路由 EvalRun 选项必须是最多 20 条的数组");
  const runs = value.map((item, index) => {
    const run = parseEvalRunAuthority(item);
    try {
      inspectRouteEvalRunHandoff(candidate, run);
    } catch (error) {
      throw new Error(`路由 EvalRun 选项 ${index + 1} 与当前候选不一致：${String((error as Error).message || error)}`);
    }
    if (!/(?:Z|[+-]\d{2}:\d{2})$/.test(run.createdAt) || !Number.isFinite(Date.parse(run.createdAt))) {
      throw new Error(`路由 EvalRun 选项 ${index + 1} 创建时间无效`);
    }
    return run;
  });
  if (new Set(runs.map((run) => run.runId)).size !== runs.length) throw new Error("路由 EvalRun 选项含重复运行标识");
  return runs;
}
