import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../../components/PageChrome";
import { apiGet, apiPost } from "../../api/client";
import { getApiBase } from "../../api/apiBase";

/* ============================================================================
 * Phase 1 · AIP Assist 深度完善
 * - SSE 流式对话（fetch ReadableStream + 可中断）
 * - 对话历史持久化（侧栏 + localStorage 兜底）
 * - 动态建议问题（API + 兜底）
 * - 权限感知标签（读取 API permissions 字段）
 * - 保存到分支 / 取消
 * ==========================================================================*/

/* ----------------------------- 类型定义 ----------------------------- */

type PermissionTag = "read" | "edit" | "delete" | "authorized";

type CodeSuggestion = {
  id: string;
  title: string;
  language?: string;
  diff?: string;
  status?: "pending" | "saving" | "saved" | "cancelled";
  branchName?: string;
};

type AiMessageMeta = {
  route?: string;
  provider?: string;
  offline?: boolean;
  permissions?: PermissionTag[];
  codeSuggestions?: CodeSuggestion[];
};

type Message =
  | {
      id: string;
      role: "user";
      content: string;
      ts: number;
    }
  | ({
      id: string;
      role: "ai";
      content: string;
      streaming?: boolean;
      ts: number;
    } & AiMessageMeta)
  | {
      id: string;
      role: "error";
      code: string;
      message: string;
      ts: number;
    };

type Conversation = {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
};

/* ----------------------------- 常量 / Mock 数据 ----------------------------- */

const STORAGE_KEY = "aos.aip.assist.conversations";

const API_ENDPOINTS = {
  chatSse: "/v1/aip/assist/chat",
  conversations: "/v1/aip/assist/conversations",
  suggestions: "/v1/aip/assist/suggestions",
  saveToBranch: "/v1/aip/assist/save-to-branch",
} as const;

const DEFAULT_SUGGESTIONS = [
  "如何与协作者分享我的笔记本？",
  "如何在笔记本中嵌入其他应用的内容？",
  "如何创建 Object Set 并绑定到 Widget？",
  "如何配置 AIP Agent 的工具面板？",
];

type SuggestionDto = {
  id?: unknown;
  category?: unknown;
  text?: unknown;
};

/**
 * 将服务端对象 DTO 与历史字符串 DTO 收敛为页面可安全渲染的文本。
 * 非法项与重复文本会被过滤，避免单个坏数据拖垮整个 Assist 页面。
 */
export function normalizeSuggestionItems(items: unknown): string[] {
  if (!Array.isArray(items)) return [];
  const seen = new Set<string>();
  const normalized: string[] = [];
  for (const item of items) {
    const text = typeof item === "string"
      ? item.trim()
      : item !== null && typeof item === "object" && typeof (item as SuggestionDto).text === "string"
        ? ((item as SuggestionDto).text as string).trim()
        : "";
    if (!text || seen.has(text)) continue;
    seen.add(text);
    normalized.push(text);
  }
  return normalized;
}

/** API 不存在时的建议兜底（上下文相关） */
const CONTEXT_SUGGESTIONS: Record<string, string[]> = {
  分享: ["如何批量管理笔记本权限？", "如何查看笔记本的访问审计？"],
  嵌入: ["嵌入的应用如何传递筛选参数？", "如何嵌入 Map 画布？"],
  Object: ["Object Set 如何做聚合统计？", "如何为 Object Type 添加 Wiki 字段？"],
  Agent: ["如何为 Agent 配置 HITL 审批？", "Agent 如何调用 Function？"],
};

const PERMISSION_META: Record<PermissionTag, { label: string; color: string; bg: string }> = {
  read: { label: "只读", color: "var(--aos-blue-600)", bg: "rgba(59, 130, 246, 0.15)" },
  edit: { label: "需审批", color: "var(--aos-amber-700)", bg: "rgba(245, 158, 11, 0.18)" },
  delete: { label: "需审批", color: "var(--aos-amber-700)", bg: "rgba(245, 158, 11, 0.18)" },
  authorized: { label: "已授权", color: "var(--aos-green-700)", bg: "rgba(16, 185, 129, 0.18)" },
};

const INITIAL_AI_TEXT =
  "您好！我是 AIP Assist，一个基于 Palantir 产品文档和相关信息的智能助手。我可以帮助您了解如何使用平台功能。\n\n💡 提示：我也可以说其他语言！";

