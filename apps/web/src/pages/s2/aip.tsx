import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiGet, apiPost, apiPut, apiDelete, S2Chrome, useJsonGet } from "./shared";
import {
  BpBanner,
  BpDebugPanel,
  BpLinkRow,
  BpPropGrid,
  BpScoreGrid,
  BpTable,
  BpToolbar,
  BpToolGrid,
} from "./blueprintUi";
import { BpArchitectureBar } from "../../components/bp/BpArchitectureBar";
import { MODEL_CONFIG_NO_VAULT } from "../../lib/productCopy";
import {
  aipEvidenceSdk,
  LINEAGE_ROOT_TYPES,
  type LineageEvent,
  type LineageRootType,
  type EvalRunAuthority,
} from "../../api/aipEvidence";

const TOOL_CATS = [
  { id: "action", label: "Action", zh: "写回动作（可 HITL）", defaultOn: true },
  { id: "query", label: "Object Query", zh: "对象属性查询", defaultOn: true },
  { id: "function", label: "Function", zh: "函数 / 已发布 Logic", defaultOn: true },
  { id: "var", label: "Update App Var", zh: "更新应用变量", defaultOn: false },
  { id: "cmd", label: "Command", zh: "命令类工具", defaultOn: false },
  { id: "clarify", label: "Request Clarification", zh: "向用户澄清", defaultOn: true },
  { id: "capability", label: "Capability", zh: "重能力（平台代调）", defaultOn: true },
  { id: "wiki", label: "Wiki Field Tool", zh: "Wiki 结构化字段", defaultOn: true, wiki: true },
];

function toolCategory(kind: string): string {
  const k = kind.toLowerCase();
  if (k.includes("wiki")) return "wiki";
  if (k.includes("cap")) return "capability";
  if (k.includes("query") || k.includes("object")) return "query";
  if (k.includes("function") || k.includes("logic")) return "function";
  if (k.includes("clarify")) return "clarify";
  if (k.includes("action")) return "action";
  return "function";
}

function toolSubtitle(kind: string): string {
  const cat = toolCategory(kind);
  if (cat === "action") return "HITL: ●确认后执行";
  if (cat === "query") return "属性子集 · 含 Wiki 字段";
  if (cat === "function") return "或已发布 AIP Logic";
  if (cat === "clarify") return "暂停 · 向用户要澄清";
  if (cat === "capability") return "写回经 Action · 经平台代调";
  if (cat === "wiki") return "结构化字段优先";
  return "只读 / 可提案";
}

/** 80 / 81 · 对齐 aip-tools.html · 三栏 + 策略 radio + 边框导航钮 */
export function ToolsPage() {
  const { data, err, reload } = useJsonGet<{ items: { id: string; kind: string }[] }>(
    "/v1/aip/tools",
  );
  const agents = useJsonGet<{
    items?: Array<{
      instanceId?: string;
      id?: string;
      name?: string;
      status?: string;
      overlay?: { displayName?: string };
    }>;
  }>("/v1/aip/agents");
  const toolsCfg = useJsonGet<{
    categories?: string[];
    mode?: string;
    hitl?: "auto" | "form" | "draft";
  }>("/v1/aip/tools/config");
  const [cats, setCats] = useState<Set<string>>(
    () => new Set(TOOL_CATS.filter((c) => c.defaultOn).map((c) => c.id)),
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hitl, setHitl] = useState<"auto" | "form" | "draft">("form");
  const [invokeSummary, setInvokeSummary] = useState("");
  const [invokePayload, setInvokePayload] = useState<unknown>(null);
  const [localErr, setLocalErr] = useState<string | null>(null);
  const [mode, setMode] = useState("native");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const cfg = toolsCfg.data;
    if (!cfg) return;
    if (Array.isArray(cfg.categories) && cfg.categories.length) {
      setCats(new Set(cfg.categories));
    }
    if (cfg.mode) setMode(cfg.mode);
    if (cfg.hitl === "auto" || cfg.hitl === "form" || cfg.hitl === "draft") {
      setHitl(cfg.hitl);
    }
  }, [toolsCfg.data]);

  const tools = useMemo(() => {
    return (data?.items || []).filter((t) => cats.has(toolCategory(t.kind)));
  }, [data, cats]);

  const selected = tools.find((t) => t.id === selectedId) || tools[0] || null;
  const selectedCat = selected ? toolCategory(selected.kind) : null;
  const currentAgent = useMemo(() => {
    const items = agents.data?.items || [];
    if (!items.length) return null;
    const preferred =
      items.find((item) => {
        const id = String(item.instanceId || item.id || "");
        return id.includes("content_officer");
      }) || items[0];
    const label = preferred.overlay?.displayName || preferred.name || preferred.instanceId || preferred.id || "";
    return label ? { label, status: preferred.status || "" } : null;
  }, [agents.data]);

  function toggleCat(id: string) {
    setCats((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  }

  async function saveToolsConfig() {
    setSaving(true);
    setSaveMsg("");
    setLocalErr(null);
    try {
      await apiPut("/v1/aip/tools/config", {
        categories: Array.from(cats),
        mode,
        hitl,
      });
      setSaveMsg("工具配置已保存");
      toolsCfg.reload();
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
    } finally {
      setSaving(false);
    }
  }

  async function invoke(id: string) {
    setLocalErr(null);
    setInvokeSummary("");
    setInvokePayload(null);
    try {
      const r = await apiPost<Record<string, unknown>>(`/v1/aip/tools/${encodeURIComponent(id)}/invoke`, {
        objectType: "WorkOrder",
        objectId: "wo-1001",
      });
      setInvokeSummary(`试跑完成 · ${id}`);
      setInvokePayload(r);
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
    }
  }

  function renderDetail() {
    if (!selected || !selectedCat) {
      return <p className="muted">选择已启用工具查看细项</p>;
    }

    if (selectedCat === "action") {
      return (
        <>
          <h2 className="bp-tool-detail-title">工具卡 · Action</h2>
          <p className="bp-tool-detail-meta">
            Action Type: <code>{selected.id}</code>
          </p>
          <fieldset className="bp-tool-strategy">
            <legend>执行策略</legend>
            <label>
              <input
                type="radio"
                name="hitl"
                checked={hitl === "auto"}
                onChange={() => setHitl("auto")}
              />
              对话中自动提交
            </label>
            <label>
              <input
                type="radio"
                name="hitl"
                checked={hitl === "form"}
                onChange={() => setHitl("form")}
              />
              弹出 Action 表单供人确认
            </label>
            <label>
              <input
                type="radio"
                name="hitl"
                checked={hitl === "draft"}
                onChange={() => setHitl("draft")}
              />
              仅生成 Draft（提案台）
            </label>
          </fieldset>
          <p className="muted" style={{ fontSize: "0.75rem" }}>
            说明给 LLM：「仅当严重级≥高且用户未否决时调用」
          </p>
          <div className="mp-cfg-actions" style={{ marginTop: "0.75rem" }}>
            <button type="button" className="btn-outline-cyan" onClick={() => void invoke(selected.id)}>
              试跑
            </button>
            <Link to="/aip/drafts" className="btn-nav">
              打开 Draft 审批台 →
            </Link>
          </div>
        </>
      );
    }

    if (selectedCat === "query") {
      return (
        <>
          <h2 className="bp-tool-detail-title">工具卡 · Object Query</h2>
          <p className="bp-tool-detail-meta">Object Type · 遍历深度 1 · {selected.id}</p>
          <div className="bp-tool-chips">
            <span className="bp-tool-chip">☑ id</span>
            <span className="bp-tool-chip">☑ status</span>
            <span className="bp-tool-chip is-wiki">☑ wiki.risk_level</span>
            <span className="bp-tool-chip">☐ raw_payload</span>
          </div>
          <Link to="/ontology/wiki" className="btn-nav">
            打开 LLM Wiki →
          </Link>
        </>
      );
    }

    if (selectedCat === "function") {
      return (
        <>
          <h2 className="bp-tool-detail-title">工具卡 · Function</h2>
          <p className="bp-tool-detail-meta">
            <code style={{ color: "#6ee7b7" }}>{selected.id}</code> · 类型安全核
          </p>
          <p className="muted" style={{ fontSize: "0.75rem" }}>
            亦可挂已发布 AIP Logic（见画布）
          </p>
          <div className="mp-cfg-actions">
            <Link to="/aip/logic" className="btn-nav-accent">
              打开 Logic →
            </Link>
            <button type="button" className="btn-outline-cyan" onClick={() => void invoke(selected.id)}>
              试跑
            </button>
          </div>
        </>
      );
    }

    if (selectedCat === "clarify") {
      return (
        <>
          <h2 className="bp-tool-detail-title">工具卡 · Request Clarification</h2>
          <p className="muted" style={{ fontSize: "0.8rem" }}>
            触发：「信息不足时先问，不要猜」
          </p>
          <p className="muted" style={{ fontSize: "0.75rem" }}>
            UI：对话气泡暂停 + chips；用户回答写入上下文后续推。
          </p>
        </>
      );
    }

    if (selectedCat === "wiki") {
      return (
        <>
          <h2 className="bp-tool-detail-title">工具卡 · Wiki 字段 Tool</h2>
          <p className="muted" style={{ fontSize: "0.8rem", color: "#fdba74" }}>
            结构化字段优先 · Agent 不扫全文向量库
          </p>
          <div className="bp-tool-chips">
            <span className="bp-tool-chip is-wiki">wiki.risk_level</span>
            <span className="bp-tool-chip is-wiki">wiki.specification</span>
          </div>
          <Link to="/ontology/wiki" className="btn-nav">
            打开 LLM Wiki →
          </Link>
        </>
      );
    }

    if (selectedCat === "capability") {
      return (
        <>
          <h2 className="bp-tool-detail-title">工具卡 · Capability</h2>
          <p className="bp-tool-detail-meta">
            Capability: <code style={{ color: "#67e8f9" }}>{selected.id}</code>
          </p>
          <p className="muted" style={{ fontSize: "0.75rem" }}>
            LLM 只请求；平台代调。产物进媒体集；状态写回须经 Action。
          </p>
          <div className="mp-cfg-actions">
            <Link to="/aip/capabilities" className="btn-nav">
              打开重能力接入 →
            </Link>
            <button type="button" className="btn-outline-cyan" onClick={() => void invoke(selected.id)}>
              试跑
            </button>
          </div>
        </>
      );
    }

    return (
      <>
        <h2 className="bp-tool-detail-title">工具卡 · {selected.kind}</h2>
        <p className="bp-tool-detail-meta">
          id: <code>{selected.id}</code>
        </p>
        <button type="button" className="btn-outline-cyan" onClick={() => void invoke(selected.id)}>
          试跑
        </button>
      </>
    );
  }

  return (
    <S2Chrome
      title="Agent 工具面板"
      lede="配置当前智能体可用工具类型与细项。LLM 只「请求」工具；平台以调用用户权限代调。写路径默认可提案。"
    >
      <BpToolbar>
        <label className="muted" style={{ fontSize: "0.65rem", display: "inline-flex", alignItems: "center", gap: 8 }}>
          调用模式
          <select
            className="bp-tool-select"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            aria-label="tool-mode"
          >
            <option value="native">Native（并行）</option>
            <option value="prompted">Prompted（单次一工具）</option>
          </select>
        </label>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <Link to="/aip/capabilities" className="btn-nav">
          重能力 →
        </Link>
        <Link to="/aip/maturity" className="btn-nav">
          ← 成熟度
        </Link>
        <Link to="/aip/logic" className="btn-nav-accent">
          Logic →
        </Link>
        <Link to="/aip/studio" className="btn-nav">
          Chatbot Studio →
        </Link>
      </BpToolbar>
      {(err || localErr || toolsCfg.err) && <p className="error">{err || localErr || toolsCfg.err}</p>}

      <div className="bp-agent-selector">
        <Link to="/aip/studio" className="bp-agent-selector-back">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M15 18l-6-6 6-6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          返回智能体列表
        </Link>
        <span className="bp-agent-selector-divider">|</span>
        <div className="bp-agent-selector-info">
          <span className="bp-agent-selector-label">当前智能体：</span>
          <div className="bp-agent-selector-buddy">
            <div className="bp-agent-selector-avatar">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path
                  d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <span>{currentAgent?.label || "尚未绑定栖月汇数字同事"}</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 9l-7 7-7-7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          {currentAgent ? (
            <>
              <span className="bp-tag bp-tag-ok">{currentAgent.status === "active" || currentAgent.status === "running" ? "运行中" : currentAgent.status || "已安装"}</span>
              <span className="bp-tag bp-tag-warn">L2 · HITL</span>
            </>
          ) : (
            <Link to="/aip/studio" className="bp-tag bp-tag-warn">去 Studio 安装</Link>
          )}
        </div>
        <span className="bp-agent-selector-count">{tools.length} 个工具已启用 / {TOOL_CATS.filter((c) => cats.has(c.id)).length} 类可配</span>
      </div>

      <BpToolGrid
        catalog={
          <>
            <div className="bp-section-micro">工具目录</div>
            {TOOL_CATS.filter((c) => !c.wiki).map((c) => (
              <label key={c.id} className="bp-tool-cat">
                <input
                  type="checkbox"
                  checked={cats.has(c.id)}
                  onChange={() => toggleCat(c.id)}
                />
                <span className="bp-tool-cat-text">
                  <span className="bp-tool-cat-label">{c.label}</span>
                  <span className="bp-tool-cat-zh">{c.zh}</span>
                </span>
              </label>
            ))}
            <hr className="bp-tool-cat-divider" />
            {TOOL_CATS.filter((c) => c.wiki).map((c) => (
              <label key={c.id} className="bp-tool-cat is-wiki">
                <input
                  type="checkbox"
                  checked={cats.has(c.id)}
                  onChange={() => toggleCat(c.id)}
                />
                <span className="bp-tool-cat-text">
                  <span className="bp-tool-cat-label">{c.label}</span>
                  <span className="bp-tool-cat-zh">{c.zh}</span>
                </span>
              </label>
            ))}
            <p className="muted" style={{ fontSize: "0.625rem", marginTop: "0.5rem", padding: "0 0.5rem" }}>
              优先 Wiki 结构化字段 · Query 属性子集
            </p>
            <Link to="/aip/capabilities" className="bp-tool-cat is-capability-entry">
              <span className="bp-tool-cat-text">
                <span className="bp-tool-cat-label">登记重能力 Adapter →</span>
                <span className="bp-tool-cat-zh">登记 Adapter · 写回经 Action</span>
              </span>
            </Link>
          </>
        }
        enabled={
          <>
            <div className="bp-section-micro">已启用</div>
            {tools.map((t, i) => {
              const cat = toolCategory(t.kind);
              const active = selected?.id === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  className={`bp-tool-item${active ? " is-active" : ""}${cat === "capability" ? " is-capability" : ""}`}
                  onClick={() => {
                    setSelectedId(t.id);
                    setInvokeSummary("");
                    setInvokePayload(null);
                    setAdvancedOpen(false);
                  }}
                >
                  <div style={{ fontWeight: 500, color: "var(--aos-text)", fontSize: "0.875rem" }}>
                    {i + 1}. {t.kind} · {t.id}
                  </div>
                  <div
                    className="muted"
                    style={{
                      fontSize: "0.65rem",
                      marginTop: 4,
                      color: cat === "action" && active ? "#fde68a" : undefined,
                    }}
                  >
                    {toolSubtitle(t.kind)}
                  </div>
                </button>
              );
            })}
            {tools.length === 0 && <p className="muted">无匹配工具 · 调整目录勾选</p>}
          </>
        }
        detail={
          <>
            <div className="bp-quality-score">
              <div className="bp-quality-score-header">
                <div className="bp-quality-score-title">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                  </svg>
                  <span>质量评分</span>
                </div>
                <div className="bp-quality-score-value">
                  <span className="bp-quality-score-num">82</span>
                  <span className="bp-quality-score-max">/ 100</span>
                </div>
              </div>
              <div className="bp-quality-score-grid">
                <div className="bp-quality-score-item">
                  <div className="bp-quality-score-item-label">结构分</div>
                  <div className="bp-quality-score-item-val bp-quality-score-item-ok">88</div>
                  <div className="bp-quality-score-bar"><div style={{ width: "88%", background: "#10B981" }} /></div>
                  <div className="bp-quality-score-item-foot">Schema 完整性</div>
                </div>
                <div className="bp-quality-score-item">
                  <div className="bp-quality-score-item-label">文档分</div>
                  <div className="bp-quality-score-item-val bp-quality-score-item-warn">75</div>
                  <div className="bp-quality-score-bar"><div style={{ width: "75%", background: "#F59E0B" }} /></div>
                  <div className="bp-quality-score-item-foot">描述 + 示例</div>
                </div>
                <div className="bp-quality-score-item">
                  <div className="bp-quality-score-item-label">测试分</div>
                  <div className="bp-quality-score-item-val bp-quality-score-item-info">83</div>
                  <div className="bp-quality-score-bar"><div style={{ width: "83%", background: "#3B82F6" }} /></div>
                  <div className="bp-quality-score-item-foot">12/15 用例通过</div>
                </div>
              </div>
              <div className="bp-quality-score-tip">
                <strong>改进建议：</strong>补充 2 个边界测试用例（空输入 + 超长文本），文档分可提升至 85+。
              </div>
              <div className="bp-quality-score-history">
                <span>最近评分：</span>
                <span>v3 → 78</span>
                <span>→</span>
                <span>v4 → 80</span>
                <span>→</span>
                <span className="bp-quality-score-current">v5 → 82</span>
                <span className="bp-quality-score-date">2026-07-25</span>
              </div>
            </div>
            {renderDetail()}
            {invokeSummary && (
              <p className="aos-text" style={{ fontSize: "0.8rem", marginTop: "0.75rem" }}>
                {invokeSummary}
              </p>
            )}
            {invokePayload != null && (
              <>
                <button
                  type="button"
                  className="mp-advanced-toggle"
                  onClick={() => setAdvancedOpen((v) => !v)}
                >
                  {advancedOpen ? "收起高级" : "高级 · 试跑详情"}
                </button>
                {advancedOpen && <BpDebugPanel value={invokePayload} title="试跑详情" />}
              </>
            )}
          </>
        }
      />

      <div className="bp-tool-foot">
        <span>
          Logic：Apply Action · Call Function · Call Capability · Query。Studio{" "}
          <Link to="/aip/studio">试聊</Link>
        </span>
        <button
          type="button"
          className="btn-nav-accent"
          disabled={saving}
          onClick={() => void saveToolsConfig()}
        >
          {saving ? "保存中…" : "保存智能体配置"}
        </button>
      </div>
      {saveMsg && (
        <p className="bp-prop-ok" style={{ fontSize: "0.7rem", marginTop: 6 }}>
          {saveMsg}
        </p>
      )}
    </S2Chrome>
  );
}

