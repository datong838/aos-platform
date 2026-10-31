import type { ExactRuntimeRef, ModelRouteRevision, RegisteredModelRevision, RuntimePolicyRevision } from "./contracts";

export const QYH_RUNTIME_SUCCESSOR = {
  tenant: { orgId: "org-org", projectId: "dev-project" },
  modelId: "a0v-agnes-2-5-flash-readonly-dev",
  providerModelId: "agnes-2.5-flash",
  policyId: "a0v-ecommerce-runtime-policy-v1",
  routeId: "a0v-ecommerce-text-readonly-v1",
} as const;

type Step = { id: "model" | "policy" | "route"; label: string; status: "ready" | "blocked"; reason: string };
export type QyhSuccessorPreflight = { ready: boolean; executionAllowed: false; steps: Step[] };

const sameTenant = (value: { tenant: { orgId: string; projectId: string } }) =>
  value.tenant.orgId === QYH_RUNTIME_SUCCESSOR.tenant.orgId && value.tenant.projectId === QYH_RUNTIME_SUCCESSOR.tenant.projectId;
const sameRef = (ref: ExactRuntimeRef, type: string, id: string, revision: number, hash: string) =>
  ref.assetType === type && ref.assetId === id && ref.revision === revision && ref.contentHash === hash;

export function inspectQyhSuccessorPreflight(input: {
  model: RegisteredModelRevision;
  policy: RuntimePolicyRevision;
  route: ModelRouteRevision;
  pairedPolicyRef: ExactRuntimeRef;
  pairedPriceRef: ExactRuntimeRef;
}): QyhSuccessorPreflight {
  const policyPair = /^window-policy-([0-9a-f]{64})$/.exec(input.pairedPolicyRef.assetId);
  const pricePair = /^window-price-([0-9a-f]{64})$/.exec(input.pairedPriceRef.assetId);
  const pairedRefsReady = input.pairedPolicyRef.assetType === "BudgetPolicyRevision"
    && input.pairedPriceRef.assetType === "ModelPriceSnapshotRevision"
    && input.pairedPolicyRef.revision === 1 && input.pairedPriceRef.revision === 1
    && policyPair?.[1] === pricePair?.[1];
  const modelReady = pairedRefsReady && sameTenant(input.model)
    && input.model.registeredModelId === QYH_RUNTIME_SUCCESSOR.modelId
    && input.model.providerModelId === QYH_RUNTIME_SUCCESSOR.providerModelId
    && input.model.provider.assetType === "ProviderInstanceRevision"
    && input.model.quotaPolicyRef.assetType === "QuotaPolicyRevision"
    && input.model.budgetPolicyRef.assetType === "BudgetPolicyRevision"
    && input.model.priceSnapshotRef.assetType === "ModelPriceSnapshotRevision"
    && input.model.lifecycle === "active";
  const policyReady = pairedRefsReady && sameTenant(input.policy)
    && input.policy.policyId === QYH_RUNTIME_SUCCESSOR.policyId
    && input.policy.killSwitchEnabled
    && input.policy.unknownUsageBehavior === "block"
    && input.policy.unknownPriceBehavior === "block"
    && input.policy.lifecycle === "active";
  const candidate = input.route.candidates.length === 1 ? input.route.candidates[0] : undefined;
  const routeReady = sameTenant(input.route)
    && input.route.routeId === QYH_RUNTIME_SUCCESSOR.routeId
    && input.route.lifecycle === "active"
    && candidate?.weight === 100
    && Boolean(candidate && sameRef(candidate.model, "RegisteredModelRevision", input.model.registeredModelId, input.model.revision, input.model.contentHash))
    && sameRef(input.route.runtimePolicyRef, "RuntimePolicyRevision", input.policy.policyId, input.policy.revision, input.policy.contentHash);
  const steps: Step[] = [
    { id: "model", label: "注册模型草稿", status: modelReady ? "ready" : "blocked", reason: modelReady ? "可仅替换新预算策略与价格引用" : "租户、模型身份、Provider/配额或 paired 引用不匹配" },
    { id: "policy", label: "运行策略草稿", status: policyReady ? "ready" : "blocked", reason: policyReady ? "可保持 Kill Switch 与未知费用禁入" : "租户、策略身份或默认禁入语义不匹配" },
    { id: "route", label: "模型路由草稿", status: routeReady ? "ready" : "blocked", reason: routeReady ? "可精确接到当前单模型与策略头" : "租户、路由身份、候选模型或运行策略引用漂移" },
  ];
  return { ready: steps.every((item) => item.status === "ready"), executionAllowed: false, steps };
}
