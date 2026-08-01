import { apiGet, apiPost, apiPut } from "../../api/client";
import {
  assertSavedLogicGraphMatches,
  normalizeLogicGraph,
  type LogicGraphSaveExpectation,
  type LogicGraphSnapshot,
} from "./logicCanvasGraph";

export interface LogicGraphListResponse {
  items: LogicGraphSnapshot[];
  count: number;
}

export interface LogicGraphDraft {
  id: string;
  name: string;
  description: string;
  status: "draft" | "archived";
  schema_version: number;
  nodes: LogicGraphSnapshot["nodes"];
  edges: LogicGraphSnapshot["edges"];
  entry_node_ids: string[];
}

function draftBody(draft: LogicGraphDraft): Omit<LogicGraphDraft, "id"> {
  return {
    name: draft.name,
    description: draft.description,
    status: draft.status,
    schema_version: draft.schema_version,
    nodes: draft.nodes,
    edges: draft.edges,
    entry_node_ids: draft.entry_node_ids,
  };
}

function saveExpectation(draft: LogicGraphDraft, expectedRevision: number): LogicGraphSaveExpectation {
  return {
    graphId: draft.id,
    expectedRevision,
    name: draft.name,
    description: draft.description,
    status: draft.status,
    schemaVersion: draft.schema_version,
    nodes: draft.nodes,
    edges: draft.edges,
    entryNodeIds: draft.entry_node_ids,
  };
}

function assertRereadMatches(saved: LogicGraphSnapshot, reread: LogicGraphSnapshot): void {
  if (!reread.persisted || reread.demo) throw new Error("重新读取未确认持久化");
  if (reread.id !== saved.id || reread.revision !== saved.revision || reread.graph_hash !== saved.graph_hash) {
    throw new Error("保存后重新读取的版本或校验和不一致");
  }
  const savedNormalized = normalizeLogicGraph(saved);
  const rereadNormalized = normalizeLogicGraph(reread);
  const comparable = (graph: LogicGraphSnapshot) => ({
    name: graph.name,
    description: graph.description,
    status: graph.status,
    schema_version: graph.schema_version,
    nodes: graph.nodes,
    edges: graph.edges,
    entry_node_ids: graph.entry_node_ids,
  });
  if (JSON.stringify(comparable(savedNormalized)) !== JSON.stringify(comparable(rereadNormalized))) {
    throw new Error("保存后重新读取的图快照不一致");
  }
}

export async function listLogicGraphs(): Promise<LogicGraphListResponse> {
  const response = await apiGet<LogicGraphListResponse>("/v1/aip/logic/graphs");
  if (!response || !Array.isArray(response.items) || response.count !== response.items.length) {
    throw new Error("Logic Graph 列表响应不完整");
  }
  return { items: response.items.map(normalizeLogicGraph), count: response.count };
}

export async function getLogicGraph(graphId: string): Promise<LogicGraphSnapshot> {
  return normalizeLogicGraph(await apiGet<LogicGraphSnapshot>(`/v1/aip/logic/graphs/${encodeURIComponent(graphId)}`));
}

export async function createLogicGraph(draft: LogicGraphDraft): Promise<LogicGraphSnapshot> {
  const saved = normalizeLogicGraph(await apiPost<LogicGraphSnapshot>("/v1/aip/logic/graphs", {
    id: draft.id,
    ...draftBody(draft),
  }));
  assertSavedLogicGraphMatches(saved, saveExpectation(draft, 0));
  const reread = await getLogicGraph(draft.id);
  assertRereadMatches(saved, reread);
  return reread;
}

export async function replaceLogicGraph(
  draft: LogicGraphDraft,
  expectedRevision: number,
): Promise<LogicGraphSnapshot> {
  const saved = normalizeLogicGraph(await apiPut<LogicGraphSnapshot>(
    `/v1/aip/logic/graphs/${encodeURIComponent(draft.id)}`,
    { ...draftBody(draft), expected_revision: expectedRevision },
  ));
  assertSavedLogicGraphMatches(saved, saveExpectation(draft, expectedRevision));
  const reread = await getLogicGraph(draft.id);
  assertRereadMatches(saved, reread);
  return reread;
}