type ProviderRow = {
  id: string;
  name?: string;
  ready?: boolean;
  kind?: string;
  apiKeyRef?: string;
};

const FORM_FAMILY_TO_KIND: Record<string, string> = {
  openai_compatible: "openai",
  azure: "azure",
  anthropic: "anthropic",
  local: "vllm",
  adapter: "adapter",
  image: "openai",
  video: "adapter",
};

type LlmPlugin = {
  id: string;
  version?: string;
  name: string;
  nameZh?: string;
  description?: string;
  tier?: string;
  modalities?: string[];
  formFamily?: string;
  defaultModels?: string[];
  installed?: boolean;
  ready?: boolean;
  enabledModels?: string[];
  source?: string;
  configSchema?: {
    properties?: {
      baseUrl?: { default?: string };
    };
  };
};

function formKindFromFamily(family?: string | null): string {
  if (!family) return "openai";
  return FORM_FAMILY_TO_KIND[family] || "openai";
}

function tierLabel(tier?: string): string {
  if (tier === "free") return "免费档";
  if (tier === "high") return "高端";
  return "中端";
}

function modalityLabel(mods?: string[]): string {
  if (!mods?.length) return "文本";
  return mods
    .map((m) => (m === "text" ? "文本" : m === "image" ? "图片" : m === "video" ? "视频" : m))
    .join("·");
}

function secretBoundLabel(ref?: string): string {
  if (!ref) return "未绑定";
  const short = ref.includes("#") ? ref.split("#").pop() : ref.split("/").filter(Boolean).pop();
  return short ? `已绑定 · ${short}` : "已绑定凭据";
}

type ProviderView = "list" | "configure" | "credentials" | "studio" | "detail";

type MpDraft = {
  displayName?: string;
  baseUrl?: string;
  modelId?: string;
  modelOn?: boolean;
  resource?: string;
  region?: string;
  deployment?: string;
  apiVersion?: string;
  localUrl?: string;
  modelPath?: string;
  gpu?: string;
  warmup?: boolean;
  artifacts?: string;
  modelsAnthropic?: { sonnet?: boolean; opus?: boolean };
  secretRef?: string;
  keyUpdatedAt?: string;
};

function mpDraftKey(id: string) {
  return `aos.mp.draft.${id}`;
}

function loadMpDraft(id: string): MpDraft | null {
  try {
    const raw = sessionStorage.getItem(mpDraftKey(id));
    return raw ? (JSON.parse(raw) as MpDraft) : null;
  } catch {
    return null;
  }
}

function saveMpDraft(id: string, draft: MpDraft) {
  sessionStorage.setItem(mpDraftKey(id), JSON.stringify(draft));
}

