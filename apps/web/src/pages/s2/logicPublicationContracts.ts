import {
  normalizeLogicGraph,
  type LogicGraphSnapshot,
} from "./logicCanvasGraph";

export interface LogicPublishRequest {
  expected_revision: number;
  expected_graph_hash: string;
  eval_suite_id: string;
  eval_report_id: string;
  idempotency_key: string;
}

export interface LogicPublicationEvalGate {
  gate_passed: true;
  pass_rate: number;
  threshold: number;
  passed: number;
  failed: number;
  total: number;
  run_at: string;
}

export interface LogicPublication {
  publication_id: string;
  graph_id: string;
  graph_revision: number;
  graph_hash: string;
  graph_snapshot: LogicGraphSnapshot;
  dry_run_id: string;
  eval_suite_id: string;
  eval_report_id: string;
  eval_gate: LogicPublicationEvalGate;
  actor: string;
  created_at: string;
}

export interface LogicPublicationListResponse {
  items: LogicPublication[];
  count: number;
}

export interface LogicPublicationExpectation {
  graphId?: string;
  request?: LogicPublishRequest;
}

const HASH_RE = /^[0-9a-f]{64}$/;
const MAX_STRING_LENGTH = 32_768;
const MAX_RESOURCE_ID_LENGTH = 160;
const REQUEST_KEYS = new Set([
  "expected_revision",
  "expected_graph_hash",
  "eval_suite_id",
  "eval_report_id",
  "idempotency_key",
]);
const PUBLICATION_KEYS = new Set([
  "publication_id",
  "graph_id",
  "graph_revision",
  "graph_hash",
  "graph_snapshot",
  "dry_run_id",
  "eval_suite_id",
  "eval_report_id",
  "eval_gate",
  "actor",
  "created_at",
]);
const EVAL_GATE_KEYS = new Set([
  "gate_passed",
  "pass_rate",
  "threshold",
  "passed",
  "failed",
  "total",
  "run_at",
]);
const LIST_KEYS = new Set(["items", "count"]);
const SNAPSHOT_KEYS = new Set([
  "id",
  "name",
  "description",
  "status",
  "schema_version",
  "revision",
  "published_version",
  "graph_hash",
  "persisted",
  "nodes",
  "edges",
  "entry_node_ids",
  "created_at",
  "updated_at",
]);

function plainObject(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} 必须是 JSON 对象`);
  }
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) {
    throw new Error(`${label} 必须是普通 JSON 对象`);
  }
  return value as Record<string, unknown>;
}

function exactKeys(value: Record<string, unknown>, allowed: ReadonlySet<string>, label: string): void {
  const unknown = Object.keys(value).filter((key) => !allowed.has(key));
  if (unknown.length > 0) throw new Error(`${label} 包含未允许字段：${unknown.join(", ")}`);
  const missing = [...allowed].filter((key) => !(key in value));
  if (missing.length > 0) throw new Error(`${label} 缺少字段：${missing.join(", ")}`);
}

function nonEmptyString(value: unknown, label: string, maxLength = MAX_STRING_LENGTH): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label} 必须是非空字符串`);
  if (Array.from(value).length > maxLength) throw new Error(`${label} 长度超过 ${maxLength}`);
  return value;
}

function resourceId(value: unknown, label: string): string {
  return nonEmptyString(value, label, MAX_RESOURCE_ID_LENGTH);
}

function positiveSafeInteger(value: unknown, label: string): number {
  if (!Number.isSafeInteger(value) || (value as number) < 1) {
    throw new Error(`${label} 必须是正安全整数`);
  }
  return value as number;
}

function nonNegativeSafeInteger(value: unknown, label: string): number {
  if (!Number.isSafeInteger(value) || (value as number) < 0) {
    throw new Error(`${label} 必须是非负安全整数`);
  }
  return value as number;
}

function unitInterval(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1) {
    throw new Error(`${label} 必须是 0 到 1 的有限数`);
  }
  return value;
}

function graphHash(value: unknown, label: string): string {
  if (typeof value !== "string" || !HASH_RE.test(value)) {
    throw new Error(`${label} 必须是 64 位十六进制 hash`);
  }
  return value;
}

function timestamp(value: unknown, label: string): string {
  const normalized = nonEmptyString(value, label);
  if (!Number.isFinite(Date.parse(normalized))) throw new Error(`${label} 必须是有效时间`);
  return normalized;
}

function normalizeSnapshot(
  value: unknown,
  graphId: string,
  graphRevision: number,
  hash: string,
): LogicGraphSnapshot {
  const raw = plainObject(value, "graph_snapshot");
  exactKeys(raw, SNAPSHOT_KEYS, "graph_snapshot");
  if (raw.persisted !== true) throw new Error("graph_snapshot.persisted 必须严格为 persisted=true");
  const publishedVersion = raw.published_version === null
    ? null
    : positiveSafeInteger(raw.published_version, "graph_snapshot.published_version");
  const createdAt = timestamp(raw.created_at, "graph_snapshot.created_at");
  const updatedAt = timestamp(raw.updated_at, "graph_snapshot.updated_at");
  if (Date.parse(updatedAt) < Date.parse(createdAt)) {
    throw new Error("graph_snapshot.updated_at 不得早于 created_at");
  }
  const normalized = normalizeLogicGraph({
    ...(raw as unknown as LogicGraphSnapshot),
    published_version: publishedVersion,
    persisted: true,
    created_at: createdAt,
    updated_at: updatedAt,
  });
  if (normalized.id !== graphId) throw new Error("graph_snapshot.id 与 graph_id 不一致");
  if (normalized.revision !== graphRevision) throw new Error("graph_snapshot.revision 与 graph_revision 不一致");
  if (normalized.graph_hash !== hash) throw new Error("graph_snapshot.graph_hash 与 graph_hash 不一致");
  return normalized;
}

