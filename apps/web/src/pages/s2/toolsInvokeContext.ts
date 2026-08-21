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
    return "缺少 exact 对象上下文（objectType + objectId）；禁止使用演示 wo-1001";
  }
  if (objectId.toLowerCase() === "wo-1001") {
    return "演示对象 wo-1001 已禁用；请提供真实对象 exact";
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
