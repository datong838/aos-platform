import { LOGIC_BLOCK_KINDS, type LogicBlockKind } from "./logicCanvasGraph";

export type LogicRunStatus = "succeeded" | "failed";
export type LogicNodeRunStatus = "executed" | "skipped" | "failed" | "canceled";

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

export interface LogicDryRunRequest {
  expected_revision: number;
  dry_run: true;
  expected_graph_hash: string;
  inputs: JsonObject;
  idempotency_key?: string;
}

export interface LogicTokenUsage {
  model: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

export interface LogicRunError {
  code: string;
  message: string;
  node_id: string | null;
  reason: string | null;
}

export interface LogicToolCall {
  tool: string;
  adapter: string;
  read_only: true;
  dry_run_safe: true;
}

export interface LogicProposedEdit {
  action: string;
  object_id: string;
  field: string;
  value: JsonValue;
  source_node_id: string;
  applied: false;
}

export interface LogicNodeResult {
  node_id: string;
  kind: LogicBlockKind;
  status: LogicNodeRunStatus;
  started_at: string | null;
  finished_at: string | null;
  elapsed_ms: number | null;
  summary: string;
  output: JsonValue;
  usage: LogicTokenUsage | null;
  tool_call: LogicToolCall | null;
  selected_branch_path: string | null;
  proposed_edits: LogicProposedEdit[];
  error: LogicRunError | null;
  truncated: boolean;
}

interface LogicRunCommon {
  run_id: string;
  graph_id: string;
  mode: "dry_run";
  status: LogicRunStatus;
  evaluated_revision: number;
  graph_hash: string;
  production_written: false;
  started_at: string;
  finished_at: string;
  elapsed_ms: number;
  total_tokens: number | null;
}

export interface LogicDryRun extends LogicRunCommon {
  node_results: LogicNodeResult[];
  proposed_edits: LogicProposedEdit[];
  error: LogicRunError | null;
}

export interface LogicRunNodeCounts {
  executed: number;
  skipped: number;
  failed: number;
  canceled: number;
}

export interface LogicRunSummary extends LogicRunCommon {
  node_counts: LogicRunNodeCounts;
  error_code: string | null;
}

export interface LogicRunListResponse {
  items: LogicRunSummary[];
  count: number;
  next_cursor: string | null;
}

export interface LogicRunExpectation {
  graphId: string;
  revision: number;
  graphHash: string;
  nodeIds?: readonly string[];
}

const HASH_RE = /^[0-9a-f]{64}$/i;
const RUN_STATUSES = new Set<LogicRunStatus>(["succeeded", "failed"]);
const NODE_STATUSES = new Set<LogicNodeRunStatus>(["executed", "skipped", "failed", "canceled"]);
const BLOCK_KINDS = new Set<string>(LOGIC_BLOCK_KINDS);
const FORBIDDEN_REASONING_KEYS = new Set(["cot", "reasoning", "chain_of_thought"]);
const REQUEST_KEYS = new Set([
  "expected_revision",
  "dry_run",
  "expected_graph_hash",
  "inputs",
  "idempotency_key",
]);
const RUN_KEYS = new Set([
  "run_id",
  "graph_id",
  "mode",
  "status",
  "evaluated_revision",
  "graph_hash",
  "production_written",
  "started_at",
  "finished_at",
  "elapsed_ms",
  "total_tokens",
  "node_results",
  "proposed_edits",
  "error",
]);
const SUMMARY_KEYS = new Set([
  "run_id",
  "graph_id",
  "mode",
  "status",
  "evaluated_revision",
  "graph_hash",
  "production_written",
  "started_at",
  "finished_at",
  "elapsed_ms",
  "total_tokens",
  "node_counts",
  "error_code",
]);
const NODE_RESULT_KEYS = new Set([
  "node_id",
  "kind",
  "status",
  "started_at",
  "finished_at",
  "elapsed_ms",
  "summary",
  "output",
  "usage",
  "tool_call",
  "selected_branch_path",
  "proposed_edits",
  "error",
  "truncated",
]);
const USAGE_KEYS = new Set(["model", "input_tokens", "output_tokens", "total_tokens"]);
const ERROR_KEYS = new Set(["code", "message", "node_id", "reason"]);
const TOOL_CALL_KEYS = new Set(["tool", "adapter", "read_only", "dry_run_safe"]);
const PROPOSED_EDIT_KEYS = new Set(["action", "object_id", "field", "value", "source_node_id", "applied"]);
const NODE_COUNT_KEYS = new Set(["executed", "skipped", "failed", "canceled"]);
const LIST_KEYS = new Set(["items", "count", "next_cursor"]);

function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function objectValue(value: unknown, label: string): Record<string, unknown> {
  if (!isPlainObject(value)) throw new Error(`${label} 必须是 JSON 对象`);
  return value;
}

function exactKeys(value: Record<string, unknown>, allowed: ReadonlySet<string>, label: string): void {
  const unknown = Object.keys(value).filter((key) => !allowed.has(key));
  if (unknown.length > 0) throw new Error(`${label} 包含未允许字段：${unknown.join(", ")}`);
}

function nonEmptyString(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label} 必须是非空字符串`);
  return value;
}

function timestamp(value: unknown, label: string): string {
  const normalized = nonEmptyString(value, label);
  if (!Number.isFinite(Date.parse(normalized))) throw new Error(`${label} 必须是有效时间`);
  return normalized;
}

function nonNegativeInteger(value: unknown, label: string): number {
  if (!Number.isInteger(value) || (value as number) < 0) throw new Error(`${label} 必须是非负整数`);
  return value as number;
}

function positiveInteger(value: unknown, label: string): number {
  const normalized = nonNegativeInteger(value, label);
  if (normalized < 1) throw new Error(`${label} 必须大于等于 1`);
  return normalized;
}

function nullableNonNegativeInteger(value: unknown, label: string): number | null {
  return value === null ? null : nonNegativeInteger(value, label);
}

function hash(value: unknown, label: string): string {
  if (typeof value !== "string" || !HASH_RE.test(value)) throw new Error(`${label} 必须是 64 位十六进制 hash`);
  return value;
}

function jsonValue(value: unknown, label: string): JsonValue {
  const stack: Array<{ value: unknown; path: string }> = [{ value, path: label }];
  const seen = new WeakSet<object>();
  while (stack.length > 0) {
    const current = stack.pop()!;
    if (
      current.value === null
      || typeof current.value === "string"
      || typeof current.value === "boolean"
    ) continue;
    if (typeof current.value === "number") {
      if (!Number.isFinite(current.value)) throw new Error(`${current.path} 包含非有限数字`);
      continue;
    }
    if (!current.value || typeof current.value !== "object") {
      throw new Error(`${current.path} 包含非 JSON 值`);
    }
    if (seen.has(current.value)) throw new Error(`${current.path} 包含循环引用`);
    seen.add(current.value);
    if (Array.isArray(current.value)) {
      current.value.forEach((item, index) => stack.push({ value: item, path: `${current.path}[${index}]` }));
      continue;
    }
    if (!isPlainObject(current.value)) throw new Error(`${current.path} 包含非 JSON 对象`);
    Object.entries(current.value).forEach(([key, item]) => stack.push({ value: item, path: `${current.path}.${key}` }));
  }
  return value as JsonValue;
}

function jsonObject(value: unknown, label: string): JsonObject {
  objectValue(value, label);
  return jsonValue(value, label) as JsonObject;
}

export function assertNoPrivateReasoning(value: unknown): void {
  const stack: Array<{ value: unknown; path: string }> = [{ value, path: "response" }];
  const seen = new WeakSet<object>();
  while (stack.length > 0) {
    const current = stack.pop()!;
    if (!current.value || typeof current.value !== "object") continue;
    if (seen.has(current.value)) continue;
    seen.add(current.value);
    if (Array.isArray(current.value)) {
      current.value.forEach((item, index) => stack.push({ value: item, path: `${current.path}[${index}]` }));
      continue;
    }
    Object.entries(current.value as Record<string, unknown>).forEach(([key, item]) => {
      if (FORBIDDEN_REASONING_KEYS.has(key.toLowerCase())) {
        throw new Error(`响应包含禁止的模型私有推理字段：${current.path}.${key}`);
      }
      stack.push({ value: item, path: `${current.path}.${key}` });
    });
  }
}

function normalizeUsage(value: unknown, label: string): LogicTokenUsage | null {
  if (value === null) return null;
  const raw = objectValue(value, label);
  exactKeys(raw, USAGE_KEYS, label);
  const inputTokens = nonNegativeInteger(raw.input_tokens, `${label}.input_tokens`);
  const outputTokens = nonNegativeInteger(raw.output_tokens, `${label}.output_tokens`);
  const totalTokens = nonNegativeInteger(raw.total_tokens, `${label}.total_tokens`);
  if (totalTokens !== inputTokens + outputTokens) throw new Error(`${label}.total_tokens 与输入输出 token 不一致`);
  return {
    model: nonEmptyString(raw.model, `${label}.model`),
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    total_tokens: totalTokens,
  };
}

function normalizeError(value: unknown, label: string): LogicRunError | null {
  if (value === null) return null;
  const raw = objectValue(value, label);
  exactKeys(raw, ERROR_KEYS, label);
  return {
    code: nonEmptyString(raw.code, `${label}.code`),
    message: nonEmptyString(raw.message, `${label}.message`),
    node_id: raw.node_id === null ? null : nonEmptyString(raw.node_id, `${label}.node_id`),
    reason: raw.reason === null ? null : nonEmptyString(raw.reason, `${label}.reason`),
  };
}

function normalizeToolCall(value: unknown, label: string): LogicToolCall | null {
  if (value === null) return null;
  const raw = objectValue(value, label);
  exactKeys(raw, TOOL_CALL_KEYS, label);
  if (raw.read_only !== true || raw.dry_run_safe !== true) {
    throw new Error(`${label} 必须明确 read_only=true 且 dry_run_safe=true`);
  }
  return {
    tool: nonEmptyString(raw.tool, `${label}.tool`),
    adapter: nonEmptyString(raw.adapter, `${label}.adapter`),
    read_only: true,
    dry_run_safe: true,
  };
}

function normalizeEdits(value: unknown, label: string): LogicProposedEdit[] {
  if (!Array.isArray(value)) throw new Error(`${label} 必须是数组`);
  return value.map((item, index) => {
    const itemLabel = `${label}[${index}]`;
    const raw = objectValue(item, itemLabel);
    exactKeys(raw, PROPOSED_EDIT_KEYS, itemLabel);
    if (raw.applied !== false) throw new Error(`${itemLabel}.applied 必须严格为 false`);
    return {
      action: nonEmptyString(raw.action, `${itemLabel}.action`),
      object_id: nonEmptyString(raw.object_id, `${itemLabel}.object_id`),
      field: nonEmptyString(raw.field, `${itemLabel}.field`),
      value: jsonValue(raw.value, `${itemLabel}.value`),
      source_node_id: nonEmptyString(raw.source_node_id, `${itemLabel}.source_node_id`),
      applied: false,
    };
  });
}

function normalizeNodeResult(value: unknown, index: number): LogicNodeResult {
  const label = `node_results[${index}]`;
  const raw = objectValue(value, label);
  exactKeys(raw, NODE_RESULT_KEYS, label);
  const kind = nonEmptyString(raw.kind, `${label}.kind`);
  if (!BLOCK_KINDS.has(kind)) throw new Error(`${label}.kind 未知：${kind}`);
  const status = nonEmptyString(raw.status, `${label}.status`);
  if (!NODE_STATUSES.has(status as LogicNodeRunStatus)) throw new Error(`${label}.status 未知：${status}`);
  const error = normalizeError(raw.error, `${label}.error`);
  if (status === "executed" && error !== null) throw new Error(`${label} executed 节点不得带 error`);
  if (status === "failed" && error === null) throw new Error(`${label} failed 节点必须带 error`);
  if ((status === "skipped" || status === "canceled") && !error?.reason) {
    throw new Error(`${label} ${status} 节点必须带机器可读 reason`);
  }
  return {
    node_id: nonEmptyString(raw.node_id, `${label}.node_id`),
    kind: kind as LogicBlockKind,
    status: status as LogicNodeRunStatus,
    started_at: raw.started_at === null ? null : timestamp(raw.started_at, `${label}.started_at`),
    finished_at: raw.finished_at === null ? null : timestamp(raw.finished_at, `${label}.finished_at`),
    elapsed_ms: nullableNonNegativeInteger(raw.elapsed_ms, `${label}.elapsed_ms`),
    summary: typeof raw.summary === "string" ? raw.summary : (() => { throw new Error(`${label}.summary 必须是字符串`); })(),
    output: jsonValue(raw.output, `${label}.output`),
    usage: normalizeUsage(raw.usage, `${label}.usage`),
    tool_call: normalizeToolCall(raw.tool_call, `${label}.tool_call`),
    selected_branch_path: raw.selected_branch_path === null
      ? null
      : nonEmptyString(raw.selected_branch_path, `${label}.selected_branch_path`),
    proposed_edits: normalizeEdits(raw.proposed_edits, `${label}.proposed_edits`),
    error,
    truncated: typeof raw.truncated === "boolean"
      ? raw.truncated
      : (() => { throw new Error(`${label}.truncated 必须是 boolean`); })(),
  };
}

function normalizeRunStatus(value: unknown, label: string): LogicRunStatus {
  const normalized = nonEmptyString(value, label);
  if (!RUN_STATUSES.has(normalized as LogicRunStatus)) throw new Error(`${label} 未知：${normalized}`);
  return normalized as LogicRunStatus;
}

function commonRunFields(raw: Record<string, unknown>, label: string): LogicRunCommon {
  if (raw.mode !== "dry_run") throw new Error(`${label}.mode 必须严格为 dry_run`);
  if (raw.production_written !== false) throw new Error(`${label}.production_written 必须严格为 false`);
  return {
    run_id: nonEmptyString(raw.run_id, `${label}.run_id`),
    graph_id: nonEmptyString(raw.graph_id, `${label}.graph_id`),
    mode: "dry_run",
    status: normalizeRunStatus(raw.status, `${label}.status`),
    evaluated_revision: positiveInteger(raw.evaluated_revision, `${label}.evaluated_revision`),
    graph_hash: hash(raw.graph_hash, `${label}.graph_hash`),
    production_written: false,
    started_at: timestamp(raw.started_at, `${label}.started_at`),
    finished_at: timestamp(raw.finished_at, `${label}.finished_at`),
    elapsed_ms: nonNegativeInteger(raw.elapsed_ms, `${label}.elapsed_ms`),
    total_tokens: nullableNonNegativeInteger(raw.total_tokens, `${label}.total_tokens`),
  };
}

function assertRunExpectation(run: LogicRunCommon, expectation?: LogicRunExpectation): void {
  if (!expectation) return;
  if (run.graph_id !== expectation.graphId) throw new Error("运行结果 graph_id 与请求不一致");
  if (run.evaluated_revision !== expectation.revision) throw new Error("运行结果 revision 与请求不一致");
  if (run.graph_hash !== expectation.graphHash) throw new Error("运行结果 graph_hash 与请求不一致");
}

export function assertLogicDryRunRequest(value: unknown): asserts value is LogicDryRunRequest {
  const raw = objectValue(value, "dry-run 请求");
  exactKeys(raw, REQUEST_KEYS, "dry-run 请求");
  positiveInteger(raw.expected_revision, "expected_revision");
  if (raw.dry_run !== true) throw new Error("dry_run 必须显式且严格为 true");
  hash(raw.expected_graph_hash, "expected_graph_hash");
  jsonObject(raw.inputs, "inputs");
  let serialized: string;
  try {
    serialized = JSON.stringify(raw.inputs);
  } catch {
    throw new Error("inputs 必须可序列化为 JSON");
  }
  if (new TextEncoder().encode(serialized).byteLength > 256 * 1024) throw new Error("inputs 超过 256 KiB");
  if (raw.idempotency_key !== undefined) {
    const key = nonEmptyString(raw.idempotency_key, "idempotency_key");
    if (key.length > 160) throw new Error("idempotency_key 最长 160 字符");
  }
}

export function normalizeLogicDryRun(value: unknown, expectation?: LogicRunExpectation): LogicDryRun {
  assertNoPrivateReasoning(value);
  const raw = objectValue(value, "dry-run 响应");
  exactKeys(raw, RUN_KEYS, "dry-run 响应");
  const common = commonRunFields(raw, "dry-run 响应");
  assertRunExpectation(common, expectation);
  if (!Array.isArray(raw.node_results)) throw new Error("dry-run 响应.node_results 必须是数组");
  const nodeResults = raw.node_results.map(normalizeNodeResult);
  const nodeIds = new Set<string>();
  const expectedNodeIds = expectation?.nodeIds ? new Set(expectation.nodeIds) : null;
  nodeResults.forEach((result) => {
    if (nodeIds.has(result.node_id)) throw new Error(`运行结果包含重复 node_id：${result.node_id}`);
    nodeIds.add(result.node_id);
    if (expectedNodeIds && !expectedNodeIds.has(result.node_id)) {
      throw new Error(`运行结果 node_id 不属于当前图：${result.node_id}`);
    }
  });
  const error = normalizeError(raw.error, "dry-run 响应.error");
  if (common.status === "succeeded" && error !== null) throw new Error("成功的 dry-run 响应不得带 error");
  if (common.status === "failed" && error === null) throw new Error("失败的 dry-run 响应必须带 error");
  return {
    ...common,
    node_results: nodeResults,
    proposed_edits: normalizeEdits(raw.proposed_edits, "dry-run 响应.proposed_edits"),
    error,
  };
}

export function normalizeLogicRunSummary(value: unknown, expectedGraphId?: string): LogicRunSummary {
  assertNoPrivateReasoning(value);
  const raw = objectValue(value, "运行摘要");
  exactKeys(raw, SUMMARY_KEYS, "运行摘要");
  const countRaw = objectValue(raw.node_counts, "运行摘要.node_counts");
  exactKeys(countRaw, NODE_COUNT_KEYS, "运行摘要.node_counts");
  const summary: LogicRunSummary = {
    ...commonRunFields(raw, "运行摘要"),
    node_counts: {
      executed: nonNegativeInteger(countRaw.executed, "运行摘要.node_counts.executed"),
      skipped: nonNegativeInteger(countRaw.skipped, "运行摘要.node_counts.skipped"),
      failed: nonNegativeInteger(countRaw.failed, "运行摘要.node_counts.failed"),
      canceled: nonNegativeInteger(countRaw.canceled, "运行摘要.node_counts.canceled"),
    },
    error_code: raw.error_code === null ? null : nonEmptyString(raw.error_code, "运行摘要.error_code"),
  };
  if (expectedGraphId !== undefined && summary.graph_id !== expectedGraphId) {
    throw new Error("运行摘要 graph_id 与历史路径不一致");
  }
  return summary;
}

export function normalizeLogicRunList(value: unknown, expectedGraphId: string): LogicRunListResponse {
  assertNoPrivateReasoning(value);
  const raw = objectValue(value, "运行历史响应");
  exactKeys(raw, LIST_KEYS, "运行历史响应");
  if (!Array.isArray(raw.items)) throw new Error("运行历史响应.items 必须是数组");
  const items = raw.items.map((item) => normalizeLogicRunSummary(item, expectedGraphId));
  const count = nonNegativeInteger(raw.count, "运行历史响应.count");
  if (count !== items.length) throw new Error("运行历史响应.count 与 items 数量不一致");
  const runIds = new Set<string>();
  items.forEach((item) => {
    if (runIds.has(item.run_id)) throw new Error(`运行历史包含重复 run_id：${item.run_id}`);
    runIds.add(item.run_id);
  });
  return {
    items,
    count,
    next_cursor: raw.next_cursor === null ? null : nonEmptyString(raw.next_cursor, "运行历史响应.next_cursor"),
  };
}

export function assertDryRunDetailMatches(response: LogicDryRun, detail: LogicDryRun): void {
  if (
    detail.run_id !== response.run_id
    || detail.graph_id !== response.graph_id
    || detail.status !== response.status
    || detail.evaluated_revision !== response.evaluated_revision
    || detail.graph_hash !== response.graph_hash
    || detail.production_written !== false
  ) {
    throw new Error("响应已收到，但历史持久化核验失败：detail 与 POST 响应不一致");
  }
}
