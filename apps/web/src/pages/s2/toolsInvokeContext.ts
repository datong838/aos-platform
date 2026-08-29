/** W-T3: exact invoke context for tools panel — no wo-1001 fallback. */

export type ToolsInvokeContext = {
  objectType: string;
  objectId: string;
  taskId?: string;
  agentRunId?: string;
};

export function parseToolsInvokeContext(search: URLSearchParams): ToolsInvokeContext | null {
  const objectType = String(search.get("objectType") || "").trim();
  const objectId = String(search.get("objectId") || "").trim();
  if (!objectType || !objectId) return null;
  if (objectId.toLowerCase() === "wo-1001") return null;
  const taskId = String(search.get("taskId") || "").trim() || undefined;
  const agentRunId = String(search.get("agentRunId") || "").trim() || undefined;
  return { objectType, objectId, taskId, agentRunId };
}

export function toolsInvokeBlocker(
  ctx: ToolsInvokeContext | null,
  drafts: { draftObjectType: string; draftObjectId: string },
): string | null {
  const objectType = (ctx?.objectType || drafts.draftObjectType).trim();
  const objectId = (ctx?.objectId || drafts.draftObjectId).trim();
  if (!objectType || !objectId) {
    return "缺少精确的业务对象类型和真实对象标识；禁止使用演示对象";
  }
  if (objectId.toLowerCase() === "wo-1001") {
    return "演示对象已禁用；请提供真实业务对象";
  }
  return null;
}

export function buildToolsInvokePayload(
  ctx: ToolsInvokeContext | null,
  drafts: { draftObjectType: string; draftObjectId: string },
): { objectType: string; objectId: string; taskId?: string; agentRunId?: string } | null {
  if (toolsInvokeBlocker(ctx, drafts)) return null;
  const objectType = (ctx?.objectType || drafts.draftObjectType).trim();
  const objectId = (ctx?.objectId || drafts.draftObjectId).trim();
  const payload: {
    objectType: string;
    objectId: string;
    taskId?: string;
    agentRunId?: string;
  } = { objectType, objectId };
  if (ctx?.taskId) payload.taskId = ctx.taskId;
  if (ctx?.agentRunId) payload.agentRunId = ctx.agentRunId;
  return payload;
}

export function validateExactObjectQueryResult(
  response: unknown,
  expectedObjectId: string,
): string | null {
  const result = (response as { result?: { items?: Array<{ id?: unknown }>; total?: unknown } } | null)?.result;
  const items = Array.isArray(result?.items) ? result.items : null;
  if (!items || items.length !== 1 || Number(result?.total) !== 1) {
    return "对象查询未返回唯一精确对象；本次试跑不计为成功";
  }
  if (String(items[0]?.id || "") !== expectedObjectId) {
    return "对象查询回包与请求的真实对象标识不一致";
  }
  return null;
}
