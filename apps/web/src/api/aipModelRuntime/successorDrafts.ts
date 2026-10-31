import type { ExactRuntimeRef, ModelRouteRevision, RegisteredModelRevision, RuntimePolicyRevision } from "./contracts";
import { inspectQyhSuccessorPreflight, QYH_RUNTIME_SUCCESSOR, type QyhSuccessorPreflight } from "./qyhSuccessorPreflight";

export type QyhSuccessorDraftClient = {
  model(id: string, revision?: number): Promise<RegisteredModelRevision>;
  policy(id: string, revision?: number): Promise<RuntimePolicyRevision>;
  route(id: string, revision?: number): Promise<ModelRouteRevision>;
  publishModel(item: RegisteredModelRevision, key: string, expectedVersion: number): Promise<RegisteredModelRevision>;
  publishPolicy(item: RuntimePolicyRevision, key: string, expectedVersion: number): Promise<RuntimePolicyRevision>;
  publishRoute(item: ModelRouteRevision, key: string, expectedVersion: number): Promise<ModelRouteRevision>;
};

type PrepareInput = { pairedPolicyRef: ExactRuntimeRef; pairedPriceRef: ExactRuntimeRef; now?: () => string };
type Prepared = { status: "prepared"; model: RegisteredModelRevision; policy: RuntimePolicyRevision; route: ModelRouteRevision };
export type QyhSuccessorDraftState = {
  status: "ready_to_prepare" | "partial_observed" | "prepared";
  observed: { model: boolean; policy: boolean; route: boolean };
  model: RegisteredModelRevision;
  policy: RuntimePolicyRevision;
  route: ModelRouteRevision;
  preflight: QyhSuccessorPreflight;
};

type ResolvedDraftState = QyhSuccessorDraftState & {
  suffix: string;
  modelBase: RegisteredModelRevision;
  policyBase: RuntimePolicyRevision;
  routeBase: ModelRouteRevision;
};