/** 78 v1.2 · list / configure / credentials · 表单可编辑 · 会话草稿 */
export function ProvidersPage() {
  const { data, err, loading, reload } = useJsonGet<{
    items: ProviderRow[];
    sidecar?: string;
    endpoint?: string;
    defaultTextModel?: string;
    apiKeyRef?: string;
    probe?: { ok?: boolean; sidecar?: string };
  }>("/v1/aip/providers");
  const pluginsApi = useJsonGet<{
    items: LlmPlugin[];
    totals?: { all?: number; installed?: number; catalog?: number };
  }>("/v1/aip/llm-provider-plugins");
  const gatewayApi = useJsonGet<{
    current?: { kind?: string; pluginId?: string | null; defaultModel?: string | null; source?: string };
    options?: Array<{ kind: string; pluginId?: string | null; label: string; defaultModel?: string }>;
  }>("/v1/aip/gateway-default");
  const agnesReady = data?.sidecar === "agnes-openai-compatible";
  const [view, setView] = useState<ProviderView>("list");
  const [gwChoice, setGwChoice] = useState("");
  const [gwBusy, setGwBusy] = useState(false);
  const [catalogType, setCatalogType] = useState<string | null>(null);
  const [activePluginId, setActivePluginId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [catalogOpen, setCatalogOpen] = useState(true);
  const [msg, setMsg] = useState("");
  const [probeMsg, setProbeMsg] = useState("");
  const [probePayload, setProbePayload] = useState<unknown>(null);
  const [probing, setProbing] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [studioId, setStudioId] = useState("my-corp-llm");
  const [studioName, setStudioName] = useState("我的企业模型");
  const [studioDesc, setStudioDesc] = useState("内部 OpenAI 兼容网关");
  const [studioTier, setStudioTier] = useState("mid");
  const [studioMods, setStudioMods] = useState("text");
  const [studioFamily, setStudioFamily] = useState("openai_compatible");
  const [studioBaseUrl, setStudioBaseUrl] = useState("https://llm.example.com/v1");
  const [studioBusy, setStudioBusy] = useState(false);

  const [displayName, setDisplayName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [modelId, setModelId] = useState("");
  const [modelOn, setModelOn] = useState(true);
  const [resource, setResource] = useState("aos-cn-east");
  const [region, setRegion] = useState("chinaeast2");
  const [deployment, setDeployment] = useState("gpt-4o");
  const [apiVersion, setApiVersion] = useState("2024-06-01");
  const [localUrl, setLocalUrl] = useState("http://127.0.0.1:8000/v1");
  const [modelPath, setModelPath] = useState("Qwen2.5-72B-Instruct");
  const [gpu, setGpu] = useState("0,1");
  const [warmup, setWarmup] = useState(true);
  const [artifacts, setArtifacts] = useState("my-llm:1.2");
  const [sonnetOn, setSonnetOn] = useState(true);
  const [opusOn, setOpusOn] = useState(false);
  const [secretRef, setSecretRef] = useState("");
  const [newSecret, setNewSecret] = useState("");
  const [keyUpdatedAt, setKeyUpdatedAt] = useState<string | null>(null);

  const apiVaultRef =
    data?.apiKeyRef || data?.items?.[0]?.apiKeyRef || "vault:secret/data/aos/llm#agnes";
  const apiEndpoint = data?.endpoint || "";
  const selected = (data?.items || []).find((p) => p.id === selectedId) || null;
  const draftId =
    selectedId || (activePluginId ? `plugin:${activePluginId}` : catalogType ? `new:${catalogType}` : "draft");
  const cfgTitle = displayName || selected?.name || selected?.id || activePluginId || "当前供应商";
  /** 插件接入也有凭据槽；不再依赖「仅运行态 selectedId」才露出管理入口 */
  const credTargetId = draftId;
  const pluginItems = pluginsApi.data?.items || [];
  const installedPlugins = pluginItems.filter((p) => p.installed);
  const catalogPlugins = pluginItems.filter((p) => !p.installed);
  const boundLabel = keyUpdatedAt
    ? `已更新 · ${new Date(keyUpdatedAt).toLocaleString()}`
    : secretBoundLabel(secretRef || selected?.apiKeyRef || apiVaultRef);
  const canProbe = !catalogType || agnesReady || Boolean(baseUrl);

  useEffect(() => {
    const cur = gatewayApi.data?.current;
    if (!cur?.kind) return;
    const key =
      cur.kind === "plugin" && cur.pluginId
        ? `plugin:${cur.pluginId}`
        : cur.kind;
    setGwChoice(key);
  }, [gatewayApi.data?.current?.kind, gatewayApi.data?.current?.pluginId]);

  async function saveGatewayDefault() {
    setGwBusy(true);
    setMsg("");
    setSaveMsg("");
    try {
      const opt = (gatewayApi.data?.options || []).find((o) => {
        const k = o.kind === "plugin" && o.pluginId ? `plugin:${o.pluginId}` : o.kind;
        return k === gwChoice;
      });
      if (!opt) {
        setMsg("请选择有效的默认网关");
        return;
      }
      await apiPut("/v1/aip/gateway-default", {
        kind: opt.kind,
        pluginId: opt.pluginId || null,
        defaultModel: opt.defaultModel || null,
      });
      setSaveMsg(
        `已设为平台默认网关：${opt.label}（运行态与无 model 试聊将走此通道）`,
      );
      gatewayApi.reload();
      reload();
      pluginsApi.reload();
    } catch (e) {
      setMsg(String((e as Error).message || e));
    } finally {
      setGwBusy(false);
    }
  }

  function resetTransient() {
    setAdvancedOpen(false);
    setMsg("");
    setProbeMsg("");
    setProbePayload(null);
    setSaveMsg("");
    setNewSecret("");
  }

  function hydrateForm(opts: {
    providerId?: string | null;
    type?: string | null;
    plugin?: LlmPlugin | null;
  }) {
    const pid = opts.providerId || null;
    const type = opts.type || null;
    const plugin = opts.plugin || null;
    const row = (data?.items || []).find((p) => p.id === pid) || null;
    const id = pid || (plugin?.id ? `plugin:${plugin.id}` : type ? `new:${type}` : "draft");
    const draft = loadMpDraft(id);
    const defaultModel =
      plugin?.defaultModels?.[0] || data?.defaultTextModel || row?.id || "default";

    setDisplayName(
      draft?.displayName ||
        row?.name ||
        plugin?.nameZh ||
        plugin?.name ||
        (type === "adapter" ? "自定义 Adapter" : "新供应商"),
    );
    const schemaBase =
      (plugin?.configSchema as { properties?: { baseUrl?: { default?: string } } } | undefined)
        ?.properties?.baseUrl?.default || "";
    setBaseUrl(draft?.baseUrl || schemaBase || data?.endpoint || "https://apihub.agnes-ai.com/v1");
    setModelId(draft?.modelId || defaultModel);
    setModelOn(draft?.modelOn !== false);
    setResource(draft?.resource || "aos-cn-east");
    setRegion(draft?.region || "chinaeast2");
    setDeployment(draft?.deployment || "gpt-4o");
    setApiVersion(draft?.apiVersion || "2024-06-01");
    setLocalUrl(draft?.localUrl || schemaBase || "http://127.0.0.1:8000/v1");
    setModelPath(draft?.modelPath || plugin?.defaultModels?.[0] || "Qwen2.5-72B-Instruct");
    setGpu(draft?.gpu || "0,1");
    setWarmup(draft?.warmup !== false);
    setArtifacts(draft?.artifacts || "my-llm:1.2");
    setSonnetOn(draft?.modelsAnthropic?.sonnet !== false);
    setOpusOn(Boolean(draft?.modelsAnthropic?.opus));
    const defaultRef = plugin
      ? `vault:secret/data/aos/llm#${plugin.id}`
      : row?.apiKeyRef || data?.apiKeyRef || apiVaultRef;
    setSecretRef(draft?.secretRef || (plugin ? defaultRef : row?.apiKeyRef || data?.apiKeyRef || apiVaultRef));
    setKeyUpdatedAt(draft?.keyUpdatedAt || null);
  }

  function openConfigure(opts: {
    providerId?: string | null;
    type?: string | null;
    plugin?: LlmPlugin | null;
  }) {
    const plugin = opts.plugin || null;
    const kind = opts.type || formKindFromFamily(plugin?.formFamily);
    setSelectedId(opts.providerId ?? null);
    setCatalogType(kind);
    setActivePluginId(plugin?.id || null);
    resetTransient();
    hydrateForm({ ...opts, type: kind, plugin });
    setView("configure");
  }

  async function installAndConfigure(plugin: LlmPlugin) {
    setMsg("");
    try {
      await apiPost(`/v1/aip/llm-provider-plugins/${encodeURIComponent(plugin.id)}/install`, {});
      pluginsApi.reload();
      openConfigure({ plugin });
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  async function publishStudioPlugin() {
    setStudioBusy(true);
    setMsg("");
    setSaveMsg("");
    try {
      await apiPut("/v1/aip/llm-provider-plugins/custom", {
        id: studioId.trim(),
        name: studioName.trim() || studioId,
        nameZh: studioName.trim() || studioId,
        description: studioDesc.trim(),
        tier: studioTier,
        modalities: studioMods.split(/[,，\s]+/).filter(Boolean),
        formFamily: studioFamily,
        defaultModels: [],
        configSchema: {
          type: "object",
          properties: {
            baseUrl: { type: "string", default: studioBaseUrl },
            apiKeyRef: { type: "string" },
            models: { type: "array", items: { type: "string" } },
          },
        },
      });
      setSaveMsg(`已发布插件 ${studioId} · 已自动安装`);
      pluginsApi.reload();
      setView("list");
    } catch (e) {
      setMsg(String((e as Error).message || e));
    } finally {
      setStudioBusy(false);
    }
  }

  function openCredentials(providerId?: string | null) {
    const key = providerId || credTargetId;
    if (key.startsWith("plugin:")) {
      const pid = key.slice("plugin:".length);
      setActivePluginId(pid);
      setSelectedId(null);
      const plugin = pluginItems.find((p) => p.id === pid) || null;
      setCatalogType(formKindFromFamily(plugin?.formFamily) || catalogType || "openai");
      resetTransient();
      hydrateForm({ plugin, type: formKindFromFamily(plugin?.formFamily) });
    } else if (key.startsWith("new:")) {
      setSelectedId(null);
      setActivePluginId(null);
      setCatalogType(key.slice("new:".length));
      resetTransient();
      hydrateForm({ type: key.slice("new:".length) });
    } else {
      setSelectedId(key);
      setActivePluginId(null);
      setCatalogType(null);
      resetTransient();
      hydrateForm({ providerId: key });
    }
    setView("credentials");
  }

  function reopenConfigureFromCredentials() {
    if (activePluginId) {
      const plugin = pluginItems.find((p) => p.id === activePluginId) || null;
      openConfigure({ plugin: plugin || undefined, type: catalogType });
      return;
    }
    if (selectedId) {
      openConfigure({ providerId: selectedId });
      return;
    }
    if (catalogType) {
      openConfigure({ type: catalogType });
      return;
    }
    setView("configure");
  }

  function backToList() {
    setView("list");
    setCatalogType(null);
    setSelectedId(null);
    setActivePluginId(null);
    resetTransient();
  }

  function collectDraft(): MpDraft {
    return {
      displayName,
      baseUrl,
      modelId,
      modelOn,
      resource,
      region,
      deployment,
      apiVersion,
      localUrl,
      modelPath,
      gpu,
      warmup,
      artifacts,
      modelsAnthropic: { sonnet: sonnetOn, opus: opusOn },
      secretRef,
      keyUpdatedAt: keyUpdatedAt || undefined,
    };
  }

  async function saveConfigure() {
    setSaveMsg("");
    setMsg("");
    const pluginId = activePluginId;
    if (pluginId) {
      try {
        const models =
          formKind === "openai" || formKind === "azure"
            ? modelOn && modelId
              ? [modelId]
              : []
            : formKind === "vllm"
              ? modelPath
                ? [modelPath]
                : []
              : formKind === "anthropic"
                ? [sonnetOn ? "claude-sonnet-4" : "", opusOn ? "claude-opus" : ""].filter(Boolean)
                : [];
        await apiPut(`/v1/aip/llm-provider-plugins/${encodeURIComponent(pluginId)}/config`, {
          displayName,
          baseUrl: formKind === "vllm" ? localUrl : baseUrl,
          secretRef: secretRef || `vault:secret/data/aos/llm#${pluginId}`,
          models,
          ready: true,
        });
        setSaveMsg("已保存并启用 · 模型已进入路由候选，请到路由策略刷新后选用");
        pluginsApi.reload();
      } catch (e) {
        setMsg(String((e as Error).message || e));
      }
      return;
    }
    saveMpDraft(draftId, collectDraft());
    setSaveMsg("已保存到本机会话草稿 · 测连通仍走当前网关");
  }

  async function enablePluginReady(plugin: LlmPlugin) {
    setMsg("");
    try {
      await apiPost(`/v1/aip/llm-provider-plugins/${encodeURIComponent(plugin.id)}/enable`, {});
      setSaveMsg(`${plugin.nameZh || plugin.name} 已启用就绪 · 可到路由策略选用`);
      pluginsApi.reload();
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  async function disablePluginReady(plugin: LlmPlugin) {
    setMsg("");
    try {
      await apiPost(`/v1/aip/llm-provider-plugins/${encodeURIComponent(plugin.id)}/disable`, {});
      setSaveMsg(`${plugin.nameZh || plugin.name} 已取消就绪`);
      pluginsApi.reload();
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  async function saveCredentials() {
    setSaveMsg("");
    setMsg("");
    const stamped = newSecret.trim() ? new Date().toISOString() : keyUpdatedAt || undefined;
    if (newSecret.trim()) setKeyUpdatedAt(stamped || null);
    const ref = secretRef.trim() || (activePluginId ? `vault:secret/data/aos/llm#${activePluginId}` : apiVaultRef);

    if (activePluginId) {
      try {
        await apiPut(`/v1/aip/llm-provider-plugins/${encodeURIComponent(activePluginId)}/config`, {
          displayName,
          baseUrl: formKind === "vllm" ? localUrl : baseUrl,
          secretRef: ref,
          models:
            formKind === "openai" || formKind === "azure"
              ? modelOn && modelId
                ? [modelId]
                : []
              : [],
          ready: true,
          apiKey: newSecret.trim() || undefined,
        });
        setNewSecret("");
        setSecretRef(ref);
        setSaveMsg("凭据已保存并启用 · 试聊将按所选模型路由（不再回落 Agnes）");
        pluginsApi.reload();
      } catch (e) {
        setMsg(String((e as Error).message || e));
      }
      return;
    }

    saveMpDraft(draftId, {
      ...collectDraft(),
      secretRef: ref,
      keyUpdatedAt: stamped,
    });
    setNewSecret("");
    setSaveMsg("凭据草稿已更新 · 明文密钥不会写入页面日志");
  }

  async function testConnectivity() {
    setProbing(true);
    setMsg("");
    setProbeMsg("");
    setProbePayload(null);
    try {
      const r = await apiPost<{ answer?: string; route?: string; provider?: string }>("/v1/aip/chat", {
        query: "ping · 供应商连通探测",
        withTools: false,
      });
      setProbePayload(r);
      setProbeMsg(`route=${r.route || "?"} · provider=${r.provider || "?"}`);
      if (r.route === "agnes") setMsg("连通 OK");
      else if (r.route === "fallback-mock") setMsg("当前走本地回退 · 请检查供应商凭据与网关状态");
      else setMsg("连通探测完成");
    } catch (e) {
      setMsg(String((e as Error).message || e));
    } finally {
      setProbing(false);
    }
  }

  function providerMeta(p: ProviderRow): string {
    return `${p.kind || "llm"} · ${p.id}`;
  }

  const formKind = catalogType || "openai";

  if (view === "studio") {
    return (
      <S2Chrome
        title="插件工作室 · 定制与发布"
        lede="在线填写 Provider manifest，发布后进入可安装目录并自动安装。对齐 20 §3.1 插件契约。"
      >
        <BpToolbar>
          <button type="button" className="btn-nav" onClick={backToList}>
            ← 返回大模型接入(插件)
          </button>
          <Link to="/aip/model-router" className="btn-nav">
            路由策略 →
          </Link>
        </BpToolbar>
        {msg && <p className="error">{msg}</p>}
        {saveMsg && <p className="bp-prop-ok">{saveMsg}</p>}
        <div className="mp-cfg-panel mp-form-grid">
          <label className="mp-field">
            <span>插件 id（小写-连字符）</span>
            <input value={studioId} onChange={(e) => setStudioId(e.target.value)} aria-label="studio-id" />
          </label>
          <label className="mp-field">
            <span>显示名</span>
            <input value={studioName} onChange={(e) => setStudioName(e.target.value)} />
          </label>
          <label className="mp-field mp-field-span">
            <span>说明</span>
            <input value={studioDesc} onChange={(e) => setStudioDesc(e.target.value)} />
          </label>
          <label className="mp-field">
            <span>档位</span>
            <select value={studioTier} onChange={(e) => setStudioTier(e.target.value)}>
              <option value="free">免费档</option>
              <option value="mid">中端</option>
              <option value="high">高端</option>
            </select>
          </label>
          <label className="mp-field">
            <span>模态（逗号分隔 text/image/video）</span>
            <input value={studioMods} onChange={(e) => setStudioMods(e.target.value)} />
          </label>
          <label className="mp-field">
            <span>表单族</span>
            <select value={studioFamily} onChange={(e) => setStudioFamily(e.target.value)}>
              <option value="openai_compatible">openai_compatible</option>
              <option value="azure">azure</option>
              <option value="anthropic">anthropic</option>
              <option value="local">local</option>
              <option value="adapter">adapter</option>
              <option value="image">image</option>
              <option value="video">video</option>
            </select>
          </label>
          <label className="mp-field">
            <span>默认 Base URL</span>
            <input value={studioBaseUrl} onChange={(e) => setStudioBaseUrl(e.target.value)} />
          </label>
        </div>
        <div className="mp-cfg-actions">
          <button
            type="button"
            className="btn-primary"
            disabled={studioBusy || !studioId.trim()}
            onClick={() => void publishStudioPlugin()}
          >
            {studioBusy ? "发布中…" : "发布插件"}
          </button>
        </div>
      </S2Chrome>
    );
  }

  if (view === "credentials") {
    return (
      <S2Chrome
        title={`管理凭据 · ${cfgTitle}`}
        lede="可改凭据引用或粘贴新密钥；明文不会出现在列表与日志中。"
      >
        <BpToolbar>
          <button type="button" className="btn-nav" onClick={backToList}>
            ← 返回大模型接入(插件)
          </button>
          <button type="button" className="btn-nav-accent" onClick={reopenConfigureFromCredentials}>
            打开配置 →
          </button>
        </BpToolbar>

        <div className="mp-cfg-panel is-creds">
          <div className="mp-cfg-grid">
            <label className="mp-field">
              <span>供应商</span>
              <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
            </label>
            <label className="mp-field">
              <span>绑定状态</span>
              <input readOnly value={boundLabel} className="mp-input-ro" />
            </label>
            <label className="mp-field mp-field-span">
              <span>凭据引用</span>
              <input
                value={secretRef}
                onChange={(e) => setSecretRef(e.target.value)}
                placeholder="vault://aip/providers/...#api_key"
              />
            </label>
            <label className="mp-field mp-field-span">
              <span>新密钥（可选 · 不回显）</span>
              <input
                type="password"
                value={newSecret}
                onChange={(e) => setNewSecret(e.target.value)}
                placeholder="粘贴新 API Key，保存后仅记「已更新」"
                autoComplete="new-password"
              />
            </label>
          </div>
          <p className="muted" style={{ fontSize: "0.75rem", marginTop: "0.75rem" }}>
            保存后请到「配置」页测连通。服务端 PUT 未上线前，草稿仅存本机会话。
          </p>
          <div className="mp-cfg-actions">
            <button type="button" className="btn-primary" onClick={() => void saveCredentials()}>
              轮换 / 重新绑定
            </button>
            <button type="button" className="btn-nav" onClick={reopenConfigureFromCredentials}>
              去配置页测连通 →
            </button>
          </div>
          {saveMsg && (
            <p className="aos-text" style={{ marginTop: 8, fontSize: "0.8rem" }}>
              {saveMsg}
            </p>
          )}
        </div>
      </S2Chrome>
    );
  }

  if (view === "configure") {
    return (
      <S2Chrome title={`配置 · ${cfgTitle}`} lede="填写连接与启用模型；密钥在「管理凭据」中维护。">
        <BpToolbar>
          <button type="button" className="btn-nav" onClick={backToList}>
            ← 返回大模型接入(插件)
          </button>
          <button type="button" className="btn-nav" onClick={() => openCredentials(credTargetId)}>
            管理凭据 →
          </button>
          <Link to="/aip/model-router" className="btn-nav-accent">
            路由策略 →
          </Link>
        </BpToolbar>

        <div className="mp-cfg-panel">
          <div className="mp-cfg-grid">
            {formKind === "openai" && (
              <>
                <label className="mp-field">
                  <span>显示名</span>
                  <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
                </label>
                <label className="mp-field">
                  <span>Base URL</span>
                  <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
                </label>
                <div className="mp-field mp-field-span">
                  <span className="muted" style={{ fontSize: "0.75rem" }}>
                    API Key
                  </span>
                  <div className="mp-cred-summary">
                    <span>{boundLabel}</span>
                    <button
                      type="button"
                      className="btn-nav"
                      onClick={() => openCredentials(credTargetId)}
                    >
                      管理凭据 →
                    </button>
                  </div>
                </div>
                <div className="mp-field mp-field-span mp-check-row">
                  <label>
                    <input
                      type="checkbox"
                      checked={modelOn}
                      onChange={(e) => setModelOn(e.target.checked)}
                    />
                  </label>
                  <input
                    value={modelId}
                    onChange={(e) => setModelId(e.target.value)}
                    style={{ flex: 1, minWidth: "12rem" }}
                    aria-label="model-id"
                  />
                </div>
              </>
            )}
            {formKind === "azure" && (
              <>
                <label className="mp-field">
                  <span>显示名</span>
                  <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
                </label>
                <label className="mp-field">
                  <span>资源名</span>
                  <input value={resource} onChange={(e) => setResource(e.target.value)} />
                </label>
                <label className="mp-field">
                  <span>区域</span>
                  <input value={region} onChange={(e) => setRegion(e.target.value)} />
                </label>
                <label className="mp-field">
                  <span>部署名</span>
                  <input value={deployment} onChange={(e) => setDeployment(e.target.value)} />
                </label>
                <label className="mp-field">
                  <span>API 版本</span>
                  <input value={apiVersion} onChange={(e) => setApiVersion(e.target.value)} />
                </label>
                <div className="mp-field mp-field-span">
                  <span className="muted" style={{ fontSize: "0.75rem" }}>
                    API Key
                  </span>
                  <div className="mp-cred-summary">
                    <span>{boundLabel}</span>
                    <button
                      type="button"
                      className="btn-nav"
                      onClick={() => openCredentials(credTargetId)}
                    >
                      管理凭据 →
                    </button>
                  </div>
                </div>
              </>
            )}
            {formKind === "anthropic" && (
              <>
                <label className="mp-field mp-field-span">
                  <span>显示名</span>
                  <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
                </label>
                <div className="mp-field mp-field-span">
                  <span className="muted" style={{ fontSize: "0.75rem" }}>
                    API Key
                  </span>
                  <div className="mp-cred-summary">
                    <span>{boundLabel}</span>
                    <button
                      type="button"
                      className="btn-nav"
                      onClick={() => openCredentials(credTargetId)}
                    >
                      管理凭据 →
                    </button>
                  </div>
                </div>
                <div className="mp-field mp-field-span mp-check-row">
                  <label>
                    <input
                      type="checkbox"
                      checked={sonnetOn}
                      onChange={(e) => setSonnetOn(e.target.checked)}
                    />{" "}
                    claude-sonnet-4
                  </label>
                  <label>
                    <input
                      type="checkbox"
                      checked={opusOn}
                      onChange={(e) => setOpusOn(e.target.checked)}
                    />{" "}
                    claude-opus
                  </label>
                </div>
              </>
            )}
            {formKind === "vllm" && (
              <>
                <label className="mp-field">
                  <span>显示名</span>
                  <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
                </label>
                <label className="mp-field">
                  <span>本机 OpenAI 兼容地址</span>
                  <input value={localUrl} onChange={(e) => setLocalUrl(e.target.value)} />
                </label>
                <label className="mp-field">
                  <span>模型 ID / 路径</span>
                  <input value={modelPath} onChange={(e) => setModelPath(e.target.value)} />
                </label>
                <label className="mp-field">
                  <span>GPU 可见设备</span>
                  <input value={gpu} onChange={(e) => setGpu(e.target.value)} />
                </label>
                <div className="mp-field mp-check-row">
                  <label>
                    <input
                      type="checkbox"
                      checked={warmup}
                      onChange={(e) => setWarmup(e.target.checked)}
                    />{" "}
                    启动时预热
                  </label>
                </div>
              </>
            )}
            {formKind === "adapter" && (
              <div className="mp-adapter-box">
                <div className="mp-adapter-title">Model Adapter</div>
                <label className="mp-field mp-field-span">
                  <span>显示名</span>
                  <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
                </label>
                <label className="mp-field mp-field-span">
                  <span>Artifacts（容器或 Source API）</span>
                  <input value={artifacts} onChange={(e) => setArtifacts(e.target.value)} />
                </label>
              </div>
            )}
          </div>

          <div className="mp-cfg-actions">
            <button
              type="button"
              className="btn-outline-cyan"
              disabled={probing || !canProbe}
              onClick={() => void testConnectivity()}
            >
              {probing ? "探测中…" : "测连通"}
            </button>
            <button type="button" className="btn-primary" onClick={() => void saveConfigure()}>
              保存并启用
            </button>
            <Link to="/aip/model-router" className="btn-nav">
              去路由策略选用 →
            </Link>
          </div>

          {(saveMsg || msg || probeMsg) && (
            <div className="mp-probe-summary">
              {saveMsg && <p className="aos-text">{saveMsg}</p>}
              {msg && <p className={msg.includes("回退") ? "bp-prop-warn" : "aos-text"}>{msg}</p>}
              {probeMsg && (
                <p className="muted" style={{ fontSize: "0.8rem", margin: 0 }}>
                  {probeMsg}
                </p>
              )}
            </div>
          )}

          <button
            type="button"
            className="mp-advanced-toggle"
            onClick={() => setAdvancedOpen((v) => !v)}
          >
            {advancedOpen ? "收起高级" : "高级 · 网关 / 探测详情"}
          </button>
          {advancedOpen && (
            <div className="mp-advanced">
              <BpPropGrid
                items={[
                  { label: "平台默认网关（只读）", value: data?.sidecar || "—", tone: agnesReady ? "ok" : "muted" },
                  { label: "endpoint", value: baseUrl || apiEndpoint || "—" },
                  { label: "配置源", value: data?.sidecar?.startsWith("plugin:") ? "插件默认" : agnesReady ? "环境托管" : "本地回退" },
                ]}
              />
              {probePayload != null && <BpDebugPanel value={probePayload} title="连通探测详情" />}
            </div>
          )}
        </div>
      </S2Chrome>
    );
  }

  return (
    <S2Chrome
      title="大模型接入(插件)"
      lede="每种供应商 = 一个插件（20 §3.1）。先安装插件，再填类型化配置；运行时经平台网关，不直连厂商。"
    >
      <BpArchitectureBar activeLayer="L1" />
      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            reload();
            pluginsApi.reload();
            gatewayApi.reload();
          }}
        >
          刷新
        </button>
        <button type="button" className="btn-nav-accent" onClick={() => setView("studio")}>
          插件工作室
        </button>
        <button
          type="button"
          className="btn-nav"
          onClick={() => {
            const adapter = pluginItems.find((p) => p.id === "custom-adapter");
            if (adapter) void installAndConfigure(adapter);
            else openConfigure({ type: "adapter" });
          }}
        >
          Adapter 管理
        </button>
        <Link to="/aip/model-router" className="btn-nav">
          路由策略 →
        </Link>
      </BpToolbar>
      {loading && <p className="muted">加载中…</p>}
      {(err || pluginsApi.err || gatewayApi.err || msg) && (
        <p className="error">{err || pluginsApi.err || gatewayApi.err || msg}</p>
      )}
      {saveMsg && <p className="bp-prop-ok">{saveMsg}</p>}
      <BpBanner tone="info">{MODEL_CONFIG_NO_VAULT}</BpBanner>

      <section className="mp-section">
        <div className="mp-section-head">
          <h2 className="mp-section-title">平台默认网关</h2>
          <span className="mp-section-hint">
            运行态 = 网关托管的默认通道 · 就绪 ≠ 自动升运行态
          </span>
        </div>
        <div className="mp-gateway-bar">
          <label className="mp-field">
            <span className="mp-field-label">当前默认</span>
            <select
              className="mp-input"
              value={gwChoice}
              onChange={(e) => setGwChoice(e.target.value)}
              disabled={gwBusy || !(gatewayApi.data?.options || []).length}
            >
              {(gatewayApi.data?.options || []).map((o) => {
                const k = o.kind === "plugin" && o.pluginId ? `plugin:${o.pluginId}` : o.kind;
                return (
                  <option key={k} value={k}>
                    {o.label}
                  </option>
                );
              })}
            </select>
          </label>
          <button
            type="button"
            className="btn-nav-accent"
            disabled={gwBusy || !gwChoice}
            onClick={() => void saveGatewayDefault()}
          >
            {gwBusy ? "保存中…" : "保存为默认"}
          </button>
        </div>
        <p className="muted" style={{ fontSize: "0.8rem", margin: "0.4rem 0 0" }}>
          当前：{data?.sidecar || "—"}
          {data?.defaultTextModel ? ` · ${data.defaultTextModel}` : ""}
          {gatewayApi.data?.current?.source ? ` · 源 ${gatewayApi.data.current.source}` : ""}
          。候选含环境 Agnes、已「启用就绪」的插件、LiteLLM。
        </p>
      </section>

      <section className="mp-section">
        <div className="mp-section-head">
          <h2 className="mp-section-title">已安装 / 运行中</h2>
          <span className="mp-section-hint">
            插件 {pluginsApi.data?.totals?.installed ?? installedPlugins.length} · 运行态{" "}
            {data?.items?.length || 0}
          </span>
        </div>
        <div className="mp-card-grid">
          {(data?.items || []).map((p) => {
            const ready = p.ready !== false;
            return (
              <div key={`rt-${p.id}`} className={`mp-provider-card${ready ? " is-ready" : " is-warn"}`}>
                <div className="mp-provider-card-head">
                  <div>
                    <div className="mp-provider-name">{p.name || p.id}</div>
                    <div className="mp-provider-meta">{providerMeta(p)} · 运行态</div>
                  </div>
                  <span className={ready ? "mp-badge-ok" : "mp-badge-warn"}>
                    {ready ? "就绪" : "未就绪"}
                  </span>
                </div>
                <div className="mp-provider-actions">
                  <Link
                    to={`/aip/model-providers/${p.id}`}
                    className="btn btn-nav-accent"
                  >
                    详情
                  </Link>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => openConfigure({ providerId: p.id })}
                  >
                    配置
                  </button>
                  <button type="button" className="btn" onClick={() => openCredentials(p.id)}>
                    管理凭据
                  </button>
                  <span
                    className="btn-nav"
                    title="网关运行态由环境 / 边车托管，不走插件「启用/取消就绪」；要下线请改网关配置或停边车"
                    style={{ opacity: 0.85, cursor: "default" }}
                    data-testid="provider-runtime-hosted-badge"
                  >
                    运行态：环境/边车托管
                  </span>
                </div>
              </div>
            );
          })}
          {installedPlugins.map((p) => (
            <div key={`pl-${p.id}`} className={`mp-provider-card${p.ready ? " is-ready" : " is-warn"}`}>
              <div className="mp-provider-card-head">
                <div>
                  <div className="mp-provider-name">{p.nameZh || p.name}</div>
                  <div className="mp-provider-meta">
                    {p.id} · v{p.version || "0.1.0"} · {tierLabel(p.tier)} · {modalityLabel(p.modalities)}
                    {p.ready && p.enabledModels?.length
                      ? ` · ${p.enabledModels.slice(0, 2).join(", ")}`
                      : ""}
                  </div>
                </div>
                <span className={p.ready ? "mp-badge-ok" : "mp-badge-warn"}>
                  {p.ready ? "就绪" : "已安装"}
                </span>
              </div>
              <div className="mp-provider-actions">
                <Link
                  to={`/aip/model-providers/${p.id}`}
                  className="btn btn-nav-accent"
                >
                  详情
                </Link>
                <button type="button" className="btn" onClick={() => openConfigure({ plugin: p })}>
                  配置
                </button>
                <button
                  type="button"
                  className="btn"
                  onClick={() => openCredentials(`plugin:${p.id}`)}
                >
                  管理凭据
                </button>
                {p.ready ? (
                  <button type="button" className="btn-nav" onClick={() => void disablePluginReady(p)}>
                    取消就绪
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn-nav-accent"
                    onClick={() => void enablePluginReady(p)}
                  >
                    启用就绪
                  </button>
                )}
              </div>
            </div>
          ))}
          {!loading && !err && !pluginsApi.err && (data?.items?.length || 0) === 0 && installedPlugins.length === 0 && (
            <p className="muted">服务端已确认暂无已安装插件 · 从下方目录安装（DeepSeek 等）</p>
          )}
        </div>
      </section>

      <section className="mp-section">
        <div className="mp-section-head">
          <button
            type="button"
            className="mp-collapse-toggle"
            onClick={() => setCatalogOpen((v) => !v)}
            aria-expanded={catalogOpen}
          >
            <span className="mp-section-title">
              {catalogOpen ? "▾" : "▸"} 可安装插件
            </span>
            <span className="mp-section-hint">
              {catalogPlugins.length} / 共 {pluginItems.length} · DeepSeek 必选 · 文本/图片/视频
            </span>
          </button>
        </div>
        {catalogOpen && (
          <div className="mp-card-grid mp-catalog-grid">
            {catalogPlugins.map((p) => (
              <div
                key={p.id}
                className={`mp-catalog-card${p.id === "deepseek" ? " is-featured" : ""}${
                  p.id === "custom-adapter" ? " is-adapter" : ""
                }`}
              >
                <div className="mp-provider-name">{p.nameZh || p.name}</div>
                <p className="mp-provider-meta">{p.description || p.id}</p>
                <div className="mp-plugin-tags">
                  <span className={`mp-tag mp-tag-${p.tier || "mid"}`}>{tierLabel(p.tier)}</span>
                  <span className="mp-tag">{modalityLabel(p.modalities)}</span>
                </div>
                <div className="mp-provider-actions" style={{ marginTop: "0.65rem" }}>
                  <button
                    type="button"
                    className="btn-nav-accent"
                    onClick={() => void installAndConfigure(p)}
                  >
                    安装并配置
                  </button>
                  <button type="button" className="btn" onClick={() => openConfigure({ plugin: p })}>
                    详情
                  </button>
                </div>
              </div>
            ))}
            {catalogPlugins.length === 0 && (
              <p className="muted">目录插件均已安装 · 可用插件工作室继续扩展</p>
            )}
          </div>
        )}
      </section>

      <p className="mp-footnote">
        按需还可扩展接入更多供应商。使用{" "}
        <button type="button" className="bp-action-link" onClick={() => setView("studio")}>
          插件工作室
        </button>{" "}
        在线定制并发布。接入 ≠ 路由；任务策略见 <Link to="/aip/model-router">模型路由</Link>。
      </p>
    </S2Chrome>
  );
}


type ModelItem = { id: string; kind: string; ready: boolean; provider?: string };

type RouteRule = {
  id: string;
  task: string;
  primary: string;
  fallback: string;
  egress: string;
  span?: boolean;
};

const EGRESS_OPTIONS = ["禁公网", "审批后", "继承", "强制不出域", "fallback"] as const;

/** Phase B — V2 RouteRule with weights/fallback_chain/circuit_config */
type V2RouteRule = RouteRule & {
  weights?: { model: string; pct: number }[];
  fallback_chain?: string[];
  circuit_config?: Record<string, number>;
  strategy?: string;
  enabled?: boolean;
};

/** Phase B — Global circuit breaker config */
type GlobalCircuitConfig = {
  error_rate_threshold_pct?: number;
  latency_p99_ms?: number;
  cooldown_seconds?: number;
  half_open_probes?: number;
};

/** Phase B — Route test result */
type RouteTestResult = {
  route_id: string;
  strategy: string;
  prompt: string;
  selected: { model: string; weight_pct: number; reason: string }[];
  estimated_latency_ms: number;
  estimated_input_tokens: number;
  estimated_output_tokens: number;
  circuit_state: string;
  tested_at: string;
  evaluatedVersion: number;
};

type RouterConfig = {
  items: V2RouteRule[];
  version: number;
  updatedAt: string;
};

function sameRouterItems(left: V2RouteRule[], right: V2RouteRule[]): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function egressTone(egress: string): "ok" | "warn" | "bad" | "muted" {
  if (egress.includes("禁公网")) return "ok";
  if (egress.includes("审批")) return "warn";
  if (egress.includes("不出域") || egress.includes("强制")) return "bad";
  return "muted";
}

/** 79 / 81 · 对齐 aip-model-router · 规则可编辑持久化 / 预热试聊分层 */
export function ModelRouterPage() {
  const models = useJsonGet<{ items: ModelItem[]; sidecar?: string; defaultTextModel?: string }>(
    "/v1/aip/models",
  );
  const routerApi = useJsonGet<RouterConfig>("/api/models/router");
  const warm = useJsonGet<{
    ready?: boolean;
    models?: { id: string; state?: string }[];
    sidecar?: string;
  }>("/v1/aip/models/warmup");
  const [view, setView] = useState<"rules" | "warmup">("rules");
  const [modelId, setModelId] = useState("");
  const [query, setQuery] = useState("你好，介绍一下本系统的模型路由");
  const [chatAnswer, setChatAnswer] = useState("");
  const [chatPayload, setChatPayload] = useState<unknown>(null);
  const [chatErr, setChatErr] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [routeRows, setRouteRows] = useState<V2RouteRule[]>([]);
  const [confirmedVersion, setConfirmedVersion] = useState<number | null>(null);
  const [saveMsg, setSaveMsg] = useState("");
  const [drillMsg, setDrillMsg] = useState("");
  const [localErr, setLocalErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const items = models.data?.items || [];
  const modelOptions = useMemo(() => {
    const ids = items.map((m) => m.id).filter(Boolean);
    return ["—", ...ids];
  }, [items]);

  useEffect(() => {
    const d = models.data?.defaultTextModel;
    if (d) setModelId(d);
  }, [models.data?.defaultTextModel]);

  useEffect(() => {
    if (routerApi.data?.items) {
      setRouteRows(routerApi.data.items);
      setConfirmedVersion(routerApi.data.version);
    }
  }, [routerApi.data]);

  function patchRow(id: string, patch: Partial<RouteRule>) {
    setRouteRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));
    setSaveMsg("");
  }

  async function saveRoutes() {
    if (confirmedVersion == null) return;
    setSaving(true);
    setLocalErr(null);
    setSaveMsg("");
    try {
      const saved = await apiPut<RouterConfig>("/api/models/router", {
        items: routeRows,
        expectedVersion: confirmedVersion,
      });
      if (saved.version <= confirmedVersion) {
        throw new Error("保存回包版本未递增，未确认成功");
      }
      const reread = await apiGet<RouterConfig>("/api/models/router");
      if (reread.version !== saved.version || !sameRouterItems(reread.items, saved.items)) {
        throw new Error("写入已提交，但配置重读与保存回包不一致");
      }
      setRouteRows(reread.items);
      setConfirmedVersion(reread.version);
      routerApi.setData(reread);
      setSaveMsg(`路由策略已保存并重读确认 · v${reread.version}`);
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
    } finally {
      setSaving(false);
    }
  }

  async function runCircuitDrill() {
    setDrillMsg("");
    setLocalErr(null);
    const routeId = routeRows[0]?.id;
    if (!routeId || confirmedVersion == null) return;
    try {
      const r = await apiPost<RouteTestResult>(`/api/models/router/${routeId}/test`, {
        prompt: "circuit-drill",
        context_length: 0,
        configVersion: confirmedVersion,
      });
      if (r.evaluatedVersion !== confirmedVersion) {
        throw new Error(
          `熔断演练版本不一致：页面 v${confirmedVersion}，服务端评估 v${r.evaluatedVersion}`,
        );
      }
      setDrillMsg(`已按配置 v${r.evaluatedVersion} 完成熔断演练`);
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
    }
  }

  function exportAuditSnapshot() {
    const blob = new Blob(
      [
        JSON.stringify(
          { items: routeRows, version: confirmedVersion, exportedAt: new Date().toISOString() },
          null,
          2,
        ),
      ],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `model-routes-audit-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setDrillMsg("已导出审计快照");
  }

  async function tryChat() {
    setChatErr(null);
    setChatAnswer("");
    setChatPayload(null);
    try {
      const r = await apiPost<{ answer?: string; model?: string }>("/v1/aip/chat", {
        query,
        withTools: false,
        model: modelId || undefined,
      });
      setChatAnswer(String(r.answer || "（无回复）"));
      setChatPayload(r);
    } catch (e) {
      setChatErr(String((e as Error).message || e));
      setChatPayload(null);
    }
  }

  if (view === "warmup") {
    return (
      <S2Chrome title="预热与试聊" lede="查看模型预热状态，并用当前路由网关做一次试聊验证。">
        <BpToolbar>
          <button type="button" className="btn-nav" onClick={() => setView("rules")}>
            ← 返回路由策略
          </button>
          <Link to="/aip/model-providers" className="btn-nav-accent">
            大模型接入(插件)
          </Link>
          <button
            type="button"
            className="btn"
            onClick={() => {
              models.reload();
              warm.reload();
            }}
          >
            刷新
          </button>
        </BpToolbar>

        <div className="mr-warmup-card">
          <h2 className="mr-warmup-title">模型预热状态</h2>
          {items.length === 0 && <p className="muted">暂无模型状态</p>}
          {items.map((m) => {
            const id = m.id;
            const warmRow = (warm.data?.models || []).find((w) => w.id === id);
            const state = warmRow?.state || (m.ready ? "ready" : "cold");
            const ready = state === "ready" || m.ready;
            return (
              <div key={id} className="mr-warmup-row">
                <span>
                  {id}
                  {m.provider ? ` · ${m.provider}` : ""}
                </span>
                <span className={ready ? "bp-prop-ok" : "bp-prop-warn"}>
                  {ready ? "已就绪" : "预热 / 加载中"}
                </span>
              </div>
            );
          })}
        </div>

        <section className="mp-section">
          <div className="mp-section-head">
            <h2 className="mp-section-title">试聊</h2>
            <span className="mp-section-hint">选用可路由模型验证策略</span>
          </div>
          <div className="mp-card-grid">
            {items.map((m) => (
              <label key={m.id} className={`mp-provider-card${modelId === m.id ? " is-ready" : ""}`}>
                <div className="mp-provider-card-head">
                  <div>
                    <div className="mp-provider-name">{m.id}</div>
                    <div className="mp-provider-meta">
                      {m.kind}
                      {m.provider ? ` · ${m.provider}` : ""}
                    </div>
                  </div>
                  <input
                    type="radio"
                    name="router-model"
                    checked={modelId === m.id}
                    onChange={() => setModelId(m.id)}
                  />
                </div>
              </label>
            ))}
          </div>
          <div className="filter-bar">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              style={{ minWidth: "16rem", flex: 1 }}
              aria-label="router-query"
            />
            <button type="button" className="btn-primary" onClick={() => void tryChat()}>
              试聊
            </button>
          </div>
          {chatErr && <p className="error">{chatErr}</p>}
          {chatAnswer && (
            <div className="mp-cfg-panel" style={{ marginTop: "0.75rem" }}>
              <div className="mp-section-title">试聊回复</div>
              <p className="aos-text" style={{ whiteSpace: "pre-wrap", marginTop: "0.5rem" }}>
                {chatAnswer}
              </p>
            </div>
          )}
          <button
            type="button"
            className="mp-advanced-toggle"
            onClick={() => setAdvancedOpen((v) => !v)}
          >
            {advancedOpen ? "收起高级" : "高级 · 试聊详情"}
          </button>
          {advancedOpen && chatPayload != null && (
            <BpDebugPanel value={chatPayload} title="试聊详情" />
          )}
        </section>
      </S2Chrome>
    );
  }

  return (
    <S2Chrome
      title="模型路由策略"
      lede="任务类型 · 出境 · 熔断降级。供应商安装与类型化配置见大模型接入(插件)。"
    >
      <BpArchitectureBar activeLayer="L2" />
      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            models.reload();
            routerApi.reload();
            warm.reload();
          }}
        >
          刷新
        </button>
        <Link to="/aip/model-providers" className="btn-nav-accent">
          大模型接入(插件)
        </Link>
        <Link to="/aip/tools" className="btn-nav">
          工具面板 →
        </Link>
        <button type="button" className="btn-nav" onClick={() => setView("warmup")}>
          预热与试聊 →
        </button>
      </BpToolbar>
      {(models.err || warm.err || routerApi.err || localErr) && (
        <p className="error">
          {routerApi.err === "Not Found"
            ? "路由配置接口未就绪（/api/models/router 404）· 请重启 aos-api 后点刷新"
            : models.err || warm.err || routerApi.err || localErr}
        </p>
      )}

      <p className="mr-hint">
        本页只选<strong>已就绪</strong>模型做策略。新装插件（如 DeepSeek）须在供应商页点「启用就绪」或「保存并启用」后，再回本页刷新。
      </p>

      <div className="mr-rules-card">
        <div className="mr-rules-head">
          <h2 className="mr-rules-title">路由规则</h2>
          <span className="mr-rules-meta">
            任务类型 / 回退 / 出境 · 可编辑 · 配置版本 v{confirmedVersion ?? "—"}
          </span>
        </div>
        <table className="mr-table">
          <thead>
            <tr>
              <th>任务类型</th>
              <th>首选</th>
              <th>回退</th>
              <th>出境</th>
            </tr>
          </thead>
          <tbody>
            {routeRows.map((r) => {
              const tone = egressTone(r.egress);
              return (
                <tr key={r.id}>
                  <td>{r.task}</td>
                  {r.span ? (
                    <td className="mr-egress-bad" colSpan={2}>
                      <span className="mr-span-label">熔断降级 → </span>
                      <select
                        className="mr-select"
                        value={r.primary}
                        onChange={(e) => patchRow(r.id, { primary: e.target.value })}
                        aria-label={`${r.task}-degrade`}
                      >
                        {modelOptions
                          .filter((o) => o !== "—")
                          .concat(r.primary && !modelOptions.includes(r.primary) ? [r.primary] : [])
                          .map((o) => (
                            <option key={o} value={o}>
                              {o}
                            </option>
                          ))}
                      </select>
                    </td>
                  ) : (
                    <>
                      <td>
                        <select
                          className="mr-select mr-select-primary"
                          value={r.primary}
                          onChange={(e) => patchRow(r.id, { primary: e.target.value })}
                          aria-label={`${r.task}-primary`}
                        >
                          {modelOptions
                            .concat(r.primary && !modelOptions.includes(r.primary) ? [r.primary] : [])
                            .map((o) => (
                              <option key={o} value={o}>
                                {o}
                              </option>
                            ))}
                        </select>
                      </td>
                      <td>
                        <select
                          className="mr-select"
                          value={r.fallback || "—"}
                          onChange={(e) => patchRow(r.id, { fallback: e.target.value })}
                          aria-label={`${r.task}-fallback`}
                        >
                          {modelOptions
                            .concat(
                              r.fallback && r.fallback !== "—" && !modelOptions.includes(r.fallback)
                                ? [r.fallback]
                                : [],
                            )
                            .map((o) => (
                              <option key={o} value={o}>
                                {o}
                              </option>
                            ))}
                        </select>
                      </td>
                    </>
                  )}
                  <td
                    className={
                      tone === "ok"
                        ? "mr-egress-ok"
                        : tone === "warn"
                          ? "mr-egress-warn"
                          : tone === "bad"
                            ? "mr-egress-bad"
                            : "mr-cell-muted"
                    }
                  >
                    <select
                      className="mr-select"
                      value={r.egress}
                      onChange={(e) => patchRow(r.id, { egress: e.target.value })}
                      aria-label={`${r.task}-egress`}
                    >
                      {[
                        ...EGRESS_OPTIONS,
                        ...(EGRESS_OPTIONS as readonly string[]).includes(r.egress) ? [] : [r.egress],
                      ].map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="mr-rules-foot">
          <button
            type="button"
            className="btn-nav-accent"
            disabled={saving || routeRows.length === 0 || confirmedVersion == null}
            onClick={() => void saveRoutes()}
          >
            {saving ? "保存中…" : "保存策略"}
          </button>
          <button
            type="button"
            className="btn-nav"
            disabled={confirmedVersion == null || routeRows.length === 0}
            onClick={() => void runCircuitDrill()}
          >
            熔断演练
          </button>
          <button type="button" className="btn-nav" onClick={exportAuditSnapshot}>
            导出审计快照
          </button>
        </div>
        {(saveMsg || drillMsg) && (
          <p className="bp-prop-ok" style={{ fontSize: "0.7rem", margin: "0.5rem 1rem 0.75rem" }}>
            {saveMsg || drillMsg}
          </p>
        )}
      </div>

      {/* === Phase B 新增面板 === */}
      <ModelRouterPanels
        routeRows={routeRows}
        configVersion={confirmedVersion}
      />
    </S2Chrome>
  );
}

/** Phase B · 权重分配 / 全局熔断配置 / Fallback 链 / 路由测试 */
function ModelRouterPanels({
  routeRows,
  configVersion,
}: {
  routeRows: V2RouteRule[];
  configVersion: number | null;
}) {
  const [activePanel, setActivePanel] = useState<"weights" | "circuit" | "fallback" | "test">(
    "weights",
  );
  const circuitApi = useJsonGet<GlobalCircuitConfig>("/api/models/router/circuit-config");
  const [circuitDraft, setCircuitDraft] = useState<GlobalCircuitConfig | null>(null);
  const [circuitSaving, setCircuitSaving] = useState(false);
  const [circuitMsg, setCircuitMsg] = useState("");
  const [testRouteId, setTestRouteId] = useState("");
  const [testPrompt, setTestPrompt] = useState("你好，介绍一下本系统的模型路由");
  const [testResult, setTestResult] = useState<RouteTestResult | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [testErr, setTestErr] = useState<string | null>(null);

  const v2Rules = routeRows;
  const circuitCfg = circuitDraft || circuitApi.data || {
    error_rate_threshold_pct: 10,
    latency_p99_ms: 3000,
    cooldown_seconds: 30,
    half_open_probes: 3,
  };

  useEffect(() => {
    if (!circuitDraft && circuitApi.data) {
      setCircuitDraft(circuitApi.data);
    }
  }, [circuitApi.data]);

  useEffect(() => {
    if (!testRouteId && v2Rules.length > 0) {
      setTestRouteId(v2Rules[0].id);
    }
  }, [v2Rules]);

  async function saveCircuitConfig() {
    if (!circuitDraft) return;
    setCircuitSaving(true);
    setCircuitMsg("");
    try {
      await apiPut("/api/models/router/circuit-config", circuitDraft);
      setCircuitMsg("全局熔断配置已保存");
      circuitApi.reload();
    } catch (e) {
      setCircuitMsg(String((e as Error).message || e));
    } finally {
      setCircuitSaving(false);
    }
  }

  async function runRouteTest() {
    if (!testRouteId || configVersion == null) return;
    setTestLoading(true);
    setTestErr(null);
    setTestResult(null);
    try {
      const r = await apiPost<RouteTestResult>(
        `/api/models/router/${testRouteId}/test`,
        {
          prompt: testPrompt,
          context_length: testPrompt.length * 2,
          configVersion,
        },
      );
      if (r.evaluatedVersion !== configVersion) {
        throw new Error(
          `路由测试版本不一致：页面 v${configVersion}，服务端评估 v${r.evaluatedVersion}`,
        );
      }
      setTestResult(r);
    } catch (e) {
      setTestErr(String((e as Error).message || e));
    } finally {
      setTestLoading(false);
    }
  }

  const tabBtn = (id: typeof activePanel, label: string) => (
    <button
      type="button"
      key={id}
      className={`btn-nav${activePanel === id ? " btn-nav-accent" : ""}`}
      onClick={() => setActivePanel(id)}
    >
      {label}
    </button>
  );

  return (
    <div className="mr-rules-card" style={{ marginTop: "1rem" }}>
      <div className="mr-rules-head">
        <h2 className="mr-rules-title">高级配置</h2>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          {tabBtn("weights", "权重分配")}
          {tabBtn("circuit", "熔断器配置")}
          {tabBtn("fallback", "Fallback 链")}
          {tabBtn("test", "路由测试")}
        </div>
      </div>

      {/* === 权重分配可视化 === */}
      {activePanel === "weights" && (
        <div style={{ padding: "1rem" }}>
          {v2Rules.length === 0 && <p className="muted">暂无路由规则</p>}
          {v2Rules.map((rule) => {
            const weights = rule.weights || [];
            const totalPct = weights.reduce((s, w) => s + (w.pct || 0), 0);
            const hasWeights = totalPct > 0;
            return (
              <div key={rule.id} style={{ marginBottom: "1rem" }}>
                <div className="flex items-center justify-between mb-1.5">
                  <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "#1f2937" }}>
                    {rule.task}
                    <span style={{ marginLeft: "0.5rem", fontSize: "0.65rem", color: "#9ca3af" }}>
                      策略: {rule.strategy}
                    </span>
                  </span>
                </div>
                {hasWeights ? (
                  <div
                    style={{
                      height: "1.75rem",
                      borderRadius: "0.5rem",
                      overflow: "hidden",
                      display: "flex",
                      border: "1px solid #e5e7eb",
                    }}
                  >
                    {weights.map((w, i) => {
                      const colors = ["#4f46e5", "#6366f1", "#818cf8", "#a5b4fc"];
                      return (
                        <div
                          key={w.model}
                          style={{
                            width: `${w.pct}%`,
                            background: colors[i % colors.length],
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color: "white",
                            fontSize: "0.625rem",
                            fontWeight: 500,
                          }}
                        >
                          {w.pct > 10 ? `${w.model} · ${w.pct}%` : ""}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div
                    style={{
                      height: "1.75rem",
                      borderRadius: "0.5rem",
                      background: "#f3f4f6",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      border: "1px solid #e5e7eb",
                      fontSize: "0.625rem",
                      color: "#9ca3af",
                    }}
                  >
                    {rule.primary}（failover 模式 · 无权重分配）
                  </div>
                )}
                {rule.circuit_config && Object.keys(rule.circuit_config).length > 0 && (
                  <div
                    style={{
                      marginTop: "0.375rem",
                      fontSize: "0.625rem",
                      color: "#6b7280",
                      display: "flex",
                      gap: "0.75rem",
                    }}
                  >
                    <span>熔断: 5xx &gt; {(rule.circuit_config.error_rate_threshold_pct || 10)}%</span>
                    <span>·</span>
                    <span>p99 &gt; {(rule.circuit_config.latency_p99_ms || 3000)}ms</span>
                    <span>·</span>
                    <span>恢复: {(rule.circuit_config.cooldown_seconds || 30)}s</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* === 全局熔断器配置面板 === */}
      {activePanel === "circuit" && (
        <div style={{ padding: "1rem" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(12rem, 1fr))",
              gap: "0.75rem",
              fontSize: "0.75rem",
            }}
          >
            <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
              <span style={{ color: "#6b7280" }}>5xx 错误率阈值</span>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="range"
                  min={1}
                  max={50}
                  value={circuitCfg.error_rate_threshold_pct ?? 10}
                  onChange={(e) =>
                    setCircuitDraft({
                      ...circuitCfg,
                      error_rate_threshold_pct: Number(e.target.value),
                    })
                  }
                  style={{ flex: 1, accentColor: "#4f46e5" }}
                />
                <span style={{ fontWeight: 600, width: "2rem", textAlign: "right" }}>
                  {circuitCfg.error_rate_threshold_pct ?? 10}%
                </span>
              </div>
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
              <span style={{ color: "#6b7280" }}>延迟 p99 阈值</span>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="range"
                  min={500}
                  max={10000}
                  step={500}
                  value={circuitCfg.latency_p99_ms ?? 3000}
                  onChange={(e) =>
                    setCircuitDraft({
                      ...circuitCfg,
                      latency_p99_ms: Number(e.target.value),
                    })
                  }
                  style={{ flex: 1, accentColor: "#4f46e5" }}
                />
                <span style={{ fontWeight: 600, width: "3rem", textAlign: "right" }}>
                  {circuitCfg.latency_p99_ms ?? 3000}ms
                </span>
              </div>
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
              <span style={{ color: "#6b7280" }}>熔断时长</span>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="range"
                  min={10}
                  max={300}
                  step={10}
                  value={circuitCfg.cooldown_seconds ?? 30}
                  onChange={(e) =>
                    setCircuitDraft({
                      ...circuitCfg,
                      cooldown_seconds: Number(e.target.value),
                    })
                  }
                  style={{ flex: 1, accentColor: "#4f46e5" }}
                />
                <span style={{ fontWeight: 600, width: "2.5rem", textAlign: "right" }}>
                  {circuitCfg.cooldown_seconds ?? 30}s
                </span>
              </div>
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
              <span style={{ color: "#6b7280" }}>半开探测请求数</span>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="range"
                  min={1}
                  max={20}
                  value={circuitCfg.half_open_probes ?? 3}
                  onChange={(e) =>
                    setCircuitDraft({
                      ...circuitCfg,
                      half_open_probes: Number(e.target.value),
                    })
                  }
                  style={{ flex: 1, accentColor: "#4f46e5" }}
                />
                <span style={{ fontWeight: 600, width: "1.5rem", textAlign: "right" }}>
                  {circuitCfg.half_open_probes ?? 3}
                </span>
              </div>
            </label>
          </div>
          <div
            style={{
              marginTop: "0.75rem",
              padding: "0.5rem 0.75rem",
              borderRadius: "0.5rem",
              background: "#f9fafb",
              border: "1px solid #e5e7eb",
              fontSize: "0.6875rem",
              color: "#4b5563",
            }}
          >
            <strong>熔断状态机</strong>：Closed（正常）→ 达到阈值 →{" "}
            <span style={{ color: "#ef4444" }}>
              Open（熔断中，直接返回降级响应）
            </span>{" "}
            → 等待熔断时长 →{" "}
            <span style={{ color: "#d97706" }}>Half-Open（放探测请求）</span> →
            成功率恢复 → Closed；否则回到 Open
          </div>
          <div style={{ marginTop: "0.75rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <button
              type="button"
              className="btn-nav-accent"
              disabled={circuitSaving}
              onClick={() => void saveCircuitConfig()}
            >
              {circuitSaving ? "保存中…" : "保存熔断配置"}
            </button>
            {circuitMsg && (
              <span style={{ fontSize: "0.7rem", color: circuitMsg.includes("失败") ? "#ef4444" : "#059669" }}>
                {circuitMsg}
              </span>
            )}
          </div>
        </div>
      )}

      {/* === Fallback 链可视化 === */}
      {activePanel === "fallback" && (
        <div style={{ padding: "1rem" }}>
          {v2Rules.length === 0 && <p className="muted">暂无路由规则</p>}
          {v2Rules.map((rule) => {
            const chain = rule.fallback_chain || [];
            const isPII = rule.id === "pii" || rule.egress?.includes("不出域");
            return (
              <div
                key={rule.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  fontSize: "0.75rem",
                  marginBottom: "0.75rem",
                }}
              >
                <span style={{ width: "5rem", color: "#6b7280", flexShrink: 0 }}>
                  {rule.task}
                </span>
                {chain.map((model, i) => {
                  const isEnd = model === "报错" || model === "拒绝" || model === "拒绝（不出域）";
                  const isPrimary = i === 0;
                  return (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      {i > 0 && (
                        <svg
                          width="16"
                          height="16"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="#9ca3af"
                          strokeWidth="1.5"
                        >
                          <path d="M5 12h14M13 6l6 6-6 6" strokeLinecap="round" />
                        </svg>
                      )}
                      <span
                        style={{
                          padding: "0.25rem 0.5rem",
                          borderRadius: "0.375rem",
                          fontSize: "0.6875rem",
                          fontWeight: 500,
                          ...(isEnd
                            ? {
                                background: isPII ? "#fee2e2" : "#fef3c7",
                                color: isPII ? "#dc2626" : "#d97706",
                              }
                            : isPrimary
                              ? {
                                  background: isPII ? "#dc2626" : "#4f46e5",
                                  color: "white",
                                }
                              : {
                                  background: isPII ? "#fecaca" : "#818cf8",
                                  color: "white",
                                }),
                        }}
                      >
                        {model}
                      </span>
                    </div>
                  );
                })}
                {chain.length === 0 && (
                  <span style={{ color: "#9ca3af", fontSize: "0.6875rem" }}>
                    {rule.primary}（无回退链）
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* === 路由测试面板 === */}
      {activePanel === "test" && (
        <div style={{ padding: "1rem" }}>
          <div style={{ display: "flex", gap: "0.75rem", marginBottom: "0.75rem" }}>
            <select
              className="mr-select"
              value={testRouteId}
              onChange={(e) => setTestRouteId(e.target.value)}
              aria-label="test-route-select"
              style={{ minWidth: "10rem" }}
            >
              {v2Rules.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.task}
                </option>
              ))}
            </select>
            <input
              value={testPrompt}
              onChange={(e) => setTestPrompt(e.target.value)}
              style={{ flex: 1, minWidth: "16rem" }}
              aria-label="test-prompt"
            />
            <button
              type="button"
              className="btn-primary"
              disabled={testLoading || !testRouteId || configVersion == null}
              onClick={() => void runRouteTest()}
            >
              {testLoading ? "测试中…" : "测试路由"}
            </button>
          </div>
          {testErr && <p className="error">{testErr}</p>}
          {testResult && (
            <div
              style={{
                borderRadius: "0.5rem",
                border: "1px solid #e5e7eb",
                padding: "0.75rem",
                background: "#f9fafb",
                fontSize: "0.75rem",
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: "0.5rem", color: "#1f2937" }}>
                路由测试结果
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
                <div>
                  <span style={{ color: "#6b7280" }}>策略: </span>
                  <strong>{testResult.strategy}</strong>
                </div>
                <div>
                  <span style={{ color: "#6b7280" }}>熔断状态: </span>
                  <span
                    style={{
                      color:
                        testResult.circuit_state === "closed"
                          ? "#059669"
                          : testResult.circuit_state === "open"
                            ? "#ef4444"
                            : "#d97706",
                      fontWeight: 600,
                    }}
                  >
                    {testResult.circuit_state}
                  </span>
                </div>
                <div>
                  <span style={{ color: "#6b7280" }}>选中模型: </span>
                  <strong>{testResult.selected?.[0]?.model || "—"}</strong>
                </div>
                <div>
                  <span style={{ color: "#6b7280" }}>选择原因: </span>
                  <span>{testResult.selected?.[0]?.reason || "—"}</span>
                </div>
                <div>
                  <span style={{ color: "#6b7280" }}>预估延迟: </span>
                  <strong>{testResult.estimated_latency_ms}ms</strong>
                </div>
                <div>
                  <span style={{ color: "#6b7280" }}>预估 Token: </span>
                  <span>
                    {testResult.estimated_input_tokens} → {testResult.estimated_output_tokens}
                  </span>
                </div>
              </div>
              {testResult.selected && testResult.selected.length > 1 && (
                <div style={{ marginTop: "0.5rem", fontSize: "0.6875rem", color: "#6b7280" }}>
                  <span>备选模型链: </span>
                  {testResult.selected.map((s, i) => (
                    <span key={i}>
                      {i > 0 && " → "}
                      <strong>{s.model}</strong> ({s.weight_pct}%)
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {circuitApi.err && (
        <p className="error" style={{ margin: "0.5rem 1rem" }}>
          {circuitApi.err === "Not Found" ? "熔断配置 API 未就绪" : circuitApi.err}
        </p>
      )}
    </div>
  );
}

type EvalSuiteSummary = {
  id: string;
  name: string;
  gate_threshold: number;
  cases?: Array<{
    inputs?: Record<string, unknown>;
    expected?: unknown;
    judge?: string;
  }>;
};

type EvalCaseResult = {
  case_id: string;
  passed: boolean;
  actual?: unknown;
  expected?: unknown;
  judge?: string;
  detail?: string;
};

type EvalReport = {
  report_id: string;
  suite_id: string;
  target_type: "logic_graph";
  target_id: string;
  target_revision: number;
  target_hash: string;
  results: EvalCaseResult[];
  pass_rate: number;
  passed: number;
  failed: number;
  total: number;
  gate_passed: boolean;
  run_at: string;
};

type EvalGateResult = {
  report_id: string;
  suite_id: string;
  target_type: "logic_graph";
  target_id: string;
  target_revision: number;
  target_hash: string;
  gate_passed: boolean;
  pass_rate: number;
  threshold: number;
  passed: number;
  failed: number;
  total: number;
  run_at: string;
};

export const QUICK_START_EVAL_SUITE = {
  name: "快速开始：加一函数",
  cases: [
    {
      name: "输入 1 返回 2",
      inputs: { x: 1 },
      expected: 2,
      judge: "exact",
    },
  ],
  gate_threshold: 1,
};

export function assertQuickStartSuite(suite: EvalSuiteSummary): void {
  const quickCase = suite.cases?.find((item) => (
    item.inputs?.x === 1 && item.expected === 2 && item.judge === "exact"
  ));
  if (
    !suite.id
    || suite.name !== QUICK_START_EVAL_SUITE.name
    || suite.gate_threshold !== QUICK_START_EVAL_SUITE.gate_threshold
    || !quickCase
  ) {
    throw new Error("基础套件回包核验失败");
  }
}

export function formatEvalValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export function assertEvalResultConsistency(
  suiteId: string,
  runReport: EvalReport,
  latestReport: EvalReport,
  gate: EvalGateResult,
): void {
  if (runReport.suite_id !== suiteId || latestReport.suite_id !== suiteId || gate.suite_id !== suiteId) {
    throw new Error("评测结果 suite_id 不一致");
  }
  if (runReport.run_at !== latestReport.run_at) {
    throw new Error("最新报告不是本次运行生成的报告");
  }
  const evidenceFields = ["report_id", "target_type", "target_id", "target_revision", "target_hash"] as const;
  for (const field of evidenceFields) {
    if (runReport[field] !== latestReport[field]) throw new Error(`运行与报告证据不一致：${field}`);
    if (latestReport[field] !== gate[field]) throw new Error(`报告与门控证据不一致：${field}`);
  }
  const fields = ["pass_rate", "passed", "failed", "total"] as const;
  for (const field of fields) {
    if (runReport[field] !== latestReport[field]) throw new Error(`运行与报告字段不一致：${field}`);
    if (latestReport[field] !== gate[field]) throw new Error(`报告与门控字段不一致：${field}`);
  }
  if (runReport.gate_passed !== latestReport.gate_passed) {
    throw new Error("运行与报告门控结论不一致");
  }
  if (gate.run_at !== latestReport.run_at) throw new Error("报告与门控运行时间不一致");
  if (latestReport.gate_passed !== gate.gate_passed) {
    throw new Error("报告与门控结论不一致");
  }
}

/** 81 · Evals 真实运行、报告与门控检查 */
export function EvalsPage() {
  const suitesApi = useJsonGet<{ items: EvalSuiteSummary[] }>("/v1/evals/suites");
  const graphsApi = useJsonGet<{ items: Array<{ id: string; name: string; revision: number; graph_hash: string; persisted: boolean }> }>("/v1/aip/logic/graphs");
  const [suiteId, setSuiteId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [report, setReport] = useState<EvalReport | null>(null);
  const [gate, setGate] = useState<EvalGateResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [runErr, setRunErr] = useState("");
  const [authorityRunId, setAuthorityRunId] = useState("");
  const [authorityRun, setAuthorityRun] = useState<EvalRunAuthority | null>(null);
  const [authorityState, setAuthorityState] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [authorityError, setAuthorityError] = useState("");

  const suites = suitesApi.data?.items || [];
  const graphs = graphsApi.data?.items || [];
  const selectedSuite = suites.find((suite) => suite.id === suiteId) || null;
  const selectedGraph = graphs.find((graph) => graph.id === targetId) || null;

  useEffect(() => {
    if (!suiteId && suites[0]?.id) setSuiteId(suites[0].id);
  }, [suiteId, suites]);
  useEffect(() => {
    if (!targetId && graphs[0]?.id) setTargetId(graphs[0].id);
  }, [graphs, targetId]);

  async function createQuickStartSuite() {
    setBusy(true);
    setMsg("");
    setRunErr("");
    setReport(null);
    setGate(null);
    try {
      const created = await apiPost<EvalSuiteSummary>("/v1/evals/suites", QUICK_START_EVAL_SUITE);
      assertQuickStartSuite(created);
      const reloaded = await apiGet<{ items: EvalSuiteSummary[] }>("/v1/evals/suites");
      const selected = (reloaded.items || []).find((suite) => suite.id === created.id);
      if (!selected) throw new Error("创建后重读未找到新套件");
      assertQuickStartSuite(selected);
      suitesApi.setData(reloaded);
      setSuiteId(created.id);
      setMsg(`已创建并选中真实套件“${created.name}”`);
    } catch (e) {
      setRunErr(`创建基础评测套件失败：${String((e as Error).message || e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function runSuite() {
    if (!suiteId || !selectedGraph) return;
    const payload = {
      suite_id: suiteId,
      target_type: "logic_graph",
      target_id: selectedGraph.id,
      target_revision: selectedGraph.revision,
      target_hash: selectedGraph.graph_hash,
    };
    setBusy(true);
    setMsg("");
    setRunErr("");
    setReport(null);
    setGate(null);
    try {
      const runReport = await apiPost<EvalReport>("/v1/evals/run", payload);
      const latestReport = await apiGet<EvalReport>(`/v1/evals/${encodeURIComponent(suiteId)}/report`);
      const gateResult = await apiPost<EvalGateResult>("/v1/evals/gate-check", {
        suite_id: suiteId,
        target_type: "logic_graph",
        target_id: selectedGraph.id,
        target_revision: selectedGraph.revision,
        target_hash: selectedGraph.graph_hash,
        reuse_latest_report: true,
      });
      assertEvalResultConsistency(suiteId, runReport, latestReport, gateResult);
      setGate(gateResult);
      setReport(latestReport);
      setMsg(
        gateResult.gate_passed
          ? `真实评测完成：门控通过（${gateResult.passed}/${gateResult.total}）`
          : `真实评测完成：门控未通过（${gateResult.passed}/${gateResult.total}）`,
      );
    } catch (e) {
      setRunErr(`评测运行失败：${String((e as Error).message || e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function refreshReport() {
    if (!suiteId || !selectedGraph) return;
    setRunErr("");
    setMsg("");
    setReport(null);
    setGate(null);
    try {
      const latestReport = await apiGet<EvalReport>(`/v1/evals/${encodeURIComponent(suiteId)}/report`);
      if (latestReport.suite_id !== suiteId) throw new Error("最新报告 suite_id 与当前套件不一致");
      if (
        latestReport.target_type !== "logic_graph"
        || latestReport.target_id !== selectedGraph.id
        || latestReport.target_revision !== selectedGraph.revision
        || latestReport.target_hash !== selectedGraph.graph_hash
      ) throw new Error("最新报告未绑定当前 Logic revision/hash");
      setReport(latestReport);
      setGate({
        report_id: latestReport.report_id,
        suite_id: latestReport.suite_id,
        target_type: latestReport.target_type,
        target_id: latestReport.target_id,
        target_revision: latestReport.target_revision,
        target_hash: latestReport.target_hash,
        gate_passed: latestReport.gate_passed,
        pass_rate: latestReport.pass_rate,
        threshold: selectedSuite?.gate_threshold ?? 0,
        passed: latestReport.passed,
        failed: latestReport.failed,
        total: latestReport.total,
        run_at: latestReport.run_at,
      });
      setMsg("已读取服务端最新评测报告");
    } catch (e) {
      setRunErr(`报告读取失败：${String((e as Error).message || e)}`);
    }
  }

  async function readAuthorityRun() {
    const runId = authorityRunId.trim();
    if (!runId) {
      setAuthorityError("请输入真实 Eval Run ID");
      setAuthorityState("idle");
      return;
    }
    setAuthorityRun(null);
    setAuthorityError("");
    setAuthorityState("loading");
    try {
      setAuthorityRun(await aipEvidenceSdk.evalRun(runId));
      setAuthorityState("loaded");
    } catch (error) {
      setAuthorityError(String((error as Error).message || error));
      setAuthorityState("error");
    }
  }

  return (
    <S2Chrome title="Evals 门控" lede="L4 自动化上线前须通过 Eval；未达标禁止发布为 Function / Automate。">
      <BpToolbar>
        <select
          aria-label="Eval 套件"
          className="aos-input"
          value={suiteId}
          onChange={(event) => {
            setSuiteId(event.target.value);
            setReport(null);
            setGate(null);
            setMsg("");
          }}
        >
          <option value="">选择 Eval 套件</option>
          {suites.map((suite) => (
            <option key={suite.id} value={suite.id}>{suite.name} · {suite.id}</option>
          ))}
        </select>
        <select
          aria-label="Eval Logic 目标"
          className="aos-input"
          value={targetId}
          onChange={(event) => {
            setTargetId(event.target.value);
            setReport(null);
            setGate(null);
            setMsg("");
          }}
        >
          <option value="">选择已保存 Logic Graph</option>
          {graphs.map((graph) => (
            <option key={graph.id} value={graph.id}>{graph.name} · revision {graph.revision}</option>
          ))}
        </select>
        <span className="aos-text">实际执行已保存 Logic revision/hash，不接受独立目标表达式</span>
        <button
          type="button"
          className="btn-primary"
          disabled={busy || !suiteId || !selectedGraph}
          onClick={() => void runSuite()}
        >
          {busy ? "真实评测中…" : "运行套件并检查门控"}
        </button>
        <button type="button" className="btn" disabled={!suiteId || !selectedGraph || busy} onClick={() => void refreshReport()}>
          读取最新报告
        </button>
        <button type="button" className="btn" disabled={busy} onClick={() => void createQuickStartSuite()}>
          创建基础评测套件
        </button>
        <Link to="/aip/maturity" className="btn-nav">
          ← 成熟度
        </Link>
      </BpToolbar>
      {suitesApi.loading && <p className="aos-text">正在读取 Eval 套件…</p>}
      {!suitesApi.loading && !suitesApi.err && suites.length === 0 && (
        <p className="error">暂无 Eval 套件，可创建下方基础套件后运行真实评测。</p>
      )}
      {msg && <p className="aos-text" role="status">{msg}</p>}
      {(suitesApi.err || graphsApi.err || runErr) && <p className="error" role="alert">{runErr || suitesApi.err || graphsApi.err}</p>}

      <BpBanner tone="info">
        <strong>快速开始样例</strong> · 套件“{QUICK_START_EVAL_SUITE.name}” · 用例：输入 x=1，期望 2（exact） · 门控阈值 100%。
        创建动作会真实写入 `/v1/evals/suites`，不会生成评测报告；运行时必须绑定已保存 Logic 的精确 revision/hash。
      </BpBanner>

      <BpScoreGrid
        items={[
          {
            value: report ? `${(report.pass_rate * 100).toFixed(1)}%` : "—",
            label: "总体通过率",
            hint: report ? `服务端报告 · ${report.run_at}` : "尚未运行真实评测",
            tone: report?.gate_passed ? "ok" : "warn",
          },
          {
            value: report ? String(report.total) : selectedSuite?.cases ? String(selectedSuite.cases.length) : "—",
            label: "测试用例",
            hint: report ? `通过 ${report.passed} · 失败 ${report.failed}` : "来自所选套件",
            tone: report?.failed === 0 && report.total > 0 ? "ok" : "warn",
          },
          {
            value: gate ? (gate.gate_passed ? "门控通过" : "门控阻断") : "未检查",
            label: "Eval 门控检查",
            hint: gate ? `阈值 ${(gate.threshold * 100).toFixed(1)}%` : "以 gate-check 回包为准",
            tone: gate?.gate_passed ? "ok" : "bad",
          },
        ]}
      />

      <BpTable
        columns={["用例", "评判", "期望", "实际", "结果", "详情"]}
        rows={(report?.results || []).map((result) => [
          result.case_id,
          result.judge || "—",
          formatEvalValue(result.expected),
          formatEvalValue(result.actual),
          result.passed ? "✅ 通过" : "❌ 失败",
          result.detail || "—",
        ])}
      />

      <BpBanner tone="warn">
        <strong>真实门控口径</strong> · 本页不提供手工绿灯。只有 gate-check 返回通过才显示 Eval 门控通过；L4 仍须 Draft 审批与其他发布护栏 ·{" "}
        <Link to="/aip/drafts">查看 Draft →</Link>
        {gate?.gate_passed && (
          <>
            {" · "}
            <Link to="/aip/studio">Chatbot Studio 测试 →</Link>
          </>
        )}
      </BpBanner>

      <section style={{ border: "1px solid var(--aos-border)", padding: 16, marginTop: 16 }} data-testid="eval-authority-reader">
        <h3 style={{ marginTop: 0 }}>AIP-4 权威 Eval Run 核查</h3>
        <p className="aos-text">旧评测执行入口保持兼容；此处只读 AIP-4 不可变 Run 引用，不允许手工修改状态或 revision/hash。</p>
        <BpToolbar>
          <input
            aria-label="eval-authority-run-id"
            value={authorityRunId}
            onChange={(event) => setAuthorityRunId(event.target.value)}
            placeholder="输入真实 eval-run ID"
          />
          <button type="button" className="btn" onClick={() => void readAuthorityRun()} disabled={authorityState === "loading"}>
            {authorityState === "loading" ? "读取中…" : "读取权威 Run"}
          </button>
        </BpToolbar>
        {authorityState === "idle" && !authorityError && <p className="aos-text">尚未选择权威 Eval Run。</p>}
        {authorityError && <p className="error" role="alert">权威 Eval Run 读取失败：{authorityError}</p>}
        {authorityRun && (
          <BpTable
            columns={["Run", "状态", "Suite revision/hash", "Target revision/hash", "Dataset revision/hash", "Judge revision/hash"]}
            rows={[ [
              authorityRun.runId,
              authorityRun.status,
              `${authorityRun.suiteRef.assetId}@${authorityRun.suiteRef.revision} · ${authorityRun.suiteRef.contentHash.slice(0, 12)}…`,
              `${authorityRun.target.assetId}@${authorityRun.target.revision} · ${authorityRun.target.contentHash.slice(0, 12)}…`,
              `${authorityRun.dataset.datasetId}@${authorityRun.dataset.revision} · ${authorityRun.dataset.contentHash.slice(0, 12)}…`,
              `${authorityRun.judge.judgeId}@${authorityRun.judge.revision} · ${authorityRun.judge.contentHash.slice(0, 12)}…`,
            ]]}
          />
        )}
      </section>

      <BpLinkRow
        links={[
          { to: "/aip/maturity", label: "成熟度楼梯" },
          { to: "/aip/logic", label: "Logic 画布" },
        ]}
      />
    </S2Chrome>
  );
}

export function DecisionLineagePage() {
  const [rootType, setRootType] = useState<LineageRootType>("task_run");
  const [rootId, setRootId] = useState("");
  const [events, setEvents] = useState<LineageEvent[]>([]);
  const [loadState, setLoadState] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [localErr, setLocalErr] = useState<string | null>(null);

  async function load() {
    const target = rootId.trim();
    if (!target) {
      setLocalErr("请输入真实 Root ID");
      setLoadState("idle");
      return;
    }
    setLocalErr(null);
    setEvents([]);
    setLoadState("loading");
    try {
      setEvents(await aipEvidenceSdk.lineage(rootType, target));
      setLoadState("loaded");
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
      setLoadState("error");
    }
  }

  const lineageId = events[0]?.lineageId ?? null;

  return (
    <S2Chrome
      title="Decision Lineage"
      lede="从服务端权威事件还原 TaskRun / Action / Eval / Publication / ResearchJob 因果链。"
    >
      <BpToolbar>
        <label className="muted">
          Root 类型{" "}
          <select value={rootType} onChange={(event) => setRootType(event.target.value as LineageRootType)} aria-label="lineage-root-type">
            {LINEAGE_ROOT_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
          </select>
        </label>
        <label className="muted">
          Root ID{" "}
          <input
            value={rootId}
            onChange={(e) => setRootId(e.target.value)}
            placeholder="输入真实 run / action / eval / publication ID"
            aria-label="lineage-root-id"
            style={{ minWidth: "12rem" }}
          />
        </label>
        <button type="button" className="btn" onClick={() => void load()} disabled={loadState === "loading"}>
          {loadState === "loading" ? "查询中…" : "查询权威谱系"}
        </button>
      </BpToolbar>

      {loadState === "idle" && !localErr && <BpBanner tone="info">请选择 Root 类型并输入真实 Root ID；页面不会展示示例 Trace 或固定步骤。</BpBanner>}
      {loadState === "loaded" && events.length === 0 && <BpBanner tone="warn"><span data-testid="lineage-empty">该 Root 暂无权威谱系事件。</span></BpBanner>}
      {localErr && <BpBanner tone="warn"><span data-testid="lineage-error">谱系读取失败：{localErr}</span></BpBanner>}

      {events.length > 0 && (
      <div
        data-testid="lineage-authority-timeline"
        style={{
          borderRadius: 2,
          border: "1px solid var(--aos-amber-border)",
          background: "var(--aos-amber-bg)",
          padding: "24px",
          marginTop: "1rem",
        }}
      >
        <div style={{ fontSize: 12, color: "var(--aos-muted)", marginBottom: 16 }}>
          Lineage <span style={{ fontFamily: "monospace", color: "var(--aos-text)" }}>{lineageId}</span>
          {" · "}{rootType}/{rootId} · {events.length} 个权威事件
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
          {events.map((event) => (
            <div
              key={event.eventId}
              style={{
                display: "flex",
                gap: 16,
                padding: "12px 0 12px 16px",
                marginLeft: 8,
                borderLeft: `2px solid ${event.quality === "measured" ? "var(--aos-green-600)" : event.quality === "estimated" ? "var(--aos-amber)" : "var(--aos-muted)"}`,
              }}
            >
              <div
                style={{
                  width: 80,
                  flexShrink: 0,
                  fontSize: 11,
                  textTransform: "uppercase",
                  color: "var(--aos-muted)",
                  paddingTop: 2,
                  letterSpacing: "0.05em",
                }}
              >
                #{event.sequence} {event.eventType}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ color: "var(--aos-text)", fontSize: 14 }}>{event.sourceKind || "无权威源类型"} · {event.sourceId || "无权威源 ID"}</div>
                <div style={{ fontSize: 12, color: "var(--aos-muted)", marginTop: 4 }}>
                  {event.quality} · 发生 {new Date(event.occurredAt).toLocaleString()} · 观测 {new Date(event.observedAt).toLocaleString()}
                </div>
                <div style={{ fontSize: 11, color: "var(--aos-muted)", marginTop: 4, fontFamily: "monospace", overflowWrap: "anywhere" }}>
                  event={event.eventId} · payload={event.payloadHash.slice(0, 12)}…{event.sourceHash ? ` · source=${event.sourceHash.slice(0, 12)}…` : ""}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: "1rem" }}>
        <Link
          to="/ontology/graph-health"
          style={{
            padding: "6px 12px",
            fontSize: 12,
            borderRadius: 2,
            border: "1px solid var(--aos-purple-border)",
            color: "var(--aos-purple-600)",
            textDecoration: "none",
          }}
        >
          图谱健康 →
        </Link>
        <Link
          to="/aip/evals"
          style={{
            padding: "6px 12px",
            fontSize: 12,
            borderRadius: 2,
            border: "1px solid var(--aos-border)",
            color: "var(--aos-text)",
            textDecoration: "none",
          }}
        >
          Evals 门控
        </Link>
        <Link
          to="/aip/drafts"
          style={{
            padding: "6px 12px",
            fontSize: 12,
            borderRadius: 2,
            border: "1px solid var(--aos-amber-border)",
            color: "var(--aos-amber-700)",
            textDecoration: "none",
          }}
        >
          Draft 审批台 →
        </Link>
      </div>
    </S2Chrome>
  );
}

// ── Provider Detail Page (222plan Phase A · 222 第23章) ───────────────────────

type Credential = {
  key_id: string;
  provider_id: string;
  label: string;
  key_masked: string;
  rotation_policy: string;
  last_rotated_at: string;
  next_rotation_at: string;
  rotation_history: Array<{ date: string; operator: string; old_key_tail: string }>;
  created_at: string;
};

type SecurityPolicy = {
  provider_id: string;
  content_filter: boolean;
  max_tokens: number;
  qps_limit: number;
  ip_allowlist: string[];
  audit_log: boolean;
  data_residency: string;
};

type CallLogEntry = {
  log_id: string;
  provider_id: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  cost_usd: number;
  status: string;
  trace_id: string;
  created_at: string;
};

type CallLogStats = {
  total_calls: number;
  success: number;
  failed: number;
  timeout: number;
  total_tokens: number;
  total_cost_usd: number;
  avg_latency_ms: number;
};

type DetailTab = "credentials" | "models" | "security" | "logs";

export function ProviderDetailPage() {
  const { providerId = "" } = useParams<{ providerId: string }>();
  const [tab, setTab] = useState<DetailTab>("credentials");
  const [creds, setCreds] = useState<Credential[]>([]);
  const [credsLoading, setCredsLoading] = useState(true);
  const [showAddKey, setShowAddKey] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newLabel, setNewLabel] = useState("默认");
  const [newPolicy, setNewPolicy] = useState("manual");
  const [security, setSecurity] = useState<SecurityPolicy | null>(null);
  const [logs, setLogs] = useState<CallLogEntry[]>([]);
  const [logStats, setLogStats] = useState<CallLogStats | null>(null);
  const [connResult, setConnResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);
  const [msg, setMsg] = useState("");

  function loadCreds() {
    setCredsLoading(true);
    apiGet<{ items?: Credential[] } | Credential[]>(`/api/models/providers/${providerId}/credentials`)
      .then((r) => setCreds(Array.isArray(r) ? r : (r.items || [])))
      .catch(() => setCreds([]))
      .finally(() => setCredsLoading(false));
  }

  function loadSecurity() {
    apiGet<SecurityPolicy>(`/api/models/providers/${providerId}/security`)
      .then(setSecurity)
      .catch(() => setSecurity(null));
  }

  function loadLogs() {
    apiGet<{ items: CallLogEntry[] }>(`/api/models/providers/${providerId}/logs?limit=50`)
      .then((r) => setLogs(r.items || []))
      .catch(() => setLogs([]));
    apiGet<CallLogStats>(`/api/models/providers/${providerId}/logs/stats`)
      .then(setLogStats)
      .catch(() => setLogStats(null));
  }

  useEffect(() => {
    loadCreds();
    loadSecurity();
    loadLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providerId]);

  function handleAddKey() {
    if (!newKey.trim()) return;
    apiPost<Credential>(`/api/models/providers/${providerId}/credentials`, {
      api_key: newKey.trim(),
      label: newLabel,
      rotation_policy: newPolicy,
    })
      .then(() => {
        setMsg("凭据已创建（KMS 加密存储）");
        setNewKey("");
        setShowAddKey(false);
        loadCreds();
      })
      .catch((e) => setMsg(`创建失败：${e}`));
  }

  function handleRotate(keyId: string) {
    const newApiKey = prompt("输入新的 API Key：");
    if (!newApiKey) return;
    apiPut<Credential>(`/api/models/providers/${providerId}/credentials/${keyId}`, {
      api_key: newApiKey,
    })
      .then(() => {
        setMsg("密钥已轮换");
        loadCreds();
      })
      .catch((e) => setMsg(`轮换失败：${e}`));
  }

  function handleDeleteKey(keyId: string) {
    if (!confirm("确认删除此凭据？此操作不可撤销。")) return;
    apiDelete(`/api/models/providers/${providerId}/credentials/${keyId}`)
      .then(() => {
        setMsg("凭据已删除");
        loadCreds();
      })
      .catch((e: unknown) => setMsg(`删除失败：${e}`));
  }

  function handleTestConnection() {
    setTesting(true);
    setConnResult(null);
    apiPost<{ ok: boolean; message: string; latency_ms?: number; model_count?: number }>(
      `/api/models/providers/${providerId}/test-connection`,
      {}
    )
      .then((r) => setConnResult(r))
      .catch((e) => setConnResult({ ok: false, message: String(e) }))
      .finally(() => setTesting(false));
  }

  function handleSaveSecurity() {
    if (!security) return;
    apiPut<SecurityPolicy>(`/api/models/providers/${providerId}/security`, security)
      .then(() => setMsg("安全策略已保存"))
      .catch((e) => setMsg(`保存失败：${e}`));
  }

  return (
    <S2Chrome
      title={`供应商详情 · ${providerId}`}
      lede="管理凭据、查看模型列表、配置安全策略、查看调用日志"
    >
      <Link to="/aip/model-providers" className="btn btn-nav">← 返回供应商列表</Link>

      {/* 供应商信息卡 */}
      <div className="bp-banner" style={{ marginTop: 12, marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ fontSize: 48 }}>🔌</div>
          <div>
            <h2 style={{ margin: 0 }}>{providerId}</h2>
            <p style={{ margin: "4px 0", color: "#666" }}>
              {creds.length > 0 ? `已配置 ${creds.length} 个凭据` : "未配置凭据"}
              {" · "}
              {logStats ? `${logStats.total_calls} 次调用` : ""}
            </p>
          </div>
        </div>
      </div>

      {msg && <p className="bp-prop-ok">{msg}</p>}

      {/* Tab 栏 */}
      <div style={{ display: "flex", gap: 4, borderBottom: "2px solid #e0e0e0", marginBottom: 16 }}>
        {([
          ["credentials", "凭据管理"],
          ["models", "模型列表"],
          ["security", "安全策略"],
          ["logs", "调用日志"],
        ] as [DetailTab, string][]).map(([t, label]) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            style={{
              padding: "8px 16px",
              border: "none",
              background: tab === t ? "#2563eb" : "transparent",
              color: tab === t ? "#fff" : "#333",
              borderRadius: "4px 4px 0 0",
              cursor: "pointer",
              fontWeight: tab === t ? 600 : 400,
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab 1: 凭据管理 */}
      {tab === "credentials" && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
            <h3>API Key 凭据</h3>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                className="btn btn-nav-accent"
                onClick={handleTestConnection}
                disabled={testing}
              >
                {testing ? "测试中…" : "测试连接"}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setShowAddKey((v) => !v)}
              >
                {showAddKey ? "取消" : "+ 添加凭据"}
              </button>
            </div>
          </div>

          {/* 连接测试结果 */}
          {connResult && (
            <div style={{
              padding: 12,
              borderRadius: 2,
              background: connResult.ok ? "#f0fdf4" : "#fef2f2",
              border: `1px solid ${connResult.ok ? "#86efac" : "#fca5a5"}`,
              marginBottom: 12,
            }}>
              <strong>{connResult.ok ? "✅ " : "❌ "}</strong>
              {connResult.message}
            </div>
          )}

          {/* 添加凭据表单 */}
          {showAddKey && (
            <div style={{
              padding: 16,
              borderRadius: 2,
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              marginBottom: 16,
            }}>
              <label style={{ display: "block", marginBottom: 8 }}>
                <span style={{ fontWeight: 600 }}>API Key</span>
                <input
                  type="password"
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  placeholder="sk-..."
                  style={{ width: "100%", padding: "8px 12px", borderRadius: 4, border: "1px solid #ccc", marginTop: 4 }}
                />
              </label>
              <div style={{ display: "flex", gap: 12, marginBottom: 8 }}>
                <label>
                  <span style={{ fontWeight: 600 }}>标签</span>
                  <input
                    value={newLabel}
                    onChange={(e) => setNewLabel(e.target.value)}
                    style={{ padding: "4px 8px", borderRadius: 4, border: "1px solid #ccc", marginLeft: 4 }}
                  />
                </label>
                <label>
                  <span style={{ fontWeight: 600 }}>轮换策略</span>
                  <select
                    value={newPolicy}
                    onChange={(e) => setNewPolicy(e.target.value)}
                    style={{ padding: "4px 8px", borderRadius: 4, border: "1px solid #ccc", marginLeft: 4 }}
                  >
                    <option value="manual">手动</option>
                    <option value="30d">每 30 天</option>
                    <option value="90d">每 90 天</option>
                  </select>
                </label>
              </div>
              <div style={{ fontSize: 12, color: "#666", marginBottom: 8 }}>
                密钥使用 AES-256-GCM 加密存储，不会明文落库。
              </div>
              <button type="button" className="btn btn-primary" onClick={handleAddKey} disabled={!newKey.trim()}>
                创建凭据
              </button>
            </div>
          )}

          {/* 凭据列表 */}
          {credsLoading ? (
            <p className="muted">加载中…</p>
          ) : creds.length === 0 ? (
            <p className="muted">暂无凭据。点击「+ 添加凭据」创建。</p>
          ) : (
            <table className="bp-table" style={{ width: "100%" }}>
              <thead>
                <tr>
                  <th>标签</th>
                  <th>Key（掩码）</th>
                  <th>KMS</th>
                  <th>轮换策略</th>
                  <th>上次轮换</th>
                  <th>下次轮换</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {creds.map((c) => (
                  <tr key={c.key_id}>
                    <td>{c.label}</td>
                    <td><code>{c.key_masked}</code></td>
                    <td><span className="mp-badge-ok">已加密</span></td>
                    <td>{c.rotation_policy === "manual" ? "手动" : c.rotation_policy === "30d" ? "每30天" : "每90天"}</td>
                    <td>{c.last_rotated_at ? new Date(c.last_rotated_at).toLocaleDateString() : "—"}</td>
                    <td>{c.next_rotation_at ? new Date(c.next_rotation_at).toLocaleDateString() : "—"}</td>
                    <td>
                      <button type="button" className="btn" onClick={() => handleRotate(c.key_id)}>轮换</button>
                      {" "}
                      <button type="button" className="btn" onClick={() => handleDeleteKey(c.key_id)}>删除</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {/* 轮换历史 */}
          {creds.some((c) => c.rotation_history.length > 0) && (
            <details style={{ marginTop: 16 }}>
              <summary style={{ cursor: "pointer", fontWeight: 600 }}>轮换历史</summary>
              {creds.filter((c) => c.rotation_history.length > 0).map((c) => (
                <div key={c.key_id} style={{ marginTop: 8 }}>
                  <strong>{c.label}</strong>（{c.key_masked}）
                  <ul>
                    {c.rotation_history.map((h, i) => (
                      <li key={i}>
                        {new Date(h.date).toLocaleString()} · {h.operator} · 旧Key: {h.old_key_tail}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </details>
          )}
        </div>
      )}

      {/* Tab 2: 模型列表 */}
      {tab === "models" && (
        <div>
          <h3>可用模型</h3>
          <p className="muted">
            模型列表来自供应商 API + 平台注册。点击「注册到路由」跳转路由配置页。
          </p>
          <ModelListTab providerId={providerId} />
        </div>
      )}

      {/* Tab 3: 安全策略 */}
      {tab === "security" && security && (
        <div>
          <h3>安全策略</h3>
          <div style={{ maxWidth: 600 }}>
            <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <input
                type="checkbox"
                checked={security.content_filter}
                onChange={(e) => setSecurity({ ...security, content_filter: e.target.checked })}
              />
              <span>内容过滤（PII 脱敏 + 敏感词过滤）</span>
            </label>

            <label style={{ display: "block", marginBottom: 12 }}>
              <span style={{ fontWeight: 600 }}>最大 Token 限制</span>
              <input
                type="number"
                value={security.max_tokens}
                onChange={(e) => setSecurity({ ...security, max_tokens: parseInt(e.target.value) || 0 })}
                style={{ width: 120, padding: "4px 8px", borderRadius: 4, border: "1px solid #ccc", marginLeft: 8 }}
              />
            </label>

            <label style={{ display: "block", marginBottom: 12 }}>
              <span style={{ fontWeight: 600 }}>QPS 限制</span>
              <input
                type="number"
                value={security.qps_limit}
                onChange={(e) => setSecurity({ ...security, qps_limit: parseInt(e.target.value) || 0 })}
                style={{ width: 120, padding: "4px 8px", borderRadius: 4, border: "1px solid #ccc", marginLeft: 8 }}
              />
            </label>

            <label style={{ display: "block", marginBottom: 12 }}>
              <span style={{ fontWeight: 600 }}>IP 白名单（CIDR，每行一条）</span>
              <textarea
                value={security.ip_allowlist.join("\n")}
                onChange={(e) => setSecurity({ ...security, ip_allowlist: e.target.value.split("\n").filter(Boolean) })}
                rows={4}
                placeholder="10.0.0.0/8&#10;192.168.0.0/16"
                style={{ width: "100%", padding: "8px 12px", borderRadius: 4, border: "1px solid #ccc", marginTop: 4 }}
              />
            </label>

            <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <input
                type="checkbox"
                checked={security.audit_log}
                onChange={(e) => setSecurity({ ...security, audit_log: e.target.checked })}
              />
              <span>审计日志（记录所有 prompt + response）</span>
            </label>

            <label style={{ display: "block", marginBottom: 12 }}>
              <span style={{ fontWeight: 600 }}>数据驻留</span>
              <select
                value={security.data_residency}
                onChange={(e) => setSecurity({ ...security, data_residency: e.target.value })}
                style={{ padding: "4px 8px", borderRadius: 4, border: "1px solid #ccc", marginLeft: 8 }}
              >
                <option value="provider">跟随供应商</option>
                <option value="local_cache">本地缓存（加密）</option>
                <option value="no_cache">不缓存</option>
              </select>
            </label>

            <button type="button" className="btn btn-primary" onClick={handleSaveSecurity}>
              保存策略
            </button>
          </div>
        </div>
      )}

      {/* Tab 4: 调用日志 */}
      {tab === "logs" && (
        <div>
          <h3>调用日志</h3>
          {logStats && (
            <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
              {[
                ["总调用", logStats.total_calls],
                ["成功", logStats.success],
                ["失败", logStats.failed],
                ["超时", logStats.timeout],
                ["总 Token", logStats.total_tokens.toLocaleString()],
                ["总费用", `$${logStats.total_cost_usd.toFixed(4)}`],
                ["平均延迟", `${logStats.avg_latency_ms}ms`],
              ].map(([label, val]) => (
                <div key={label} style={{
                  padding: "12px 16px",
                  borderRadius: 2,
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  textAlign: "center",
                  minWidth: 80,
                }}>
                  <div style={{ fontSize: 20, fontWeight: 700 }}>{val}</div>
                  <div style={{ fontSize: 12, color: "#666" }}>{label}</div>
                </div>
              ))}
            </div>
          )}
          {logs.length === 0 ? (
            <p className="muted">暂无调用记录。</p>
          ) : (
            <table className="bp-table" style={{ width: "100%" }}>
              <thead>
                <tr>
                  <th>时间</th>
                  <th>模型</th>
                  <th>输入/输出 Token</th>
                  <th>延迟</th>
                  <th>费用</th>
                  <th>状态</th>
                  <th>Trace ID</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.log_id}>
                    <td>{new Date(l.created_at).toLocaleString()}</td>
                    <td>{l.model || "—"}</td>
                    <td>{l.input_tokens} / {l.output_tokens}</td>
                    <td>{l.latency_ms}ms</td>
                    <td>${l.cost_usd.toFixed(4)}</td>
                    <td>
                      {l.status === "success" ? "✅" : l.status === "timeout" ? "⏱" : "❌"}
                      {" "}{l.status}
                    </td>
                    <td>
                      {l.trace_id ? (
                        <Link to={`/aip/observability?trace=${l.trace_id}`}>{l.trace_id.slice(0, 8)}</Link>
                      ) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </S2Chrome>
  );
}

// ── Model List Tab (Tab 2) ────────────────────────────────────

function ModelListTab({ providerId }: { providerId: string }) {
  const { data: models } = useJsonGet<{
    items?: Array<{ id: string; provider?: string }>;
  }>("/v1/aip/models");

  const providerModels = (models?.items || []).filter(
    (m) => m.provider === providerId || m.id.toLowerCase().includes(providerId.split("-")[0])
  );

  const knownModels: Array<{ id: string; name: string; context: string; price: string; tags: string[] }> = ({
    openai: [
      { id: "gpt-4o-2024-08-06", name: "GPT-4o", context: "128K", price: "$2.50/1M", tags: ["chat", "vision", "function-calling"] },
      { id: "gpt-4o-mini-2024-07-18", name: "GPT-4o mini", context: "128K", price: "$0.15/1M", tags: ["chat", "function-calling"] },
      { id: "o1-preview", name: "o1-preview", context: "128K", price: "$15/1M", tags: ["reasoning"] },
    ],
    anthropic: [
      { id: "claude-3-5-sonnet-20241022", name: "Claude 3.5 Sonnet", context: "200K", price: "$3/1M", tags: ["chat", "vision"] },
      { id: "claude-3-opus-20240229", name: "Claude 3 Opus", context: "200K", price: "$15/1M", tags: ["chat"] },
    ],
    deepseek: [
      { id: "deepseek-chat", name: "DeepSeek Chat", context: "64K", price: "¥1/1M", tags: ["chat"] },
      { id: "deepseek-reasoner", name: "DeepSeek Reasoner", context: "64K", price: "¥4/1M", tags: ["reasoning"] },
    ],
  } as Record<string, Array<{ id: string; name: string; context: string; price: string; tags: string[] }>>)[providerId] || [];

  if (knownModels.length === 0 && providerModels.length === 0) {
    return (
      <div>
        <p className="muted">该供应商暂无已知模型列表。</p>
        <p className="muted">
          可以点击「测试连接」获取供应商可用模型列表。
        </p>
      </div>
    );
  }

  return (
    <table className="bp-table" style={{ width: "100%" }}>
      <thead>
        <tr>
          <th>模型 ID</th>
          <th>显示名</th>
          <th>上下文窗口</th>
          <th>价格</th>
          <th>能力标签</th>
          <th>已注册</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        {knownModels.map((m) => {
          const registered = providerModels.some((pm) => pm.id === m.id);
          return (
            <tr key={m.id}>
              <td><code>{m.id}</code></td>
              <td>{m.name}</td>
              <td>{m.context}</td>
              <td>{m.price}</td>
              <td>{m.tags.map((t) => <span key={t} className="mp-badge-ok" style={{ marginRight: 4 }}>{t}</span>)}</td>
              <td>{registered ? "✅" : "❌"}</td>
              <td>
                <Link to="/aip/model-router" className="btn">注册到路由</Link>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