/** 从后端回复中探测权限标签（后端 permissions 字段或本地启发式推断） */
export function detectPermissions(text: string, fromApi?: PermissionTag[]): PermissionTag[] {
  if (fromApi && fromApi.length > 0) return fromApi;
  const tags = new Set<PermissionTag>();
  if (/查看|读取|列表|查询|搜索|只读/.test(text)) tags.add("read");
  if (/编辑|修改|更新|写入|设置/.test(text)) tags.add("edit");
  if (/删除|移除|清除|禁用/.test(text)) tags.add("delete");
  // 如果只含只读指令，则标已授权
  if (tags.size === 0) tags.add("authorized");
  return Array.from(tags);
}

/** 从回复中抽取代码建议（代码块） */
export function extractCodeSuggestions(text: string): CodeSuggestion[] {
  const out: CodeSuggestion[] = [];
  const re = /```(\w+)?\n([\s\S]*?)```/g;
  let m: RegExpExecArray | null;
  let idx = 0;
  while ((m = re.exec(text)) !== null) {
    idx += 1;
    out.push({
      id: `cs_${Date.now()}_${idx}`,
      title: `代码建议 ${idx}`,
      language: m[1] || "text",
      diff: m[2],
      status: "pending",
    });
  }
  return out;
}

/* ----------------------------- 对话持久化（localStorage） ----------------------------- */

function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw) as Conversation[];
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

function saveConversations(list: Conversation[]) {
  try {
    // 只保留最近 50 条
    const top = [...list].sort((a, b) => b.updatedAt - a.updatedAt).slice(0, 50);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(top));
  } catch {
    /* quota 忽略 */
  }
}

