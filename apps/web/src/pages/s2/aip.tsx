import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, apiPut, S2Chrome, useJsonGet } from "./shared";
import {
  BpBanner,
  BpDebugPanel,
  BpLineageTimeline,
  BpLinkRow,
  BpMetricGrid,
  BpPropGrid,
  BpScoreGrid,
  BpTable,
  BpToolbar,
  BpToolGrid,
} from "./blueprintUi";
import { MODEL_CONFIG_NO_VAULT } from "../../lib/productCopy";

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

type ProviderView = "list" | "configure" | "credentials" | "studio";

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
                  <button
                    type="button"
                    className="btn-nav"
                    disabled
                    title="网关运行态由环境 / 边车托管，不走插件「启用/取消就绪」；要下线请改网关配置或停边车"
                  >
                    运行态托管
                  </button>
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
          {!loading && (data?.items?.length || 0) === 0 && installedPlugins.length === 0 && (
            <p className="muted">暂无已安装插件 · 从下方目录安装（DeepSeek 等）</p>
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
  const routesApi = useJsonGet<{ items: RouteRule[] }>("/v1/aip/model-routes");
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
  const [routeRows, setRouteRows] = useState<RouteRule[]>([]);
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
    if (routesApi.data?.items?.length) {
      setRouteRows(routesApi.data.items);
    }
  }, [routesApi.data]);

  function patchRow(id: string, patch: Partial<RouteRule>) {
    setRouteRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));
    setSaveMsg("");
  }

  async function saveRoutes() {
    setSaving(true);
    setLocalErr(null);
    setSaveMsg("");
    try {
      const r = await apiPut<{ items: RouteRule[] }>("/v1/aip/model-routes", { items: routeRows });
      setRouteRows(r.items || routeRows);
      setSaveMsg("路由策略已保存");
      routesApi.reload();
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
    } finally {
      setSaving(false);
    }
  }

  async function runCircuitDrill() {
    setDrillMsg("");
    setLocalErr(null);
    try {
      const r = await apiPost<{ message?: string }>("/v1/aip/model-routes/circuit-drill", {
        items: routeRows,
      });
      setDrillMsg(String(r.message || "演练完成"));
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
    }
  }

  function exportAuditSnapshot() {
    const blob = new Blob(
      [JSON.stringify({ items: routeRows, exportedAt: new Date().toISOString() }, null, 2)],
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
      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            models.reload();
            routesApi.reload();
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
      {(models.err || warm.err || routesApi.err || localErr) && (
        <p className="error">
          {routesApi.err === "Not Found"
            ? "路由策略接口未就绪（/v1/aip/model-routes 404）· 请重启 aos-api 后点刷新"
            : models.err || warm.err || routesApi.err || localErr}
        </p>
      )}

      <p className="mr-hint">
        本页只选<strong>已就绪</strong>模型做策略。新装插件（如 DeepSeek）须在供应商页点「启用就绪」或「保存并启用」后，再回本页刷新。
      </p>

      <div className="mr-rules-card">
        <div className="mr-rules-head">
          <h2 className="mr-rules-title">路由规则</h2>
          <span className="mr-rules-meta">任务类型 / 回退 / 出境 · 可编辑</span>
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
            disabled={saving || routeRows.length === 0}
            onClick={() => void saveRoutes()}
          >
            {saving ? "保存中…" : "保存策略"}
          </button>
          <button type="button" className="btn-nav" onClick={() => void runCircuitDrill()}>
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
    </S2Chrome>
  );
}

