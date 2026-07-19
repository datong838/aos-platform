export type HealthPart = "up" | "down" | "unknown";

export type HealthState = {
  dify: HealthPart;
  openocta: HealthPart;
  adapter: HealthPart;
};

export type OverallHealth = "green" | "red" | "yellow";

export function aggregateHealth(h: HealthState): OverallHealth {
  // v0.1: OpenOcta 尚未强制探测，unknown 不参与红绿判定
  const critical = [h.dify, h.adapter];
  if (critical.some((p) => p === "down")) return "red";
  if (critical.every((p) => p === "up")) return "green";
  return "yellow";
}

export type Citation = {
  doc_name: string;
  page?: number | null;
  snippet?: string;
  score?: number | null;
};

export type AskStatus = "ok" | "no_hit" | "error";

export type AskResponse = {
  trace_id: string;
  answer: string;
  citations: Citation[];
  status: AskStatus;
  refuse_reason?: string | null;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  status?: AskStatus;
  citations?: Citation[];
  trace_id?: string;
  refuse_reason?: string | null;
};

export function appendUserMessage(
  messages: ChatMessage[],
  question: string,
  id: string
): ChatMessage[] {
  return [...messages, { id, role: "user", content: question }];
}

export function appendAssistantFromAsk(
  messages: ChatMessage[],
  resp: AskResponse,
  id: string
): ChatMessage[] {
  let content = resp.answer;
  if (resp.status === "no_hit" && !content) {
    content = "知识库中未命中相关内容，请换一种问法或补充文档后再试。";
  }
  if (resp.status === "error" && !content) {
    content = "服务暂时不可用，请检查本机 Docker / 模型配置后重试。";
  }
  return [
    ...messages,
    {
      id,
      role: "assistant",
      content,
      status: resp.status,
      citations: resp.citations || [],
      trace_id: resp.trace_id,
      refuse_reason: resp.refuse_reason,
    },
  ];
}

export function citationsForPanel(messages: ChatMessage[]): Citation[] {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.role === "assistant" && m.citations && m.citations.length) {
      return m.citations;
    }
  }
  return [];
}

export function buildAskBody(
  question: string,
  objectId?: string | null
): {
  question: string;
  channel: string;
  user: { id: string; display_name: string };
  meta?: { object_id: string };
} {
  const body: {
    question: string;
    channel: string;
    user: { id: string; display_name: string };
    meta?: { object_id: string };
  } = {
    question,
    channel: "desktop",
    user: { id: "local", display_name: "业务用户" },
  };
  if (objectId) body.meta = { object_id: objectId };
  return body;
}

export const TOKENS = {
  bgApp: "rgb(2, 6, 23)",
  bgPanel: "rgba(15, 23, 42, 0.92)",
  border: "rgba(255,255,255,0.08)",
  textTitle: "#f3f4f6",
  textBody: "#9ca3af",
  textMuted: "#6b7280",
  accent: "rgb(34, 211, 238)",
  accentBuddy: "#fcd34d",
} as const;
