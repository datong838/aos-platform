import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { aipAgentControl } from "../api/aipAgentControl";
import { apiGet, apiPost, apiPut } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import { templateDisplayName } from "../lib/aipChineseLabels";

type AgentItem = {
  id: string;
  name: string;
  category: string;
  level: string;
  levelLabel: string;
  status: "running" | "draft" | "stopped";
  toolCount: number;
  iconBg: string;
  iconColor: string;
  iconPath: string;
};

export function toggleToolId(enabledIds: string[], toolId: string): string[] {
  return enabledIds.includes(toolId)
    ? enabledIds.filter((id) => id !== toolId)
    : [...enabledIds, toolId];
}

export function formatStudioSaveMsg(ok: boolean, detail?: string): string {
  if (!ok) return `写入已提交但重读核验失败${detail ? ` · ${detail}` : ""}`;
  return `已保存并完成重读核验${detail ? ` · ${detail}` : ""}`;
}

type ApiAgent = {
  id?: string;
  name?: string;
  description?: string;
  source?: string;
  tags?: string[];
  status?: string;
  calls?: number;
  /** Canonical AgentInstance fields (AIP-6). */
  instanceId?: string;
  overlay?: {
    displayName?: string | null;
    allowedCapabilityIds?: string[];
  };
  template?: {
    assetId?: string;
  };
};

type StudioTool = {
  id: string;
  name: string;
  category: string;
  enabled: boolean;
};

export function mapApiAgentToStudio(agent: ApiAgent): AgentItem {
  const id = String(agent.instanceId || agent.id || "");
  const rawStatus = String(agent.status || "");
  const status: AgentItem["status"] =
    rawStatus === "draft" || rawStatus === "provisioning"
      ? "draft"
      : rawStatus === "archived" || rawStatus === "suspended" || rawStatus === "deleted"
        ? "stopped"
        : "running";
  const level = agent.tags?.find((tag) => /^L[0-4]$/.test(tag)) || "L2";
  const category =
    agent.tags?.find((tag) => !/^L[0-4]$/.test(tag)) ||
    (agent.template?.assetId ? templateDisplayName(agent.template.assetId) : null) ||
    agent.source ||
    "未分类";
  return {
    id,
    name: String(agent.overlay?.displayName || agent.name || id || "未命名智能体"),
    category,
    level,
    levelLabel: `${level} · API`,
    status,
    toolCount: 0,
    iconBg: "var(--aos-indigo-bg)",
    iconColor: "var(--aos-indigo-600)",
    iconPath: "M21 11.5a8.5 8.5 0 01-8.5 8.5H5l-3 3V11.5A8.5 8.5 0 0110.5 3h2A8.5 8.5 0 0121 11.5z",
  };
}

export function studioOverlayBlockedMessage(error: unknown): string | null {
  const code = (error as { body?: { code?: string } } | null)?.body?.code;
  if (code !== "AIP_CANONICAL_OVERLAY_NOT_IMPLEMENTED") return null;
  return "提示词/工具 overlay 尚未实现版本化权威契约（AIP_CANONICAL_OVERLAY_NOT_IMPLEMENTED）。本页不读写假配置；请到「智能体列表」查看实例状态，后续门完成后再编辑。";
}

export function sameToolIds(left: string[], right: string[]): boolean {
  return [...new Set(left)].sort().join("\u0000") === [...new Set(right)].sort().join("\u0000");
}

export function validatePromptResponse(
  response: { ok?: boolean; agent_id?: string; prompt?: string } | null | undefined,
  agentId: string,
  prompt: string,
): boolean {
  return response?.ok === true && response.agent_id === agentId && response.prompt === prompt;
}

export function validateAgentToolsResponse(
  response: { agent_id?: string; items?: Array<{ id?: string }> } | null | undefined,
  agentId: string,
  toolIds: string[],
): boolean {
  return response?.agent_id === agentId && sameToolIds((response.items || []).map((item) => String(item.id || "")), toolIds);
}

export function validateGuardrailsResponse(
  response: { agent_id?: string; items?: Array<{ id?: string; enabled?: boolean }> } | null | undefined,
  agentId: string,
  enabledIds: string[],
): boolean {
  if (response?.agent_id !== agentId) return false;
  const actual = (response.items || []).filter((item) => item.enabled !== false).map((item) => String(item.id || ""));
  return sameToolIds(actual, enabledIds);
}

export const STUDIO_GUARDRAIL_CATALOG = [
  { id: "no_fs_write", name: "禁止写文件系统" },
  { id: "no_fork", name: "禁止进程分叉" },
  { id: "token_limit", name: "强制 Token 上限" },
  { id: "auto_draft", name: "外呼默认进 Draft" },
] as const;

const STUDIO_TABS = [
  { id: "prompt", label: "提示词" },
  { id: "tools", label: "工具箱" },
  { id: "guardrails", label: "护栏" },
  { id: "try", label: "试运行" },
  { id: "publish", label: "发布" },
];


function statusBadge(status: AgentItem["status"]) {
  if (status === "running") return { label: "运行中", bg: "var(--aos-green-bg)", color: "var(--aos-green-700)" };
  if (status === "draft") return { label: "Draft", bg: "var(--aos-amber-bg)", color: "var(--aos-amber-700)" };
  return { label: "已停用", bg: "var(--aos-gray-100)", color: "var(--aos-text-secondary)" };
}