/** 81 · 对齐 aip-evals.html · 门控指标 + API green/l4Allowed */
export function EvalsPage() {
  const { data, err, reload } = useJsonGet<{ green?: boolean; l4Allowed?: boolean }>(
    "/v1/aip/evals",
  );
  const [msg, setMsg] = useState("");

  async function setGate(green: boolean) {
    await apiPost("/v1/aip/evals", { green });
    setMsg(green ? "门控已放行" : "门控已阻断");
    reload();
  }

  const green = data?.green === true;
  const l4Allowed = data?.l4Allowed === true;

  return (
    <S2Chrome title="Evals 门控" lede="L4 自动化上线前须通过 Eval；未达标禁止发布为 Function / Automate。">
      <BpToolbar>
        <button type="button" className="btn-primary" onClick={() => void setGate(true)}>
          运行 Eval 套件 / 放行
        </button>
        <button type="button" className="btn" onClick={() => void setGate(false)}>
          阻断
        </button>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <Link to="/aip/maturity" className="btn-nav">
          ← 成熟度
        </Link>
      </BpToolbar>
      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}

      <BpScoreGrid
        items={[
          {
            value: green ? "≥92%" : "87%",
            label: "总体通过率",
            hint: green ? "门控已绿" : "未达 L4 门槛",
            tone: green ? "ok" : "warn",
          },
          {
            value: green ? "42" : "—",
            label: "测试用例（登记）",
            hint: "含回归黄金集",
            tone: "warn",
          },
          {
            value: l4Allowed ? "L4 可申请" : "L4 未达标",
            label: "自动化门控",
            hint: l4Allowed ? "Eval 绿且未熔断" : "须 Eval ≥92% + Draft",
            tone: l4Allowed ? "ok" : "bad",
          },
        ]}
      />

      <BpTable
        columns={["分项", "结果", "状态"]}
        rows={[
          ["Eval 绿灯", green ? "通过" : "未通过", green ? "✅" : "❌"],
          ["L4 允许", l4Allowed ? "是" : "否", l4Allowed ? "✅" : "❌"],
          ["Draft HITL", "默认暂存", "✅"],
          ["熔断", l4Allowed ? "关闭" : "可能开启", l4Allowed ? "✅" : "⚠"],
        ]}
      />

      <BpBanner tone="warn">
        <strong>L4 门控状态</strong> · 须 Eval 绿且 Draft 审批通过后方可申请 L4 上线 ·{" "}
        <Link to="/aip/drafts">查看 Draft →</Link>
        {green && (
          <>
            {" · "}
            <Link to="/aip/studio">Chatbot Studio 测试 →</Link>
          </>
        )}
      </BpBanner>

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
  const [lineageId, setLineageId] = useState("");
  const [lineage, setLineage] = useState<{
    id?: string;
    draftId?: string;
    actionTypeId?: string;
    objectType?: string;
    objectId?: string;
    steps?: { step?: string; [key: string]: unknown }[];
  } | null>(null);
  const [localErr, setLocalErr] = useState<string | null>(null);
  const [govMsg, setGovMsg] = useState("");
  const [gov, setGov] = useState<{
    asPublicViewer?: { redactedFields?: string[]; internalCost?: unknown };
    markingForbidden?: { code?: string };
    latestLineage?: { id?: string; objectId?: string; actionTypeId?: string };
    objectId?: string;
    objectType?: string;
  } | null>(null);

  async function load(id?: string) {
    const target = id || lineageId;
    if (!target) return;
    setLocalErr(null);
    try {
      const r = await apiGet<{
        id: string;
        draftId?: string;
        actionTypeId?: string;
        objectType?: string;
        objectId?: string;
        steps?: { step?: string; [key: string]: unknown }[];
      }>(`/v1/aip/lineage/${encodeURIComponent(target)}`);
      setLineage(r);
      setLineageId(r.id);
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
      setLineage(null);
    }
  }

  async function loadGovernance() {
    setLocalErr(null);
    setGovMsg("");
    try {
      const r = await apiGet<{
        asPublicViewer?: { redactedFields?: string[]; internalCost?: unknown };
        markingForbidden?: { code?: string };
        latestLineage?: { id?: string; objectId?: string; actionTypeId?: string };
        objectId?: string;
        objectType?: string;
        say?: string;
      }>("/v1/demo/governance");
      setGov(r);
      const red = (r.asPublicViewer?.redactedFields || []).join(",") || "(none)";
      setGovMsg(
        `治理 OK · 脱敏=${red} · FORBIDDEN=${r.markingForbidden?.code ?? "n/a"} · lineage=${r.latestLineage?.id ?? "暂无（先写回）"}`,
      );
      if (r.latestLineage?.id) {
        await load(r.latestLineage.id);
      }
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
      setGov(null);
    }
  }

  const stepLabel: Record<string, string> = {
    read: "输入",
    draft: "Draft",
    approve: "批准",
    write: "写生产",
  };

  const timelineSteps = [
    ...(lineage
      ? [
          {
            phase: "Trace",
            title: `${lineage.id} · ${lineage.actionTypeId || "Action"}`,
            subtitle: `${lineage.objectType}/${lineage.objectId} · draft=${lineage.draftId}`,
            tone: "input" as const,
          },
          ...(lineage.steps || []).map((s) => {
            const key = String(s.step || "process");
            return {
              phase: stepLabel[key] || key,
              title:
                key === "write"
                  ? `合并字段：${((s.mergedKeys as string[]) || []).join(", ") || "—"}`
                  : key === "approve"
                    ? `审批人：${s.actor || "—"}`
                    : key === "draft"
                      ? `Draft ${s.draftId || "—"}`
                      : `${s.objectType}/${s.objectId}`,
              subtitle:
                key === "write" && Array.isArray(s.conflicts) && s.conflicts.length > 0
                  ? `冲突 ${s.conflicts.length} 项（已允许合并）`
                  : undefined,
              tone:
                key === "read"
                  ? ("input" as const)
                  : key === "write"
                    ? ("output" as const)
                    : ("process" as const),
            };
          }),
        ]
      : []),
    ...(gov?.markingForbidden?.code
      ? [
          {
            phase: "治理",
            title: `Marking ${gov.markingForbidden.code}`,
            subtitle: `public 视角脱敏：${(gov.asPublicViewer?.redactedFields || []).join(", ") || "—"}`,
            tone: "fuse" as const,
          },
        ]
      : []),
  ];

  return (
    <S2Chrome
      title="Decision Lineage"
      lede="单次 Agent 决策的完整因果链：输入 → 工具 → 模型 → 输出 → 副作用。"
    >
      <BpToolbar>
        <button type="button" className="btn" onClick={() => void loadGovernance()}>
          治理探针
        </button>
        <label className="muted">
          Trace{" "}
          <input
            value={lineageId}
            onChange={(e) => setLineageId(e.target.value)}
            placeholder="lin-…"
            style={{ minWidth: "12rem" }}
          />
        </label>
        <button type="button" className="btn" onClick={() => void load()}>
          查询
        </button>
      </BpToolbar>

      {govMsg && <p className="aos-text">{govMsg}</p>}
      {gov && (
        <BpMetricGrid
          items={[
            {
              label: "public 脱敏字段",
              value: (gov.asPublicViewer?.redactedFields || []).join(", ") || "—",
              tone: "warn",
            },
            {
              label: "internalCost (public)",
              value: String(gov.asPublicViewer?.internalCost ?? "—"),
              tone: "muted",
            },
            {
              label: "Marking 拒绝",
              value: gov.markingForbidden?.code ?? "—",
              tone: gov.markingForbidden?.code ? "ok" : "muted",
            },
            {
              label: "最近谱系",
              value: gov.latestLineage?.id ?? "暂无",
              tone: gov.latestLineage?.id ? "ok" : "bad",
            },
          ]}
        />
      )}

      {timelineSteps.length > 0 ? (
        <BpLineageTimeline steps={timelineSteps} />
      ) : (
        <p className="muted" style={{ marginTop: "0.75rem" }}>
          暂无谱系 · 请先在 Draft 审批台批准写入，再点治理探针
        </p>
      )}

      {localErr && <p className="error">{localErr}</p>}

      <BpLinkRow
        links={[
          { to: "/aip/drafts", label: "Draft 审批台" },
          { to: "/ontology/graph-health", label: "图谱健康" },
          { to: "/aip/evals", label: "Evals 门控" },
        ]}
      />
    </S2Chrome>
  );
}
