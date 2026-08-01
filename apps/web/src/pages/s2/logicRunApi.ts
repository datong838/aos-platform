import { apiGet, apiPost } from "../../api/client";
import {
  assertDryRunDetailMatches,
  assertLogicDryRunRequest,
  normalizeLogicDryRun,
  normalizeLogicRunList,
  type LogicDryRun,
  type LogicDryRunRequest,
  type LogicRunExpectation,
  type LogicRunListResponse,
} from "./logicRunContracts";

export interface LogicRunListOptions {
  limit?: number;
  before?: string;
}

function resourceId(value: string, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label} 必须是非空字符串`);
  return value;
}

function runExpectation(
  graphId: string,
  request: LogicDryRunRequest,
  nodeIds?: readonly string[],
): LogicRunExpectation {
  return {
    graphId,
    revision: request.expected_revision,
    graphHash: request.expected_graph_hash,
    ...(nodeIds === undefined ? {} : { nodeIds: [...nodeIds] }),
  };
}

function detailPath(graphId: string, runId: string): string {
  return `/v1/aip/logic/graphs/${encodeURIComponent(graphId)}/runs/${encodeURIComponent(runId)}`;
}

async function readLogicRunDetail(
  graphId: string,
  runId: string,
  expectation?: LogicRunExpectation,
): Promise<LogicDryRun> {
  const response = await apiGet<unknown>(detailPath(graphId, runId));
  const normalized = normalizeLogicDryRun(response, expectation);
  if (normalized.graph_id !== graphId) throw new Error("运行详情 graph_id 与请求路径不一致");
  if (normalized.run_id !== runId) throw new Error("运行详情 run_id 与请求路径不一致");
  return normalized;
}

export async function getLogicRun(graphId: string, runId: string): Promise<LogicDryRun> {
  return readLogicRunDetail(resourceId(graphId, "graphId"), resourceId(runId, "runId"));
}

export async function listLogicRuns(
  graphId: string,
  options: LogicRunListOptions = {},
): Promise<LogicRunListResponse> {
  const safeGraphId = resourceId(graphId, "graphId");
  const limit = options.limit ?? 20;
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) throw new Error("历史 limit 必须是 1 到 100 的整数");
  const query = new URLSearchParams({ limit: String(limit) });
  if (options.before !== undefined) query.set("before", resourceId(options.before, "before"));
  const response = await apiGet<unknown>(
    `/v1/aip/logic/graphs/${encodeURIComponent(safeGraphId)}/runs?${query.toString()}`,
  );
  return normalizeLogicRunList(response, safeGraphId);
}

export async function dryRunLogicGraph(
  graphId: string,
  request: LogicDryRunRequest,
  expectedNodeIds: readonly string[],
): Promise<LogicDryRun> {
  const safeGraphId = resourceId(graphId, "graphId");
  assertLogicDryRunRequest(request);
  const expectation = runExpectation(safeGraphId, request, expectedNodeIds);
  const response = normalizeLogicDryRun(await apiPost<unknown>(
    `/v1/aip/logic/graphs/${encodeURIComponent(safeGraphId)}/dry-run`,
    request,
  ), expectation);

  let detail: LogicDryRun;
  try {
    detail = await readLogicRunDetail(safeGraphId, response.run_id, expectation);
    assertDryRunDetailMatches(response, detail);
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("响应已收到，但历史持久化核验失败")) throw error;
    const detailMessage = error instanceof Error ? error.message : String(error);
    throw new Error(`响应已收到，但历史持久化核验失败：${detailMessage}`, { cause: error });
  }
  return detail;
}