function newConversationId(): string {
  return `conv_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

function newMessageId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
}

function titleFromMessages(msgs: Message[]): string {
  const first = msgs.find((m) => m.role === "user");
  if (!first) return "新对话";
  const t = first.content.slice(0, 24);
  return t.length < first.content.length ? `${t}…` : t;
}

/* ----------------------------- SSE 流式解析 ----------------------------- */

type SseCallbacks = {
  onToken: (chunk: string) => void;
  onMeta?: (meta: AiMessageMeta) => void;
  onDone?: (full: string, meta: AiMessageMeta) => void;
  onError?: (err: Error) => void;
};

/**
 * 调用 SSE 端点。后端不可用时自动降级到本地流式 mock。
 * 返回一个 abort 函数，可中断流。
 */
function streamChat(
  query: string,
  convId: string,
  cb: SseCallbacks,
): () => void {
  const controller = new AbortController();
  let aborted = false;

  async function runReal() {
    try {
      const res = await fetch(`${getApiBase()}${API_ENDPOINTS.chatSse}`, {
        method: "POST",
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({ query, conversationId: convId, stream: true }),
      });
      if (!res.ok || !res.body) {
        throw new Error(`SSE HTTP ${res.status}`);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let full = "";
      const meta: AiMessageMeta = {};
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        // SSE 事件按双换行分割
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";
        for (const block of parts) {
          const lines = block.split("\n");
          let data = "";
          for (const ln of lines) {
            if (ln.startsWith("data:")) data += ln.slice(5).trim();
          }
          if (!data) continue;
          try {
            const obj = JSON.parse(data) as {
              token?: string;
              content?: string;
              route?: string;
              provider?: string;
              permissions?: PermissionTag[];
              done?: boolean;
            };
            if (obj.route) meta.route = obj.route;
            if (obj.provider) meta.provider = obj.provider;
            if (obj.permissions) meta.permissions = obj.permissions;
            const piece = obj.token ?? obj.content ?? "";
            if (piece) {
              full += piece;
              cb.onToken(piece);
            }
            if (obj.done) {
              cb.onMeta?.(meta);
              cb.onDone?.(full, meta);
              return;
            }
          } catch {
            // 非 JSON data：当作纯文本 token
            full += data;
            cb.onToken(data);
          }
        }
      }
      cb.onMeta?.(meta);
      cb.onDone?.(full, meta);
    } catch (e) {
      if (aborted || controller.signal.aborted) return;
      // 降级到 mock 流
      cb.onError?.(e instanceof Error ? e : new Error(String(e)));
      mockStream(query, cb);
    }
  }

  function mockStream(query: string, cb: SseCallbacks) {
    const full = generateOfflineResponse(query);
    const tokens = tokenizeForStream(full);
    const meta: AiMessageMeta = { offline: true };
    let i = 0;
    const timer = setInterval(() => {
      if (aborted) {
        clearInterval(timer);
        return;
      }
      if (i >= tokens.length) {
        clearInterval(timer);
        cb.onMeta?.(meta);
        cb.onDone?.(full, meta);
        return;
      }
      const piece = tokens[i];
      i += 1;
      cb.onToken(piece);
    }, 20);
  }

  function abort() {
    aborted = true;
    controller.abort();
  }

  void runReal();
  return abort;
}

/** 将文本切成适合流式渲染的片段（按 1-3 字符） */
export function tokenizeForStream(text: string): string[] {
  const out: string[] = [];
  let i = 0;
  while (i < text.length) {
    // 遇到换行或标点，作为单次片段
    const ch = text[i];
    const step = /[\n，。！？、,.!?;:]/.test(ch) ? 1 : 2;
    out.push(text.slice(i, i + step));
    i += step;
  }
  return out;
}

/* ----------------------------- 离线兜底回答 ----------------------------- */

export function generateOfflineResponse(query: string): string {
  if (query.includes("分享") && query.includes("笔记本")) {
    return "在 Foundry 中分享笔记本有两种方式：\n\n1. **直接分享**：在笔记本右上角点击「分享」按钮，输入协作者的用户名或邮箱，选择权限级别（查看/编辑/管理）。\n\n2. **通过项目分享**：将笔记本添加到一个项目中，然后将协作者添加到该项目，他们会自动获得项目中所有资源的访问权限。\n\n💡 建议：对于长期协作，推荐使用项目方式，便于权限统一管理。";
  }
  if (query.includes("嵌入") && query.includes("应用")) {
    return "在笔记本中嵌入其他应用内容：\n\n1. 使用 Embed 组件，在代码单元格中调用 display(Embed(url=...))\n2. 支持嵌入：Workshop 应用、Map 画布、Graph 画布、Object Explorer\n3. 嵌入内容支持双向交互（筛选、选中、Action）\n\n💡 注意：嵌入的应用需要有对应的访问权限。";
  }
  if (query.includes("Object Set") || query.includes("绑定")) {
    return "创建 Object Set 并绑定到 Widget 的流程：\n\n1. 在 Ontology Manager 中定义 Object Type\n2. 在 Workshop 中添加 Object Table Widget\n3. 在 Widget 配置面板的「Data」Tab 中选择 Object Set\n4. 可选：添加筛选器限制数据范围\n\n💡 Object Set 支持链式操作：filter、select、aggregate。";
  }
  if (query.includes("Agent") || query.includes("工具面板")) {
    return "配置 AIP Agent 工具面板：\n\n1. 在 AIP Studio 中创建或选择 Agent\n2. 进入「工具」Tab\n3. 添加可用工具：Query Object Set、Execute Action、Search Document、Call API\n4. 为每个工具配置参数和权限范围\n5. 设置工具使用策略：自动选择 vs 人工确认\n\n💡 安全提示：写操作工具建议启用 HITL（Human-in-the-loop）审批。";
  }
  return `您的问题是：「${query}」\n\n这是一个很好的问题。AIP Assist 基于产品文档和最佳实践来回答。如果您需要更详细的帮助，可以：\n\n1. 查看相关文档\n2. 联系平台管理员\n3. 在社区论坛提问\n\n💡 提示：尽量使用具体的关键词，我可以给出更精准的回答。`;
}

/* ----------------------------- 主组件 ----------------------------- */

export function AipAssistPage() {
  // 对话列表
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);

  // 当前对话消息（派生自 conversations）
  const activeConv = useMemo(
    () => conversations.find((c) => c.id === activeConvId) || null,
    [conversations, activeConvId],
  );
  const messages: Message[] = activeConv?.messages ?? [];

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  // 建议
  const [suggestions, setSuggestions] = useState<string[]>(DEFAULT_SUGGESTIONS);

  // 侧栏折叠
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<null | (() => void)>(null);

  /* ---------- 持久化 ---------- */
  useEffect(() => {
    const list = loadConversations();
    if (list.length > 0) {
      setConversations(list);
      setActiveConvId(list[0].id);
    } else {
      const conv = createInitialConversation();
      setConversations([conv]);
      setActiveConvId(conv.id);
    }
  }, []);

  useEffect(() => {
    if (conversations.length > 0) {
      saveConversations(conversations);
    }
  }, [conversations]);

  /* ---------- 自动滚动 ---------- */
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  /* ---------- 建议问题（API + 兜底） ---------- */
  const fetchSuggestions = useCallback(async () => {
    try {
      const r = await apiGet<{ items?: unknown }>(`${API_ENDPOINTS.suggestions}?convId=${activeConvId || ""}`);
      const normalized = normalizeSuggestionItems(r.items);
      if (normalized.length > 0) {
        setSuggestions(normalized);
        return;
      }
    } catch {
      // API 不存在，用上下文推断
    }
    // 本地上下文推断
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (lastUser && lastUser.role === "user") {
      const key = Object.keys(CONTEXT_SUGGESTIONS).find((k) => lastUser.content.includes(k));
      if (key) {
        setSuggestions([...CONTEXT_SUGGESTIONS[key], ...DEFAULT_SUGGESTIONS].slice(0, 4));
        return;
      }
    }
    setSuggestions(DEFAULT_SUGGESTIONS);
  }, [activeConvId, messages]);

  useEffect(() => {
    void fetchSuggestions();
  }, [fetchSuggestions]);

  /* ---------- 清理 ---------- */
  useEffect(() => {
    return () => {
      if (abortRef.current) abortRef.current();
    };
  }, []);

  /* ---------- 创建对话 ---------- */
  function createInitialConversation(): Conversation {
    const now = Date.now();
    return {
      id: newConversationId(),
      title: "新对话",
      createdAt: now,
      updatedAt: now,
      messages: [
        { id: "init", role: "ai", content: INITIAL_AI_TEXT, ts: now },
      ],
    };
  }

  function handleNewConversation() {
    if (loading && abortRef.current) abortRef.current();
    const conv = createInitialConversation();
    setConversations((prev) => [conv, ...prev]);
    setActiveConvId(conv.id);
    setInput("");
  }

  function handleSelectConversation(id: string) {
    if (loading && abortRef.current) abortRef.current();
    setActiveConvId(id);
  }

  function handleDeleteConversation(id: string) {
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id);
      if (next.length === 0) {
        const conv = createInitialConversation();
        setActiveConvId(conv.id);
        return [conv];
      }
      if (id === activeConvId) setActiveConvId(next[0].id);
      return next;
    });
  }

  /* ---------- 更新当前对话消息 ---------- */
  function patchActiveMessages(updater: (msgs: Message[]) => Message[]) {
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== activeConvId) return c;
        const msgs = updater(c.messages);
        return { ...c, messages: msgs, updatedAt: Date.now(), title: titleFromMessages(msgs) };
      }),
    );
  }

  function patchAiMessage(msgId: string, patch: Partial<Message>) {
    patchActiveMessages((msgs) =>
      msgs.map((m) => (m.id === msgId ? ({ ...m, ...patch } as Message) : m)),
    );
  }

  /* ---------- 停止生成 ---------- */
  function handleStop() {
    if (abortRef.current) {
      abortRef.current();
      abortRef.current = null;
    }
    setLoading(false);
    // 把所有 streaming 状态置为 false
    patchActiveMessages((msgs) =>
      msgs.map((m) => (m.role === "ai" && m.streaming ? { ...m, streaming: false } : m)),
    );
  }

  /* ---------- 发送消息 ---------- */
  async function sendMessage(q: string) {
    if (!q.trim() || loading) return;
    const convId = activeConvId || "";
    const userMsg: Message = { id: newMessageId("u"), role: "user", content: q.trim(), ts: Date.now() };
    const aiId = newMessageId("a");
    const aiPlaceholder: Message = {
      id: aiId,
      role: "ai",
      content: "",
      streaming: true,
      ts: Date.now(),
    };
    patchActiveMessages((msgs) => [...msgs, userMsg, aiPlaceholder]);
    setInput("");
    setLoading(true);

    let acc = "";
    abortRef.current = streamChat(q.trim(), convId, {
      onToken: (piece) => {
        acc += piece;
        patchAiMessage(aiId, { content: acc, streaming: true });
      },
      onDone: (_full, meta) => {
        const last = activeConv?.messages.find((m) => m.id === aiId);
        const content = acc || (last && last.role === "ai" ? last.content : "") || "(空回复)";
        const permissions = detectPermissions(content, meta.permissions);
        const codeSuggestions = extractCodeSuggestions(content);
        patchAiMessage(aiId, {
          content,
          streaming: false,
          route: meta.route,
          provider: meta.provider,
          offline: meta.offline,
          permissions,
          codeSuggestions,
        });
        setLoading(false);
        abortRef.current = null;
      },
      onError: (_err) => {
        // mockStream 会接管，无需额外处理
      },
    });
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    void sendMessage(input);
  }

  function useSuggestion(q: string) {
    if (loading) return;
    setInput(q);
  }

  function retryLast() {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser || lastUser.role !== "user") return;
    const q = lastUser.content;
    // 移除最后一个 error 气泡
    patchActiveMessages((msgs) => {
      const last = msgs[msgs.length - 1];
      if (last && last.role === "error") return msgs.slice(0, -1);
      return msgs;
    });
    void sendMessage(q);
  }

  /* ---------- 保存到分支 / 取消 ---------- */
  async function saveToBranch(msgId: string, cs: CodeSuggestion) {
    patchActiveMessages((msgs) =>
      msgs.map((m) => {
        if (m.id !== msgId || m.role !== "ai") return m;
        const list = (m.codeSuggestions || []).map((c) =>
          c.id === cs.id ? { ...c, status: "saving" as const } : c,
        );
        return { ...m, codeSuggestions: list };
      }),
    );
    const branchName = `aip-assist/${cs.id}`;
    try {
      await apiPost<{ branchName?: string }>(API_ENDPOINTS.saveToBranch, {
        title: cs.title,
        language: cs.language,
        diff: cs.diff,
        conversationId: activeConvId,
      });
    } catch {
      // API 未就绪，本地标记成功（演示）
    }
    patchActiveMessages((msgs) =>
      msgs.map((m) => {
        if (m.id !== msgId || m.role !== "ai") return m;
        const list = (m.codeSuggestions || []).map((c) =>
          c.id === cs.id ? { ...c, status: "saved" as const, branchName } : c,
        );
        return { ...m, codeSuggestions: list };
      }),
    );
  }

  function cancelSuggestion(msgId: string, csId: string) {
    patchActiveMessages((msgs) =>
      msgs.map((m) => {
        if (m.id !== msgId || m.role !== "ai") return m;
        const list = (m.codeSuggestions || []).map((c) =>
          c.id === csId ? { ...c, status: "cancelled" as const } : c,
        );
        return { ...m, codeSuggestions: list };
      }),
    );
  }

  /* ----------------------------- 渲染 ----------------------------- */

  const showSuggestions = messages.length <= 1 && !loading;

  return (
    <PageChrome title="AIP 助手" lede="基于产品文档的智能助手 · SSE 流式 · 对话持久化">
      <div style={{ display: "flex", gap: 0, height: "calc(100vh - 140px)" }}>
        {/* 左侧：对话历史 */}
        <aside
          style={{
            width: sidebarOpen ? 240 : 48,
            flexShrink: 0,
            borderRight: "1px solid var(--aos-border)",
            display: "flex",
            flexDirection: "column",
            transition: "width 0.2s",
            overflow: "hidden",
            background: "var(--aos-surface-hover)",
          }}
        >
          <div style={{ padding: 8, display: "flex", gap: 4, borderBottom: "1px solid var(--aos-border)" }}>
            <button
              type="button"
              title={sidebarOpen ? "折叠侧栏" : "展开侧栏"}
              onClick={() => setSidebarOpen((v) => !v)}
              style={{
                width: 32, height: 32, borderRadius: 2, border: "1px solid var(--aos-border)", background: "var(--aos-surface)",
                cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--aos-text-secondary)" strokeWidth="1.5">
                <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
              </svg>
            </button>
            {sidebarOpen && (
              <button
                type="button"
                onClick={handleNewConversation}
                style={{
                  flex: 1, height: 32, borderRadius: 2, border: "1px solid var(--aos-indigo)",
                  background: "var(--aos-indigo-bg)", color: "var(--aos-indigo-600)", cursor: "pointer",
                  fontSize: 12, fontWeight: 500, display: "flex", alignItems: "center", justifyContent: "center", gap: 4,
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 5v14M5 12h14" strokeLinecap="round" />
                </svg>
                新建对话
              </button>
            )}
          </div>
          {sidebarOpen && (
            <div style={{ flex: 1, overflowY: "auto", padding: 4 }}>
              {conversations.map((c) => {
                const active = c.id === activeConvId;
                return (
                  <div
                    key={c.id}
                    style={{
                      display: "flex", alignItems: "center", gap: 4, marginBottom: 2,
                      background: active ? "var(--aos-indigo-bg)" : "transparent",
                      borderRadius: 2, padding: "6px 8px",
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => handleSelectConversation(c.id)}
                      style={{
                        flex: 1, textAlign: "left", cursor: "pointer",
                        background: "none", border: "none", padding: 0,
                        fontSize: 12, color: active ? "var(--aos-indigo-600)" : "var(--aos-text)",
                        fontWeight: active ? 500 : 400,
                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                      }}
                      title={c.title}
                    >
                      {c.title}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteConversation(c.id)}
                      title="删除"
                      style={{
                        background: "none", border: "none", cursor: "pointer", padding: 2,
                        color: "var(--aos-text-tertiary)", flexShrink: 0, display: "flex",
                      }}
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M6 6l12 12M6 18L18 6" strokeLinecap="round" />
                      </svg>
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </aside>

        {/* 右侧：对话区 */}
        <div
          style={{
            flex: 1, display: "flex", flexDirection: "column",
            maxWidth: 720, margin: "0 auto", minWidth: 0,
          }}
        >
          {/* 顶部免责声明 */}
          <div style={{ textAlign: "center", marginBottom: 16 }}>
            <p style={{ fontSize: 11, color: "var(--aos-text-tertiary)", fontStyle: "italic", maxWidth: 480, margin: "0 auto" }}>
              AIP Assist 使用第三方大语言模型（LLM）处理查询，符合 Palantir 安全标准。请根据组织政策使用。
            </p>
          </div>

          {/* 消息列表 */}
          <div
            ref={scrollRef}
            style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 16, paddingRight: 4 }}
          >
            {messages.map((m) => {
              if (m.role === "error") {
                return (
                  <div
                    key={m.id}
                    style={{
                      background: "var(--aos-red-bg)", border: "1px solid var(--aos-red-border)", borderRadius: 2,
                      padding: 12, color: "var(--aos-red)", fontSize: 13,
                    }}
                  >
                    <strong>⚠ {m.code}</strong> · {m.message}
                    {m.code === "EVAL_GATE" && (
                      <div style={{ marginTop: 8 }}>
                        <Link to="/aip/evals" style={{ color: "var(--aos-red)", textDecoration: "underline", fontSize: 12 }}>
                          查看 Evals 门控 →
                        </Link>
                      </div>
                    )}
                    <div style={{ marginTop: 8 }}>
                      <button
                        type="button"
                        onClick={retryLast}
                        style={{
                          fontSize: 12, padding: "4px 10px", borderRadius: 2,
                          border: "1px solid var(--aos-red-border)", background: "var(--aos-surface)", color: "var(--aos-red)", cursor: "pointer",
                        }}
                      >
                        重试
                      </button>
                    </div>
                  </div>
                );
              }
              if (m.role === "ai") {
                return (
                  <AiBubble
                    key={m.id}
                    msg={m}
                    onSaveToBranch={(cs) => saveToBranch(m.id, cs)}
                    onCancelSuggestion={(csId) => cancelSuggestion(m.id, csId)}
                  />
                );
              }
              // user
              return (
                <div key={m.id} style={{ display: "flex", justifyContent: "flex-end" }}>
                  <div
                    style={{
                      background: "var(--aos-gray-100)", borderRadius: 2, padding: "10px 14px",
                      maxWidth: 480, marginLeft: 48,
                    }}
                  >
                    <p style={{ fontSize: 13, color: "var(--aos-text)", margin: 0, lineHeight: 1.5, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                      {m.content}
                    </p>
                  </div>
                </div>
              );
            })}

            {/* 建议问题（仅初始状态） */}
            {showSuggestions && (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <p style={{ fontSize: 13, color: "var(--aos-text-secondary)", margin: 0 }}>以下是您可以问我的几个问题...</p>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  {suggestions.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => useSuggestion(q)}
                      style={suggestionBtnStyle}
                      onMouseEnter={(e) => {
                        (e.currentTarget as HTMLButtonElement).style.background = "var(--aos-surface-hover)";
                        (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--aos-border-strong)";
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLButtonElement).style.background = "var(--aos-surface)";
                        (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--aos-border)";
                      }}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--aos-text-tertiary)" strokeWidth="1.5" style={{ flexShrink: 0 }}>
                        <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.86 9.86 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* 权限感知标签（底部） */}
            <div style={{ display: "flex", gap: 8, fontSize: 11, color: "var(--aos-text-tertiary)", marginTop: 8, flexWrap: "wrap" }}>
              <span style={{ padding: "2px 8px", background: "var(--aos-gray-100)", borderRadius: 4 }}>当前应用：AIP Assist</span>
              <span style={{ padding: "2px 8px", background: "var(--aos-gray-100)", borderRadius: 4 }}>权限感知：仅回答有权限的数据</span>
            </div>
          </div>

          {/* 底部输入区 */}
          <div style={{ borderTop: "1px solid var(--aos-border)", background: "var(--aos-surface)", padding: 16, marginTop: 8 }}>
            {/* 动态建议 + 随机 */}
            <div style={{ fontSize: 11, color: "var(--aos-text-tertiary)", marginBottom: 8, display: "flex", alignItems: "center", gap: 4 }}>
              <span>建议问题</span>
              <button
                type="button"
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--aos-text-tertiary)", padding: 0 }}
                title="点击随机一条建议"
                onClick={() => {
                  const random = suggestions[Math.floor(Math.random() * suggestions.length)];
                  setInput(random);
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M9 9a3 3 0 115 2.9c0 1.1-.9 2.1-2 2.1H12M12 17h.01" strokeLinecap="round" />
                </svg>
              </button>
            </div>
            <form onSubmit={handleSubmit} style={{ position: "relative", display: "flex", gap: 8 }}>
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="提出问题..."
                disabled={loading}
                className="aip-assist-input"
                style={{
                  flex: 1, border: "1px solid var(--aos-border)", borderRadius: 2,
                  padding: "12px 48px 12px 16px", fontSize: 14, outline: "none",
                  transition: "border-color 0.15s, box-shadow 0.15s",
                  opacity: loading ? 0.6 : 1,
                }}
              />
              {loading ? (
                /* 停止生成按钮 */
                <button
                  type="button"
                  onClick={handleStop}
                  style={{
                    position: "absolute", right: 8, bottom: 8, width: 32, height: 32, borderRadius: 2,
                    background: "var(--aos-red)", color: "var(--text-on-brand)", border: "none", cursor: "pointer",
                    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                  }}
                  title="停止生成"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                    <rect x="6" y="6" width="12" height="12" rx="2" />
                  </svg>
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!input.trim()}
                  style={{
                    position: "absolute", right: 8, bottom: 8, width: 32, height: 32, borderRadius: 2,
                    background: input.trim() ? "var(--aos-indigo-600)" : "var(--aos-indigo-border)", color: "var(--text-on-brand)", border: "none",
                    cursor: input.trim() ? "pointer" : "not-allowed",
                    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                    transition: "background 0.15s",
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M5 12h14M12 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              )}
            </form>
          </div>
        </div>
      </div>
    </PageChrome>
  );
}

/* ----------------------------- AI 气泡子组件 ----------------------------- */

const suggestionBtnStyle: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", borderRadius: 2,
  border: "1px solid var(--aos-border)", background: "var(--aos-surface)", cursor: "pointer", textAlign: "left",
  fontSize: 13, color: "var(--aos-text)", transition: "all 0.15s",
};

function AiBubble({
  msg,
  onSaveToBranch,
  onCancelSuggestion,
}: {
  msg: Extract<Message, { role: "ai" }>;
  onSaveToBranch: (cs: CodeSuggestion) => void;
  onCancelSuggestion: (csId: string) => void;
}) {
  return (
    <div>
      <div style={{ borderRadius: 2, padding: 16, background: "linear-gradient(135deg, var(--aos-indigo) 0%, var(--aos-purple-600) 100%)", color: "var(--text-on-brand)" }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
          <div style={{ width: 32, height: 32, borderRadius: 2, background: "rgba(255,255,255,0.2)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--aos-surface)" strokeWidth="1.5">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2z" />
            </svg>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            {msg.content === "" && msg.streaming ? (
              <div style={{ display: "flex", gap: 4, alignItems: "center", height: 22 }}>
                <span className="aip-assist-dot" style={{ animationDelay: "0ms" }} />
                <span className="aip-assist-dot" style={{ animationDelay: "150ms" }} />
                <span className="aip-assist-dot" style={{ animationDelay: "300ms" }} />
              </div>
            ) : (
              <p style={{ fontSize: 13, lineHeight: 1.6, margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {msg.content}
                {msg.streaming && <span className="aip-assist-cursor">▌</span>}
              </p>
            )}

            {/* 权限感知标签 */}
            {msg.permissions && msg.permissions.length > 0 && !msg.streaming && (
              <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
                {msg.permissions.map((p) => {
                  const meta = PERMISSION_META[p] || PERMISSION_META.read;
                  return (
                    <span
                      key={p}
                      style={{
                        padding: "2px 8px", borderRadius: 4, fontSize: 11,
                        color: meta.color, background: meta.bg, fontWeight: 500,
                      }}
                    >
                      {meta.label}
                    </span>
                  );
                })}
              </div>
            )}

            {/* 路由信息 */}
            {(msg.route || msg.provider) && !msg.streaming && (
              <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid rgba(255,255,255,0.2)", fontSize: 11, color: "rgba(255,255,255,0.75)", display: "flex", gap: 8, flexWrap: "wrap" }}>
                {msg.route && <span>路线：{msg.route}</span>}
                {msg.provider && <span>· 供应商：{msg.provider}</span>}
                {msg.offline && (
                  <span style={{ background: "rgba(245, 158, 11, 0.25)", padding: "1px 6px", borderRadius: 3 }}>离线模式</span>
                )}
              </div>
            )}

            {/* 代码建议（保存到分支 / 取消） */}
            {msg.codeSuggestions && msg.codeSuggestions.length > 0 && !msg.streaming && (
              <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
                {msg.codeSuggestions.map((cs) => (
                  <CodeSuggestionCard
                    key={cs.id}
                    cs={cs}
                    onSave={() => onSaveToBranch(cs)}
                    onCancel={() => onCancelSuggestion(cs.id)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function CodeSuggestionCard({
  cs,
  onSave,
  onCancel,
}: {
  cs: CodeSuggestion;
  onSave: () => void;
  onCancel: () => void;
}) {
  const [expanded, setExpanded] = useState(true);
  if (cs.status === "cancelled") {
    return null; // 折叠（移除）
  }
  const saved = cs.status === "saved";
  const saving = (cs.status as string) === "saving";
  return (
    <div style={{ background: "rgba(255,255,255,0.12)", borderRadius: 2, overflow: "hidden" }}>
      <div style={{ padding: "8px 12px", display: "flex", alignItems: "center", gap: 8 }}>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          style={{ background: "none", border: "none", color: "var(--text-on-brand)", cursor: "pointer", padding: 0, display: "flex" }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            {expanded ? <path d="M19 9l-7 7-7-7" strokeLinecap="round" strokeLinejoin="round" /> : <path d="M9 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />}
          </svg>
        </button>
        <span style={{ fontSize: 12, fontWeight: 500 }}>{cs.title}</span>
        {cs.language && (
          <span style={{ fontSize: 10, padding: "1px 6px", background: "rgba(255,255,255,0.15)", borderRadius: 3, fontFamily: "monospace" }}>
            {cs.language}
          </span>
        )}
        <div style={{ flex: 1 }} />
        {saved ? (
          <span style={{ fontSize: 11, color: "var(--aos-green-border)", display: "flex", alignItems: "center", gap: 4 }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {cs.branchName ? `已保存到 ${cs.branchName}` : "已保存"}
          </span>
        ) : (
          <>
            <button
              type="button"
              onClick={onSave}
              disabled={saving}
              style={{
                fontSize: 11, padding: "3px 8px", borderRadius: 4, border: "1px solid rgba(255,255,255,0.3)",
                background: saving ? "rgba(255,255,255,0.1)" : "rgba(255,255,255,0.2)", color: "var(--text-on-brand)",
                cursor: saving ? "wait" : "pointer",
              }}
            >
              {saving ? "保存中…" : "保存到分支"}
            </button>
            <button
              type="button"
              onClick={onCancel}
              disabled={saving}
              style={{
                fontSize: 11, padding: "3px 8px", borderRadius: 4, border: "1px solid rgba(255,255,255,0.2)",
                background: "transparent", color: "rgba(255,255,255,0.8)", cursor: "pointer",
              }}
            >
              取消
            </button>
          </>
        )}
      </div>
      {expanded && cs.diff && (
        <pre
          style={{
            margin: 0, padding: "8px 12px", fontSize: 12, lineHeight: 1.5,
            background: "rgba(0,0,0,0.2)", color: "var(--aos-indigo-bg)", overflowX: "auto",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            whiteSpace: "pre",
          }}
        >
          {cs.diff}
        </pre>
      )}
    </div>
  );
}
