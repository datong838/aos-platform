import { getApiBase } from "../apiBase";
import { apiGet, apiPost } from "../client";
import { getTenant, tenantAuthHeaders } from "../tenant";
import type { AnalystQuery, AssistEvent, AssistThread, CancelTaskRunRequest, CreateAssistThread, CreateAssistTurn, QueryResultRevision, TaskRunControlResult } from "./contracts";
import { parseAssistEvent, parseAssistThread, parseQueryResult, parseTaskRunControlResult, validateAssistStream } from "./parser";

function scope() { const { orgId, projectId } = getTenant(); return { orgId, projectId }; }
export function newIdempotencyKey(): string { return globalThis.crypto.randomUUID(); }

export async function queryAnalyst(query: AnalystQuery): Promise<QueryResultRevision> {
  return parseQueryResult(await apiPost<unknown>("/v1/aip/analyst/query", query), scope());
}
export async function createAssistThread(body: CreateAssistThread, key = newIdempotencyKey()): Promise<AssistThread> {
  return parseAssistThread(await apiPost<unknown>("/v1/aip/assist/threads", body, { "Idempotency-Key": key }), scope());
}
export async function getAssistThread(threadId: string): Promise<AssistThread> {
  return parseAssistThread(await apiGet<unknown>(`/v1/aip/assist/threads/${encodeURIComponent(threadId)}`), scope());
}
export async function cancelAssistTaskRun(runId: string, body: CancelTaskRunRequest, key = newIdempotencyKey()): Promise<TaskRunControlResult> {
  const payload = await apiPost<unknown>(`/v1/aip/task-runs/${encodeURIComponent(runId)}/cancel`, body, { "Idempotency-Key": key });
  return parseTaskRunControlResult(payload);
}

function parseSse(text: string): AssistEvent[] {
  const events: AssistEvent[] = [];
  for (const block of text.replace(/\r\n/g, "\n").split("\n\n")) {
    if (!block.trim()) continue;
    let name = ""; const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) name = line.slice(6).trim();
      if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (!name || !data.length) throw new Error("Assist SSE frame 非法");
    const event = parseAssistEvent(JSON.parse(data.join("\n")));
    if (event.eventType !== name) throw new Error("Assist SSE event 名称漂移");
    events.push(event);
  }
  return validateAssistStream(events);
}

export async function streamAssistTurn(threadId: string, body: CreateAssistTurn, key = newIdempotencyKey()): Promise<AssistEvent[]> {
  const path = `/v1/aip/assist/threads/${encodeURIComponent(threadId)}/turns:stream`;
  const response = await fetch(`${getApiBase().replace(/\/$/, "")}${path}`, {
    method: "POST", headers: { ...tenantAuthHeaders(), Accept: "text/event-stream", "Idempotency-Key": key }, body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { message?: string };
    throw new Error(payload.message || `Assist HTTP ${response.status}`);
  }
  return parseSse(await response.text());
}