export function StudioPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState("prompt");
  const [agents, setAgents] = useState<AgentItem[]>([]);
  const [activeId, setActiveId] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [enabledTools, setEnabledTools] = useState<string[]>([]);
  const [toolCatalog, setToolCatalog] = useState<StudioTool[]>([]);
  const [loadState, setLoadState] = useState<"loading" | "live" | "error">("loading");
  const [resourceError, setResourceError] = useState<string | null>(null);
  const [defaultModel, setDefaultModel] = useState("—");
  const [lastRoute, setLastRoute] = useState<string | null>(null);
  const [query, setQuery] = useState("ORD-8821 超时了，怎么派？");
  const [answer, setAnswer] = useState("");
  const [toolCalls, setToolCalls] = useState<unknown[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [promptSaveMsg, setPromptSaveMsg] = useState<string | null>(null);
  const [toolsSaveMsg, setToolsSaveMsg] = useState<string | null>(null);
  const [guardrailsSaveMsg, setGuardrailsSaveMsg] = useState<string | null>(null);
  const [promptSaving, setPromptSaving] = useState(false);
  const [toolsSaving, setToolsSaving] = useState(false);
  const [guardrailsSaving, setGuardrailsSaving] = useState(false);
  const [enabledGuardrails, setEnabledGuardrails] = useState<string[]>(
    STUDIO_GUARDRAIL_CATALOG.map((item) => item.id),
  );
  const [overlayBlocked, setOverlayBlocked] = useState(false);
  const [installOpen, setInstallOpen] = useState(false);
  const [installBusy, setInstallBusy] = useState(false);
  const [installMsg, setInstallMsg] = useState<string | null>(null);
  const loadGeneration = useRef(0);
  const activeAgent = agents.find((a) => a.id === activeId) || null;
  const displayAgent: AgentItem = activeAgent || {
    id: "", name: "未选择智能体", category: "—", level: "—", levelLabel: "—", status: "stopped", toolCount: 0,
    iconBg: "var(--aos-gray-100)", iconColor: "var(--aos-text-secondary)", iconPath: "",
  };
  const selectedTools = enabledTools;
  const selectedToolItems = useMemo(() => toolCatalog.filter((tool) => enabledTools.includes(tool.id)), [enabledTools, toolCatalog]);

  async function refreshAgents() {
    const response = await apiGet<{ items?: ApiAgent[] }>("/v1/aip/agents");
    const next = (response.items || []).map(mapApiAgentToStudio).filter((agent) => agent.id);
    setAgents(next);
    const fromUrl = String(searchParams.get("instance") || "").trim();
    setActiveId((current) => {
      if (fromUrl && next.some((agent) => agent.id === fromUrl)) return fromUrl;
      if (current && next.some((agent) => agent.id === current)) return current;
      return next[0]?.id || "";
    });
    setLoadState("live");
    setResourceError(null);
    return next;
  }

  useEffect(() => {
    if (!activeId) return;
    const current = String(searchParams.get("instance") || "").trim();
    if (current === activeId) return;
    const next = new URLSearchParams(searchParams);
    next.set("instance", activeId);
    setSearchParams(next, { replace: true });
  }, [activeId, searchParams, setSearchParams]);

  useEffect(() => {
    const fromUrl = String(searchParams.get("instance") || "").trim();
    if (!fromUrl || !agents.some((agent) => agent.id === fromUrl)) return;
    if (fromUrl !== activeId) setActiveId(fromUrl);
  }, [searchParams, agents, activeId]);

  useEffect(() => {
    let cancelled = false;
    refreshAgents()
      .catch((error) => {
        if (cancelled) return;
        setAgents([]);
        setActiveId("");
        setLoadState("error");
        setResourceError(String((error as Error).message || error));
      });
    apiGet<{ defaultTextModel?: string }>("/v1/aip/models")
      .then((r) => { if (!cancelled) setDefaultModel(r.defaultTextModel || "—"); })
      .catch(() => { if (!cancelled) setDefaultModel("—"); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!activeId) {
      setSystemPrompt("");
      setEnabledTools([]);
      setEnabledGuardrails(STUDIO_GUARDRAIL_CATALOG.map((item) => item.id));
      setOverlayBlocked(false);
      return;
    }
    const generation = ++loadGeneration.current;
    setSystemPrompt("");
    setEnabledTools([]);
    setEnabledGuardrails(STUDIO_GUARDRAIL_CATALOG.map((item) => item.id));
    setPromptSaveMsg(null);
    setToolsSaveMsg(null);
    setGuardrailsSaveMsg(null);
    setResourceError(null);
    setOverlayBlocked(false);
    Promise.all([
      apiGet<{ agent_id?: string; prompt?: string }>(`/v1/aip/agents/${encodeURIComponent(activeId)}/prompt`),
      apiGet<{ agent_id?: string; items?: StudioTool[] }>(`/v1/aip/agents/${encodeURIComponent(activeId)}/tools`),
      apiGet<{ agent_id?: string; items?: Array<{ id?: string; enabled?: boolean }> }>(`/v1/aip/agents/${encodeURIComponent(activeId)}/guardrails`),
      apiGet<{ items?: Array<{ id?: string; name?: string; kind?: string }> }>("/v1/aip/tools"),
    ]).then(([prompt, assigned, guardrails, catalog]) => {
      if (generation !== loadGeneration.current) return;
      if (prompt.agent_id !== activeId || assigned.agent_id !== activeId || guardrails.agent_id !== activeId) {
        throw new Error("Agent 资源响应目标错配");
      }
      setSystemPrompt(String(prompt.prompt || ""));
      const assignedItems = assigned.items || [];
      setEnabledTools(assignedItems.map((tool) => tool.id));
      const catalogItems = (catalog.items || []).filter((tool) => tool.id).map((tool) => ({
        id: String(tool.id), name: String(tool.name || tool.id), category: String(tool.kind || "tool"), enabled: true,
      }));
      const catalogIds = new Set(catalogItems.map((tool) => tool.id));
      setToolCatalog([
        ...catalogItems,
        ...assignedItems.filter((tool) => !catalogIds.has(tool.id)).map((tool) => ({
          id: tool.id, name: tool.name || tool.id, category: tool.category || "tool", enabled: tool.enabled !== false,
        })),
      ]);
      const saved = guardrails.items || [];
      if (saved.length === 0) {
        setEnabledGuardrails(STUDIO_GUARDRAIL_CATALOG.map((item) => item.id));
      } else {
        setEnabledGuardrails(saved.filter((item) => item.enabled !== false).map((item) => String(item.id || "")).filter(Boolean));
      }
      setAgents((prev) => prev.map((agent) => agent.id === activeId ? { ...agent, toolCount: assignedItems.length } : agent));
      setOverlayBlocked(false);
    }).catch((error) => {
      if (generation !== loadGeneration.current) return;
      const blocked = studioOverlayBlockedMessage(error);
      setOverlayBlocked(Boolean(blocked));
      setResourceError(blocked || `Agent 配置加载失败：${String((error as Error).message || error)}`);
    });
  }, [activeId]);

  async function savePrompt() {
    if (promptSaving || !activeId || overlayBlocked) return;
    const targetId = activeId;
    const snapshot = systemPrompt;
    setPromptSaving(true);
    setPromptSaveMsg(null);
    setErr(null);
    try {
      const written = await apiPut<{ ok?: boolean; agent_id?: string; prompt?: string }>(`/v1/aip/agents/${encodeURIComponent(targetId)}/prompt`, {
        prompt: snapshot,
      });
      if (!validatePromptResponse(written, targetId, snapshot)) throw new Error("Prompt 写回响应与目标不一致");
      let reread: { agent_id?: string; prompt?: string };
      try {
        reread = await apiGet(`/v1/aip/agents/${encodeURIComponent(targetId)}/prompt`);
      } catch (error) {
        setPromptSaveMsg(formatStudioSaveMsg(false, String((error as Error).message || error)));
        return;
      }
      if (reread.agent_id !== targetId || reread.prompt !== snapshot) {
        setPromptSaveMsg(formatStudioSaveMsg(false, "服务端 Prompt 不一致"));
        return;
      }
      if (activeId === targetId) setSystemPrompt(reread.prompt);
      setPromptSaveMsg(formatStudioSaveMsg(true, "agents/prompt"));
    } catch (ex) {
      setPromptSaveMsg(`保存失败 · ${String((ex as Error).message || ex).slice(0, 120)}`);
    } finally {
      setPromptSaving(false);
    }
  }

  async function saveTools() {
    if (toolsSaving || !activeId || overlayBlocked) return;
    const targetId = activeId;
    const snapshot = [...enabledTools];
    setToolsSaving(true);
    setToolsSaveMsg(null);
    setErr(null);
    try {
      const written = await apiPut<{ agent_id?: string; items?: Array<{ id?: string }> }>(`/v1/aip/agents/${encodeURIComponent(targetId)}/tools`, {
        items: selectedToolItems.map((tool) => ({ id: tool.id, name: tool.name, category: tool.category, enabled: true })),
      });
      if (!validateAgentToolsResponse(written, targetId, snapshot)) throw new Error("Tools 写回响应与目标不一致");
      let reread: { agent_id?: string; items?: Array<{ id?: string }> };
      try {
        reread = await apiGet(`/v1/aip/agents/${encodeURIComponent(targetId)}/tools`);
      } catch (error) {
        setToolsSaveMsg(formatStudioSaveMsg(false, String((error as Error).message || error)));
        return;
      }
      if (!validateAgentToolsResponse(reread, targetId, snapshot)) {
        setToolsSaveMsg(formatStudioSaveMsg(false, "服务端 Tools 不一致"));
        return;
      }
      setToolsSaveMsg(formatStudioSaveMsg(true, "agents/{id}/tools"));
    } catch (ex) {
      setToolsSaveMsg(`保存失败 · ${String((ex as Error).message || ex).slice(0, 120)}`);
    } finally {
      setToolsSaving(false);
    }
  }

  async function saveGuardrails() {
    if (guardrailsSaving || !activeId || overlayBlocked) return;
    const targetId = activeId;
    const snapshot = [...enabledGuardrails];
    setGuardrailsSaving(true);
    setGuardrailsSaveMsg(null);
    setErr(null);
    try {
      const items = STUDIO_GUARDRAIL_CATALOG.map((item) => ({
        id: item.id,
        name: item.name,
        enabled: snapshot.includes(item.id),
      }));
      const written = await apiPut<{ agent_id?: string; items?: Array<{ id?: string; enabled?: boolean }> }>(
        `/v1/aip/agents/${encodeURIComponent(targetId)}/guardrails`,
        { items },
      );
      if (!validateGuardrailsResponse(written, targetId, snapshot)) throw new Error("Guardrails 写回响应与目标不一致");
      let reread: { agent_id?: string; items?: Array<{ id?: string; enabled?: boolean }> };
      try {
        reread = await apiGet(`/v1/aip/agents/${encodeURIComponent(targetId)}/guardrails`);
      } catch (error) {
        setGuardrailsSaveMsg(formatStudioSaveMsg(false, String((error as Error).message || error)));
        return;
      }
      if (!validateGuardrailsResponse(reread, targetId, snapshot)) {
        setGuardrailsSaveMsg(formatStudioSaveMsg(false, "服务端护栏不一致"));
        return;
      }
      setGuardrailsSaveMsg(formatStudioSaveMsg(true, "agents/{id}/guardrails"));
    } catch (ex) {
      setGuardrailsSaveMsg(`保存失败 · ${String((ex as Error).message || ex).slice(0, 120)}`);
    } finally {
      setGuardrailsSaving(false);
    }
  }

  async function installEcommercePack() {
    if (installBusy) return;
    setInstallBusy(true);
    setInstallMsg(null);
    try {
      await aipAgentControl.installEcommerce(`studio-install-${crypto.randomUUID()}`);
      const next = await refreshAgents();
      setInstallMsg(`安装完成 · 当前列表 ${next.length} 个实例`);
      setInstallOpen(false);
    } catch (ex) {
      setInstallMsg(`安装失败 · ${String((ex as Error).message || ex).slice(0, 160)}`);
    } finally {
      setInstallBusy(false);
    }
  }

  async function onChat(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setAnswer("");
    setToolCalls([]);
    setLastRoute(null);
    try {
      const res = await apiPost<{
        answer: string;
        toolCalls: unknown[];
        route?: string;
        provider?: string;
      }>("/v1/aip/chat", {
        query: `【System】${systemPrompt}\n\n【User】${query}`,
        withTools: selectedTools.length > 0,
        tools: selectedTools,
      });
      setAnswer(res.answer);
      setLastRoute(`${res.route || "?"} · ${res.provider || "?"}`);
      setToolCalls(res.toolCalls || []);
      setTab("try");
    } catch (ex) {
      setErr(String((ex as Error).message || ex));
    }
  }

  return (
    <PageChrome title="对话机器人 Studio" lede="配置壳：提示词 · 工具 · 本体/Wiki 上下文；L4 须 Evals 绿且 Draft 默认，不伪造发布通过。">
      <div
        data-testid="studio-ops-stats"
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, marginBottom: 12 }}
      >
        {[
          { label: "智能体数", value: String(agents.length) },
          { label: "当前", value: activeAgent?.name ? activeAgent.name.slice(0, 10) : "未选" },
          { label: "状态", value: activeAgent?.status || "—" },
          { label: "工具开", value: String(enabledTools.length) },
          { label: "页签", value: tab },
          { label: "加载", value: loadState === "live" ? "Live" : loadState === "error" ? "Error" : "…" },
        ].map((s) => (
          <div key={s.label} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{s.value}</div>
          </div>
        ))}
      </div>
      {resourceError && loadState === "live" && <p role="alert">{resourceError}</p>}
      <div
        style={{
          margin: "-20px -20px -24px",
          display: "flex",
          minHeight: "calc(100vh - 140px)",
        }}
      >
        {/* 左侧：智能体列表 */}
        <div
          style={{
            width: 256,
            flexShrink: 0,
            borderRight: "1px solid var(--aos-border)",
            background: "var(--aos-surface)",
            overflowY: "auto",
          }}
        >
          <div
            style={{
              padding: 12,
              borderBottom: "1px solid var(--aos-gray-100)",
            }}
          >
            <div style={{ fontSize: 14, fontWeight: 500, color: "var(--aos-text)" }}>智能体列表</div>
            <button
              type="button"
              data-testid="studio-btn-new-agent"
              title="打开组织安装向导（SolutionPack）；不解封自由创建 Agent API"
              onClick={() => { setInstallOpen((open) => !open); setInstallMsg(null); }}
              style={{
                marginTop: 8,
                width: "100%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 6,
                padding: "8px 12px",
                borderRadius: 2,
                background: "var(--aos-indigo-600)",
                color: "var(--text-on-brand)",
                border: "none",
                fontSize: 13,
                fontWeight: 500,
                cursor: "pointer",
                boxSizing: "border-box",
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 5v14M5 12h14" strokeLinecap="round" />
              </svg>
              安装数字同事…
            </button>
            {installOpen && (
              <div
                data-testid="studio-install-wizard"
                style={{
                  marginTop: 10,
                  padding: 10,
                  border: "1px solid var(--aos-border)",
                  borderRadius: 2,
                  background: "var(--aos-surface-hover)",
                  fontSize: 12,
                  color: "var(--aos-text-secondary)",
                }}
              >
                <p style={{ margin: "0 0 8px" }}>
                  权威入口是电商六数字同事 SolutionPack 组织安装，不是自由创建 Agent。
                </p>
                <button
                  type="button"
                  className="btn primary"
                  data-testid="studio-install-ecommerce"
                  disabled={installBusy}
                  onClick={() => void installEcommercePack()}
                  style={{ width: "100%", marginBottom: 8 }}
                >
                  {installBusy ? "安装中…" : "安装电商六数字同事"}
                </button>
                <Link to="/aip/agent-registry" data-testid="studio-install-registry-link" style={{ fontSize: 12 }}>
                  打开智能体目录查看就绪度 →
                </Link>
                {installMsg && <p role="status" style={{ margin: "8px 0 0" }}>{installMsg}</p>}
              </div>
            )}
          </div>

          {loadState === "error" && <p role="alert" style={{ padding: 12 }}>Agent 列表加载失败：{resourceError}</p>}
          {loadState === "live" && agents.length === 0 && <p data-testid="studio-agents-empty" style={{ padding: 12 }}>暂无智能体</p>}

          {agents.map((a) => {
            const active = a.id === activeId;
            const sb = statusBadge(a.status);
            return (
              <div
                key={a.id}
                onClick={() => setActiveId(a.id)}
                style={{
                  padding: 12,
                  borderBottom: "1px solid var(--aos-surface-hover)",
                  cursor: "pointer",
                  background: active ? "var(--aos-indigo-bg)" : "var(--aos-surface)",
                  borderLeft: active ? "2px solid var(--aos-indigo)" : "2px solid transparent",
                  transition: "background 0.15s",
                }}
              >
                <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 2,
                      background: a.iconBg,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={a.iconColor} strokeWidth="1.5">
                      {a.id === "repair-buddy" && (
                        <path
                          d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      )}
                      {a.id === "video-agent" && (
                        <>
                          <rect x="3" y="5" width="18" height="14" rx="1" />
                          <path d="M3 10h18M9 10v9M15 10v9" />
                        </>
                      )}
                      {a.id === "risk-agent" && (
                        <>
                          <path d="M12 9v4M12 17h.01" strokeLinecap="round" />
                          <path
                            d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </>
                      )}
                      {a.id === "order-agent" && (
                        <path
                          d="M21 11.5a8.5 8.5 0 01-8.5 8.5H5l-3 3V11.5A8.5 8.5 0 0110.5 3h2A8.5 8.5 0 0121 11.5z"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      )}
                      {a.id === "doc-agent" && (
                        <>
                          <path
                            d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"
                            strokeLinejoin="round"
                          />
                          <path d="M14 2v6h6" strokeLinejoin="round" />
                          <path d="M16 13H8M16 17H8M10 9H8" strokeLinecap="round" />
                        </>
                      )}
                    </svg>
                  </div>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 500,
                        color: "var(--aos-text)",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {a.name}
                    </div>
                    <div style={{ fontSize: 10, color: "var(--aos-text-secondary)", marginTop: 2 }}>
                      {a.levelLabel} · {sb.label}
                    </div>
                    <div style={{ display: "flex", gap: 4, marginTop: 4 }}>
                      <span
                        style={{
                          padding: "1.5px 6px",
                          borderRadius: 4,
                          fontSize: 9,
                          background: sb.bg,
                          color: sb.color,
                          fontWeight: 500,
                        }}
                      >
                        {sb.label}
                      </span>
                      <span
                        style={{
                          padding: "1.5px 6px",
                          borderRadius: 4,
                          fontSize: 9,
                          background: "var(--aos-gray-100)",
                          color: "var(--aos-text-secondary)",
                        }}
                      >
                        {a.toolCount} 工具
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* 右侧：详情 */}
        <div style={{ flex: 1, overflowY: "auto", minWidth: 0 }}>
          <div style={{ maxWidth: 768, margin: "0 auto", padding: 24 }}>
            {/* Agent 标题 */}
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16 }}>
              <div>
                <h1 style={{ fontSize: 20, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>
                  {displayAgent.name}
                </h1>
                <p style={{ fontSize: 13, color: "var(--aos-text-secondary)", margin: "4px 0 0", lineHeight: 1.5 }}>
                  配置壳：提示词 · 工具 · 本体/Wiki 上下文 · L4 须 Evals 绿 + Draft 默认
                </p>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span
                  style={{
                    padding: "2px 8px",
                    borderRadius: 4,
                    fontSize: 10,
                    background: "var(--aos-green-bg)",
                    color: "var(--aos-green-700)",
                    fontWeight: 500,
                  }}
                >
                  运行中
                </span>
                <span
                  style={{
                    padding: "2px 8px",
                    borderRadius: 4,
                    fontSize: 10,
                    background: "var(--aos-amber-bg)",
                    color: "var(--aos-amber-700)",
                    fontWeight: 500,
                  }}
                >
                  {displayAgent.levelLabel}
                </span>
              </div>
            </div>

            {/* Tab 导航 */}
            <div style={{ borderBottom: "1px solid var(--aos-border)", marginBottom: 16 }}>
              <div style={{ display: "flex", gap: 24 }}>
                {STUDIO_TABS.map((t) => {
                  const active = tab === t.id;
                  return (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => setTab(t.id)}
                      style={{
                        padding: "10px 0",
                        fontSize: 13,
                        fontWeight: active ? 500 : 400,
                        color: active ? "var(--aos-indigo-600)" : "var(--aos-text-secondary)",
                        background: "none",
                        border: "none",
                        borderBottom: active ? "2px solid var(--aos-indigo-600)" : "2px solid transparent",
                        cursor: "pointer",
                      }}
                    >
                      {t.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Tab: 提示词 */}
            {tab === "prompt" && (
              <div
                style={{
                  borderRadius: 2,
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-surface)",
                  padding: 20,
                }}
              >
                <label style={{ display: "block", fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 8, fontWeight: 500 }}>
                  系统提示词 (System Prompt) <span style={{ color: "var(--aos-red)" }}>*</span>
                </label>
                <textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  rows={7}
                  aria-label="system-prompt"
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    fontSize: 13,
                    borderRadius: 2,
                    border: "1px solid var(--aos-border)",
                    background: "var(--aos-surface-hover)",
                    color: "var(--aos-text)",
                    resize: "vertical",
                    lineHeight: 1.6,
                    fontFamily: "inherit",
                    boxSizing: "border-box",
                  }}
                />
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
                  <span
                    style={{
                      padding: "3px 8px",
                      borderRadius: 4,
                      border: "1px solid var(--aos-purple-600)",
                      color: "var(--aos-purple-600)",
                      fontSize: 10,
                    }}
                  >
                    /Order.status
                  </span>
                  <span
                    style={{
                      padding: "3px 8px",
                      borderRadius: 4,
                      border: "1px solid var(--aos-amber-border)",
                      color: "var(--aos-amber-600)",
                      fontSize: 10,
                    }}
                  >
                    /Wiki.sla
                  </span>
                  <span
                    style={{
                      padding: "3px 8px",
                      borderRadius: 4,
                      border: "1px solid var(--aos-amber-border)",
                      color: "var(--aos-amber-700)",
                      fontSize: 10,
                    }}
                  >
                    模型路由 → {defaultModel}
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 14 }}>
                  <button
                    type="button"
                    className="w2-b2-save-btn"
                    onClick={() => void savePrompt()}
                    disabled={promptSaving || !activeAgent || overlayBlocked}
                    style={{
                      padding: "8px 16px",
                      borderRadius: 2,
                      background: promptSaving ? "var(--aos-gray-100)" : "var(--aos-indigo-600)",
                      color: promptSaving ? "var(--aos-text-secondary)" : "var(--text-on-brand)",
                      border: "none",
                      fontSize: 13,
                      fontWeight: 500,
                      cursor: promptSaving ? "not-allowed" : "pointer",
                    }}
                  >
                    {promptSaving ? "保存中…" : "保存提示词"}
                  </button>
                  {promptSaveMsg && (
                    <span className="w2-b2-save-msg" style={{ fontSize: 12, color: "var(--aos-green-700)" }}>
                      {promptSaveMsg}
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Tab: 工具箱 */}
            {tab === "tools" && (
              <div
                style={{
                  borderRadius: 2,
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-surface)",
                  padding: 20,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: "var(--aos-text)" }}>已启用工具</div>
                  <span style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>
                    已选 {enabledTools.length} / {toolCatalog.length}
                  </span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {toolCatalog.length === 0 && <p data-testid="studio-tools-empty">暂无可用工具</p>}
                  {toolCatalog.map((t) => {
                    const isWarn = t.category === "action";
                    const isWiki = t.category === "wiki";
                    const on = enabledTools.includes(t.id);
                    return (
                      <label
                        key={t.id}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "10px 12px",
                          borderRadius: 2,
                          border: `1px solid ${isWarn ? "var(--aos-amber-border)" : isWiki ? "var(--aos-amber-border)" : "var(--aos-border)"}`,
                          background: isWarn ? "var(--aos-amber-bg)" : isWiki ? "var(--aos-amber-bg)" : "var(--aos-surface)",
                          cursor: "pointer",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                          <input
                            type="checkbox"
                            checked={on}
                            onChange={() => setEnabledTools((prev) => toggleToolId(prev, t.id))}
                            aria-label={`tool-${t.id}`}
                          />
                          <div>
                            <span style={{ fontSize: 13, color: "var(--aos-text)", fontWeight: 500 }}>{t.name}</span>
                            <span style={{ marginLeft: 8, fontSize: 10, color: isWarn ? "var(--aos-amber-700)" : "var(--aos-text-secondary)" }}>
                              {t.category}
                            </span>
                          </div>
                        </div>
                        <span
                          style={{
                            padding: "2px 8px",
                            borderRadius: 4,
                            fontSize: 11,
                            background: on
                              ? isWarn
                                ? "var(--aos-amber-bg)"
                                : isWiki
                                  ? "var(--aos-amber-bg)"
                                  : "var(--aos-green-bg)"
                              : "var(--aos-gray-100)",
                            color: on
                              ? isWarn
                                ? "var(--aos-amber-700)"
                                : isWiki
                                  ? "var(--aos-amber-700)"
                                  : "var(--aos-green-700)"
                              : "var(--aos-text-secondary)",
                            fontWeight: 500,
                          }}
                        >
                          {on ? "已分配" : "未分配"}
                        </span>
                      </label>
                    );
                  })}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 14 }}>
                  <button
                    type="button"
                    className="w2-b2-save-btn"
                    onClick={() => void saveTools()}
                    disabled={toolsSaving || !activeAgent || overlayBlocked}
                    style={{
                      padding: "8px 16px",
                      borderRadius: 2,
                      background: toolsSaving ? "var(--aos-gray-100)" : "var(--aos-indigo-600)",
                      color: toolsSaving ? "var(--aos-text-secondary)" : "var(--text-on-brand)",
                      border: "none",
                      fontSize: 13,
                      fontWeight: 500,
                      cursor: toolsSaving ? "not-allowed" : "pointer",
                    }}
                  >
                    {toolsSaving ? "保存中…" : "保存工具配置"}
                  </button>
                  {toolsSaveMsg && (
                    <span className="w2-b2-save-msg" style={{ fontSize: 12, color: "var(--aos-green-700)" }}>
                      {toolsSaveMsg}
                    </span>
                  )}
                </div>
                <div style={{ paddingTop: 12, marginTop: 12, borderTop: "1px solid var(--aos-gray-100)" }}>
                  <p data-testid="studio-overlay-authority" style={{ fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 8 }}>
                    工具权威：AgentInstance Overlay（与 `/aip/tools` 同一真源 · W-T8）
                  </p>
                  <Link
                    to={activeId ? `/aip/tools?instance=${encodeURIComponent(activeId)}` : "/aip/tools"}
                    data-testid="studio-to-tools-link"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "6px 12px",
                      borderRadius: 2,
                      background: "var(--aos-indigo-bg)",
                      color: "var(--aos-indigo-600)",
                      fontSize: 12,
                      fontWeight: 500,
                      textDecoration: "none",
                    }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path
                        d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    打开完整工具面板
                  </Link>
                </div>
                {err && <p style={{ color: "var(--aos-red)", fontSize: 12, marginTop: 12 }}>{err}</p>}
              </div>
            )}

            {tab === "guardrails" && (
              <div
                data-testid="studio-guardrails-panel"
                style={{
                  borderRadius: 2,
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-surface)",
                  padding: 20,
                }}
              >
                <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>运行护栏</h3>
                <p style={{ margin: "0 0 16px", fontSize: 12, color: "var(--aos-text-secondary)" }}>
                  租户作用域版本化配置；空初值表示尚未写入 overlay，默认勾选推荐项。
                </p>
                <div style={{ display: "grid", gap: 10 }}>
                  {STUDIO_GUARDRAIL_CATALOG.map((item) => (
                    <label key={item.id} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13 }}>
                      <input
                        type="checkbox"
                        checked={enabledGuardrails.includes(item.id)}
                        disabled={overlayBlocked || !activeAgent}
                        onChange={() => setEnabledGuardrails((prev) => toggleToolId(prev, item.id))}
                      />
                      <span>{item.name}</span>
                      <code style={{ fontSize: 11, color: "var(--aos-text-secondary)" }}>{item.id}</code>
                    </label>
                  ))}
                </div>
                <div style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "center" }}>
                  <button
                    type="button"
                    data-testid="studio-save-guardrails"
                    disabled={guardrailsSaving || !activeAgent || overlayBlocked}
                    onClick={() => void saveGuardrails()}
                    style={{
                      padding: "8px 14px",
                      borderRadius: 2,
                      border: "none",
                      background: guardrailsSaving ? "var(--aos-gray-100)" : "var(--aos-indigo-600)",
                      color: guardrailsSaving ? "var(--aos-text-secondary)" : "var(--text-on-brand)",
                      fontSize: 13,
                      fontWeight: 500,
                      cursor: guardrailsSaving ? "not-allowed" : "pointer",
                    }}
                  >
                    {guardrailsSaving ? "保存中…" : "保存护栏"}
                  </button>
                  {guardrailsSaveMsg && <span style={{ fontSize: 12 }}>{guardrailsSaveMsg}</span>}
                </div>
              </div>
            )}

            {/* Tab: 试运行 */}
            {tab === "try" && (
              <div
                style={{
                  borderRadius: 2,
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-surface)",
                  padding: 20,
                }}
              >
                <div
                  style={{
                    borderRadius: 2,
                    background: "var(--aos-surface-hover)",
                    border: "1px solid var(--aos-border)",
                    padding: 12,
                    fontSize: 13,
                    lineHeight: 1.6,
                  }}
                >
                  <div style={{ color: "var(--aos-blue-600)", fontSize: 11, fontWeight: 500, marginBottom: 4 }}>用户</div>
                  <div style={{ color: "var(--aos-text)" }}>{query}</div>
                  <div style={{ color: "var(--aos-amber-600)", fontSize: 11, fontWeight: 500, marginTop: 12, marginBottom: 4 }}>
                    Buddy
                  </div>
                  <div style={{ color: "var(--aos-text)" }}>
                    {answer || "尚未运行；发送后仅展示真实 API 回包。"}
                  </div>
                  {lastRoute && (
                    <div style={{ fontSize: 10, color: "var(--aos-text-tertiary)", marginTop: 8 }}>
                      路由：{lastRoute}
                    </div>
                  )}
                </div>
                <form
                  onSubmit={onChat}
                  style={{ display: "flex", gap: 8, marginTop: 12 }}
                >
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    style={{
                      flex: 1,
                      padding: "8px 12px",
                      fontSize: 13,
                      borderRadius: 2,
                      border: "1px solid var(--aos-border)",
                      background: "var(--aos-surface)",
                    }}
                    placeholder="输入测试问题…"
                  />
                  <button
                    type="submit"
                    style={{
                      padding: "8px 16px",
                      borderRadius: 2,
                      background: "var(--aos-indigo-600)",
                      color: "var(--text-on-brand)",
                      border: "none",
                      fontSize: 13,
                      fontWeight: 500,
                      cursor: "pointer",
                    }}
                  >
                    发送
                  </button>
                </form>
                {err && <p style={{ color: "var(--aos-red)", fontSize: 12, marginTop: 8 }}>{err}</p>}
                <Link
                  to="/aip/assist"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    marginTop: 12,
                    fontSize: 12,
                    color: "var(--aos-blue-600)",
                    textDecoration: "none",
                  }}
                >
                  在工作台预览 Buddy 组件 →
                </Link>
                {toolCalls.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)", marginBottom: 8 }}>
                      工具调用
                    </div>
                    <table
                      style={{
                        width: "100%",
                        fontSize: 11,
                        borderCollapse: "collapse",
                        borderRadius: 2,
                        overflow: "hidden",
                        border: "1px solid var(--aos-border)",
                      }}
                    >
                      <thead>
                        <tr style={{ background: "var(--aos-surface-hover)", textAlign: "left" }}>
                          <th style={{ padding: "6px 10px", fontWeight: 500, color: "var(--aos-text-secondary)", fontSize: 10 }}>工具</th>
                          <th style={{ padding: "6px 10px", fontWeight: 500, color: "var(--aos-text-secondary)", fontSize: 10 }}>状态</th>
                          <th style={{ padding: "6px 10px", fontWeight: 500, color: "var(--aos-text-secondary)", fontSize: 10 }}>详情</th>
                        </tr>
                      </thead>
                      <tbody>
                        {toolCalls.map((tc, i) => {
                          const t = tc as Record<string, unknown>;
                          return (
                            <tr key={i} style={{ borderTop: "1px solid var(--aos-gray-100)" }}>
                              <td style={{ padding: "6px 10px", fontFamily: "monospace" }}>
                                {String(t.id || t.tool || `#${i + 1}`)}
                              </td>
                              <td style={{ padding: "6px 10px" }}>{String(t.status || "—")}</td>
                              <td style={{ padding: "6px 10px" }}>{String(t.summary || t.result || "—")}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* Tab: 发布 */}
            {tab === "publish" && (
              <div
                style={{
                  borderRadius: 2,
                  border: "1px solid var(--aos-amber-border)",
                  background: "var(--aos-amber-bg)",
                  padding: 20,
                }}
              >
                <h2 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-amber-700)", margin: "0 0 8px" }}>
                  L4 门控状态
                </h2>
                <p style={{ fontSize: 12, color: "var(--aos-amber-700)", margin: "0 0 12px", lineHeight: 1.6 }}>
                  须 Eval ≥ 92% 且 Draft 审批通过后方可申请 L4 上线。87% 为产品示意数据，本页只读，不代表当前 Agent 的真实评测结果。
                </p>
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    fontSize: 12,
                    color: "var(--aos-amber-700)",
                    opacity: 0.6,
                    cursor: "not-allowed",
                  }}
                >
                  <input type="checkbox" disabled style={{ width: 14, height: 14 }} />
                  启用无人值守写回（L4）
                </label>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 16 }}>
                  <Link
                    to="/aip/evals"
                    style={{
                      padding: "6px 12px",
                      borderRadius: 2,
                      background: "var(--aos-surface)",
                      border: "1px solid var(--aos-amber-border)",
                      color: "var(--aos-amber-700)",
                      fontSize: 12,
                      textDecoration: "none",
                      fontWeight: 500,
                    }}
                  >
                    去跑 Evals →
                  </Link>
                  <Link
                    to="/aip/drafts"
                    style={{
                      padding: "6px 12px",
                      borderRadius: 2,
                      background: "var(--aos-surface)",
                      border: "1px solid var(--aos-amber-border)",
                      color: "var(--aos-amber-700)",
                      fontSize: 12,
                      textDecoration: "none",
                      fontWeight: 500,
                    }}
                  >
                    Draft 审批台 →
                  </Link>
                  <Link
                    to="/aip/maturity"
                    style={{
                      padding: "6px 12px",
                      borderRadius: 2,
                      background: "var(--aos-surface)",
                      border: "1px solid var(--aos-amber-border)",
                      color: "var(--aos-amber-700)",
                      fontSize: 12,
                      textDecoration: "none",
                      fontWeight: 500,
                    }}
                  >
                    成熟度楼梯 →
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

    </PageChrome>
  );
}
