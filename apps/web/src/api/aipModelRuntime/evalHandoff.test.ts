import { describe, expect, it } from "vitest";
import type { ExactRuntimeRef, ModelEvalCandidate } from "./contracts";
import {
  buildModelRuntimeEvalHandoffHref,
  inspectModelRuntimeEvalHandoff,
  parseModelRuntimeEvalHandoff,
} from "./evalHandoff";
import { QYH_RUNTIME_SUCCESSOR } from "./qyhSuccessorPreflight";

const model: ExactRuntimeRef = {
  assetType: "RegisteredModelRevision",
  assetId: QYH_RUNTIME_SUCCESSOR.modelId,
  revision: 13,
  contentHash: "a".repeat(64),
};
const route: ExactRuntimeRef = {
  assetType: "ModelRouteRevision",
  assetId: QYH_RUNTIME_SUCCESSOR.routeId,
  revision: 13,
  contentHash: "b".repeat(64),
};
const candidate = (sourceRef: ExactRuntimeRef): ModelEvalCandidate => ({
  sourceRef,
  targetRef: { ...sourceRef, revision: sourceRef.revision + 1, contentHash: "c".repeat(64) },
  expectedHeadVersion: sourceRef.revision,
  sourceLifecycle: "draft",
  executionAllowed: false,
});

describe("model runtime Eval exact handoff", () => {
  it("round-trips exact model and route source refs", () => {
    const href = buildModelRuntimeEvalHandoffHref(model, route);
    expect(href.startsWith("/aip/evals?")).toBe(true);
    const parsed = parseModelRuntimeEvalHandoff(new URL(href, "http://aos.local").searchParams);
    expect(parsed).toEqual({ model, route });
  });

  it("fails closed when a marked handoff is incomplete", () => {
    expect(() => parseModelRuntimeEvalHandoff(new URLSearchParams("runtimeHandoff=qyh-successor")))
      .toThrow("交接参数不完整");
  });

  it("rejects a well-formed deep link for another model or route", () => {
    const href = buildModelRuntimeEvalHandoffHref({ ...model, assetId: "foreign-model" }, route);
    expect(() => parseModelRuntimeEvalHandoff(new URL(href, "http://aos.local").searchParams))
      .toThrow("栖月汇模型或路由身份漂移");
  });

  it("accepts only the exact current model and route candidates", () => {
    const result = inspectModelRuntimeEvalHandoff({ model, route }, [candidate(model), candidate(route)]);
    expect(result.model.sourceRef).toEqual(model);
    expect(result.route.sourceRef).toEqual(route);
  });

  it("blocks source drift and executable or malformed targets", () => {
    expect(() => inspectModelRuntimeEvalHandoff({ model, route }, [
      candidate({ ...model, revision: model.revision + 1 }),
      candidate(route),
    ])).toThrow("模型候选未精确匹配");
    expect(() => inspectModelRuntimeEvalHandoff({ model, route }, [
      { ...candidate(model), executionAllowed: true } as unknown as ModelEvalCandidate,
      candidate(route),
    ])).toThrow("不得携带执行权");
    expect(() => inspectModelRuntimeEvalHandoff({ model, route }, [
      { ...candidate(model), targetRef: { ...model, revision: model.revision + 2, contentHash: "d".repeat(64) } },
      candidate(route),
    ])).toThrow("目标修订不连续");
  });
});