function canonicalJson(value: unknown): string {
  if (value === null || typeof value === "boolean" || typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new TypeError("canonical JSON 不接受非有限数值");
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (typeof value === "object") {
    const raw = value as Record<string, unknown>;
    return `{${Object.keys(raw).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(raw[key])}`).join(",")}}`;
  }
  throw new TypeError("canonical JSON 含不支持的值");
}

export async function canonicalRuntimeHash(value: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(canonicalJson(value));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function contentOf(value: RegisteredModelRevision | RuntimePolicyRevision | ModelRouteRevision): Record<string, unknown> {
  const { tenant: _tenant, revision: _revision, contentHash: _contentHash, createdBy: _createdBy, createdAt: _createdAt, ...content } = value;
  return content;
}

async function seal<T extends RegisteredModelRevision | RuntimePolicyRevision | ModelRouteRevision>(value: T): Promise<T> {
  return { ...value, contentHash: await canonicalRuntimeHash(contentOf(value)) };
}

export function exactRef(type: string, id: string, value: { revision: number; contentHash: string }): ExactRuntimeRef {
  return { assetType: type, assetId: id, revision: value.revision, contentHash: value.contentHash };
}

export async function buildQyhModelDraft(base: RegisteredModelRevision, policyRef: ExactRuntimeRef, priceRef: ExactRuntimeRef, createdAt: string): Promise<RegisteredModelRevision> {
  return seal({ ...base, revision: base.revision + 1, contentHash: "0".repeat(64), budgetPolicyRef: policyRef, priceSnapshotRef: priceRef, evalGateRef: null, lifecycle: "draft", createdAt });
}

export async function buildQyhPolicyDraft(base: RuntimePolicyRevision, policyRef: ExactRuntimeRef, createdAt: string): Promise<RuntimePolicyRevision> {
  return seal({ ...base, revision: base.revision + 1, contentHash: "0".repeat(64), budgetPolicyRef: policyRef, unknownUsageBehavior: "block", unknownPriceBehavior: "block", killSwitchEnabled: true, lifecycle: "draft", createdAt });
}

export async function buildQyhRouteDraft(base: ModelRouteRevision, model: RegisteredModelRevision, policy: RuntimePolicyRevision, createdAt: string): Promise<ModelRouteRevision> {
  return seal({ ...base, revision: base.revision + 1, contentHash: "0".repeat(64), candidates: [{ model: exactRef("RegisteredModelRevision", model.registeredModelId, model), weight: 100 }], runtimePolicyRef: exactRef("RuntimePolicyRevision", policy.policyId, policy), evalGateRef: null, lifecycle: "draft", createdAt });
}

const sameTenant = (value: { tenant: { orgId: string; projectId: string } }) => value.tenant.orgId === "org-org" && value.tenant.projectId === "dev-project";
const sameExact = (left: ExactRuntimeRef, right: ExactRuntimeRef) => left.assetType === right.assetType && left.assetId === right.assetId && left.revision === right.revision && left.contentHash === right.contentHash;
const sameRevision = <T extends { revision: number; contentHash: string }>(left: T, right: T) => left.revision === right.revision && left.contentHash === right.contentHash;

function pairSuffix(input: PrepareInput): string {
  const policy = /^window-policy-([0-9a-f]{64})$/.exec(input.pairedPolicyRef.assetId);
  const price = /^window-price-([0-9a-f]{64})$/.exec(input.pairedPriceRef.assetId);
  if (input.pairedPolicyRef.assetType !== "BudgetPolicyRevision" || input.pairedPriceRef.assetType !== "ModelPriceSnapshotRevision"
    || input.pairedPolicyRef.revision !== 1 || input.pairedPriceRef.revision !== 1 || !policy || policy[1] !== price?.[1]) throw new Error("paired 策略与价格引用漂移");
  return policy[1];
}

function assertBaseModel(value: RegisteredModelRevision) {
  if (!sameTenant(value) || value.registeredModelId !== QYH_RUNTIME_SUCCESSOR.modelId || value.providerModelId !== QYH_RUNTIME_SUCCESSOR.providerModelId
    || value.lifecycle !== "active" || value.provider.assetType !== "ProviderInstanceRevision" || value.quotaPolicyRef.assetType !== "QuotaPolicyRevision") throw new Error("当前注册模型头漂移");
}
function assertBasePolicy(value: RuntimePolicyRevision) {
  if (!sameTenant(value) || value.policyId !== QYH_RUNTIME_SUCCESSOR.policyId || value.lifecycle !== "active" || !value.killSwitchEnabled
    || value.unknownUsageBehavior !== "block" || value.unknownPriceBehavior !== "block") throw new Error("当前运行策略头漂移");
}
function assertBaseRoute(value: ModelRouteRevision, model: RegisteredModelRevision, policy: RuntimePolicyRevision) {
  const candidate = value.candidates.length === 1 ? value.candidates[0] : undefined;
  if (!sameTenant(value) || value.routeId !== QYH_RUNTIME_SUCCESSOR.routeId || value.lifecycle !== "active" || candidate?.weight !== 100
    || !candidate || !sameExact(candidate.model, exactRef("RegisteredModelRevision", model.registeredModelId, model))
    || !sameExact(value.runtimePolicyRef, exactRef("RuntimePolicyRevision", policy.policyId, policy))) throw new Error("当前模型路由头漂移");
}

async function resolveModel(input: PrepareInput, client: QyhSuccessorDraftClient, current: RegisteredModelRevision, at: string) {
  if (current.lifecycle === "active") { assertBaseModel(current); return { base: current, target: await buildQyhModelDraft(current, input.pairedPolicyRef, input.pairedPriceRef, at), done: false }; }
  if (current.lifecycle !== "draft" || current.revision < 2) throw new Error("当前注册模型头漂移");
  const base = await client.model(current.registeredModelId, current.revision - 1); assertBaseModel(base);
  const target = await buildQyhModelDraft(base, input.pairedPolicyRef, input.pairedPriceRef, at);
  if (!sameRevision(current, target)) throw new Error("当前注册模型草稿漂移");
  return { base, target: current, done: true };
}

async function resolvePolicy(input: PrepareInput, client: QyhSuccessorDraftClient, current: RuntimePolicyRevision, at: string) {
  if (current.lifecycle === "active") { assertBasePolicy(current); return { base: current, target: await buildQyhPolicyDraft(current, input.pairedPolicyRef, at), done: false }; }
  if (current.lifecycle !== "draft" || current.revision < 2) throw new Error("当前运行策略头漂移");
  const base = await client.policy(current.policyId, current.revision - 1); assertBasePolicy(base);
  const target = await buildQyhPolicyDraft(base, input.pairedPolicyRef, at);
  if (!sameRevision(current, target)) throw new Error("当前运行策略草稿漂移");
  return { base, target: current, done: true };
}

async function publishAndRead<T extends { revision: number; contentHash: string }>(publish: () => Promise<T>, read: () => Promise<T>, target: T): Promise<T> {
  try { await publish(); } catch { /* unknown result: reconcile by the authority head only */ }
  let current: T;
  try { current = await read(); } catch { throw new Error("草稿写入结果未确认；只能重新读取当前头"); }
  if (!sameRevision(current, target)) throw new Error("草稿写入结果未确认；只能重新读取当前头");
  return current;
}

async function resolveQyhSuccessorDraftState(input: PrepareInput, client: QyhSuccessorDraftClient): Promise<ResolvedDraftState> {
  const suffix = pairSuffix(input), at = (input.now ?? (() => new Date().toISOString()))();
  const [currentModel, currentPolicy, currentRoute] = await Promise.all([
    client.model(QYH_RUNTIME_SUCCESSOR.modelId), client.policy(QYH_RUNTIME_SUCCESSOR.policyId), client.route(QYH_RUNTIME_SUCCESSOR.routeId),
  ]);
  const modelState = await resolveModel(input, client, currentModel, at);
  const policyState = await resolvePolicy(input, client, currentPolicy, at);
  let routeBase: ModelRouteRevision, routeTarget: ModelRouteRevision, routeDone = false;
  if (currentRoute.lifecycle === "active") {
    assertBaseRoute(currentRoute, modelState.base, policyState.base); routeBase = currentRoute;
    routeTarget = await buildQyhRouteDraft(routeBase, modelState.target, policyState.target, at);
  } else if (currentRoute.lifecycle === "draft" && currentRoute.revision >= 2) {
    routeBase = await client.route(currentRoute.routeId, currentRoute.revision - 1); assertBaseRoute(routeBase, modelState.base, policyState.base);
    routeTarget = await buildQyhRouteDraft(routeBase, modelState.target, policyState.target, at);
    if (!sameRevision(currentRoute, routeTarget)) throw new Error("当前模型路由草稿漂移");
    routeTarget = currentRoute; routeDone = true;
  } else throw new Error("当前模型路由头漂移");

  const refreshedPreflight = inspectQyhSuccessorPreflight({
    model: modelState.base,
    policy: policyState.base,
    route: routeBase,
    pairedPolicyRef: input.pairedPolicyRef,
    pairedPriceRef: input.pairedPriceRef,
  });
  if (!refreshedPreflight.ready) throw new Error("写入前完整接续预检已漂移");

  const observed = { model: modelState.done, policy: policyState.done, route: routeDone };
  const completed = Number(observed.model) + Number(observed.policy) + Number(observed.route);
  return {
    status: completed === 0 ? "ready_to_prepare" : completed === 3 ? "prepared" : "partial_observed",
    observed,
    model: modelState.target,
    policy: policyState.target,
    route: routeTarget,
    preflight: refreshedPreflight,
    suffix,
    modelBase: modelState.base,
    policyBase: policyState.base,
    routeBase,
  };
}

export async function inspectQyhSuccessorDraftState(input: PrepareInput, client: QyhSuccessorDraftClient): Promise<QyhSuccessorDraftState> {
  const { status, observed, model, policy, route, preflight } = await resolveQyhSuccessorDraftState(input, client);
  return { status, observed, model, policy, route, preflight };
}

export async function prepareQyhSuccessorDrafts(input: PrepareInput, client: QyhSuccessorDraftClient): Promise<Prepared> {
  const state = await resolveQyhSuccessorDraftState(input, client);
  const { suffix, modelBase, policyBase, routeBase } = state;

  const modelResult = state.observed.model ? state.model : await publishAndRead(
    () => client.publishModel(state.model, `qyh-successor-model-${suffix}-r${state.model.revision}`, modelBase.revision),
    () => client.model(state.model.registeredModelId), state.model,
  );
  const policyResult = state.observed.policy ? state.policy : await publishAndRead(
    () => client.publishPolicy(state.policy, `qyh-successor-policy-${suffix}-r${state.policy.revision}`, policyBase.revision),
    () => client.policy(state.policy.policyId), state.policy,
  );
  const routeResult = state.observed.route ? state.route : await publishAndRead(
    () => client.publishRoute(state.route, `qyh-successor-route-${suffix}-r${state.route.revision}`, routeBase.revision),
    () => client.route(state.route.routeId), state.route,
  );
  return { status: "prepared", model: modelResult, policy: policyResult, route: routeResult };
}