function normalizeEvalGate(value: unknown): LogicPublicationEvalGate {
  const raw = plainObject(value, "eval_gate");
  exactKeys(raw, EVAL_GATE_KEYS, "eval_gate");
  if (raw.gate_passed !== true) throw new Error("eval_gate.gate_passed 必须严格为 gate_passed=true");
  const passRate = unitInterval(raw.pass_rate, "eval_gate.pass_rate");
  const threshold = unitInterval(raw.threshold, "eval_gate.threshold");
  const passed = nonNegativeSafeInteger(raw.passed, "eval_gate.passed");
  const failed = nonNegativeSafeInteger(raw.failed, "eval_gate.failed");
  const total = nonNegativeSafeInteger(raw.total, "eval_gate.total");
  if (total < 1) throw new Error("eval_gate.total 必须大于 0");
  if (passed + failed !== total) throw new Error("eval_gate.passed + failed 必须等于 total");
  const computedRate = passed / total;
  if (Math.abs(passRate - computedRate) > 0.0001) {
    throw new Error("eval_gate.pass_rate 与 passed/total 不一致");
  }
  if (passRate < threshold) throw new Error("eval_gate 已标通过但 pass_rate 低于 threshold");
  return {
    gate_passed: true,
    pass_rate: passRate,
    threshold,
    passed,
    failed,
    total,
    run_at: timestamp(raw.run_at, "eval_gate.run_at"),
  };
}

export function assertLogicPublicationRequest(value: LogicPublishRequest): void {
  const raw = plainObject(value, "publish request");
  exactKeys(raw, REQUEST_KEYS, "publish request");
  positiveSafeInteger(raw.expected_revision, "expected_revision");
  graphHash(raw.expected_graph_hash, "expected_graph_hash");
  resourceId(raw.eval_suite_id, "eval_suite_id");
  resourceId(raw.eval_report_id, "eval_report_id");
  resourceId(raw.idempotency_key, "idempotency_key");
}

export function normalizeLogicPublication(
  value: unknown,
  expectation: LogicPublicationExpectation = {},
): LogicPublication {
  const raw = plainObject(value, "publication");
  exactKeys(raw, PUBLICATION_KEYS, "publication");
  const graphId = resourceId(raw.graph_id, "graph_id");
  const graphRevision = positiveSafeInteger(raw.graph_revision, "graph_revision");
  const hash = graphHash(raw.graph_hash, "graph_hash");
  const evalSuiteId = resourceId(raw.eval_suite_id, "eval_suite_id");
  const evalReportId = resourceId(raw.eval_report_id, "eval_report_id");
  const evalGate = normalizeEvalGate(raw.eval_gate);
  const createdAt = timestamp(raw.created_at, "created_at");
  if (Date.parse(evalGate.run_at) > Date.parse(createdAt)) {
    throw new Error("eval_gate.run_at 不得晚于 publication.created_at");
  }
  const normalized: LogicPublication = {
    publication_id: resourceId(raw.publication_id, "publication_id"),
    graph_id: graphId,
    graph_revision: graphRevision,
    graph_hash: hash,
    graph_snapshot: normalizeSnapshot(raw.graph_snapshot, graphId, graphRevision, hash),
    dry_run_id: resourceId(raw.dry_run_id, "dry_run_id"),
    eval_suite_id: evalSuiteId,
    eval_report_id: evalReportId,
    eval_gate: evalGate,
    actor: nonEmptyString(raw.actor, "actor", 320),
    created_at: createdAt,
  };
  if (expectation.graphId !== undefined && graphId !== expectation.graphId) {
    throw new Error("publication.graph_id 与请求路径 graph_id 不一致");
  }
  if (expectation.request !== undefined) {
    assertLogicPublicationRequest(expectation.request);
    if (graphRevision !== expectation.request.expected_revision) {
      throw new Error("publication.graph_revision 与 publish request 不一致");
    }
    if (hash !== expectation.request.expected_graph_hash) {
      throw new Error("publication.graph_hash 与 publish request 不一致");
    }
    if (evalSuiteId !== expectation.request.eval_suite_id) {
      throw new Error("publication.eval_suite_id 与 publish request 不一致");
    }
    if (evalReportId !== expectation.request.eval_report_id) {
      throw new Error("publication.eval_report_id 与 publish request 不一致");
    }
  }
  return normalized;
}

export function normalizeLogicPublicationList(
  value: unknown,
  graphId: string,
): LogicPublicationListResponse {
  resourceId(graphId, "graphId");
  const raw = plainObject(value, "publication list");
  exactKeys(raw, LIST_KEYS, "publication list");
  if (!Array.isArray(raw.items)) throw new Error("publication list.items 必须是数组");
  const count = nonNegativeSafeInteger(raw.count, "publication list.count");
  if (count !== raw.items.length) throw new Error("publication list.count 与 items 长度不一致");
  const ids = new Set<string>();
  const items = raw.items.map((item) => {
    const publication = normalizeLogicPublication(item, { graphId });
    if (ids.has(publication.publication_id)) throw new Error("publication list.publication_id 重复");
    ids.add(publication.publication_id);
    return publication;
  });
  return { items, count };
}

function stableValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stableValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, child]) => [key, stableValue(child)]),
    );
  }
  return value;
}

function comparablePublication(publication: LogicPublication): string {
  return JSON.stringify(stableValue(publication));
}

export function assertLogicPublicationDetailMatches(
  posted: LogicPublication,
  reread: LogicPublication,
): void {
  if (comparablePublication(posted) !== comparablePublication(reread)) {
    throw new Error("发布响应与服务端详情回读不一致");
  }
}
