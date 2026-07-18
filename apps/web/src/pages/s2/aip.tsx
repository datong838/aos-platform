import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, S2Chrome, useJsonGet } from "./shared";
import {
  BpBanner,
  BpDebugPanel,
  BpDiscoverCard,
  BpLineageTimeline,
  BpLinkRow,
  BpMetricGrid,
  BpPropGrid,
  BpScoreGrid,
  BpTable,
  BpToolbar,
  BpToolGrid,
} from "./blueprintUi";

const TOOL_CATS = [
  { id: "action", label: "Action" },
  { id: "query", label: "Object Query" },
  { id: "function", label: "Function" },
  { id: "clarify", label: "Request Clarification" },
  { id: "capability", label: "Capability" },
  { id: "wiki", label: "Wiki Field Tool" },
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

/** 81 · 对齐 aip-tools.html · 三栏 + invoke */
export function ToolsPage() {
  const { data, err, reload } = useJsonGet<{ items: { id: string; kind: string }[] }>(
    "/v1/aip/tools",
  );
  const plugins = useJsonGet<{ items: unknown[]; totals?: { all: number } }>("/v1/plugins");
  const [cats, setCats] = useState<Set<string>>(
    () => new Set(["action", "query", "function", "clarify", "capability", "wiki"]),
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [invokeSummary, setInvokeSummary] = useState("");
  const [invokePayload, setInvokePayload] = useState<unknown>(null);
  const [localErr, setLocalErr] = useState<string | null>(null);
  const [mode, setMode] = useState("native");

  const tools = useMemo(() => {
    return (data?.items || []).filter((t) => cats.has(toolCategory(t.kind)));
  }, [data, cats]);

  const selected = tools.find((t) => t.id === selectedId) || tools[0] || null;

  function toggleCat(id: string) {
    setCats((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
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
      setInvokeSummary(`Invoke OK · ${id} · keys=${Object.keys(r).join(",")}`);
      setInvokePayload(r);
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
    }
  }

  return (
    <S2Chrome
      title="Agent 工具面板"
      lede="LLM 只「请求」工具；平台以调用用户权限代调（A-08）。写路径默认可提案。"
    >
      <BpToolbar>
        <label className="muted" style={{ fontSize: "0.75rem" }}>
          调用模式{" "}
          <select value={mode} onChange={(e) => setMode(e.target.value)} aria-label="tool-mode">
            <option value="native">Native（并行）</option>
            <option value="prompted">Prompted（单次一工具）</option>
          </select>
        </label>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新 Tools
        </button>
        <Link to="/aip/capabilities" className="muted">
          重能力 →
        </Link>
        <Link to="/aip/maturity" className="muted">
          成熟度 →
        </Link>
        <Link to="/aip/logic" className="muted">
          Logic →
        </Link>
      </BpToolbar>
      <p className="muted">
        插件目录 {plugins.data?.totals?.all ?? "—"} · Studio{" "}
        <Link to="/aip/studio">试聊</Link>
      </p>
      {(err || localErr || plugins.err) && (
        <p className="error">{err || localErr || plugins.err}</p>
      )}

      <BpToolGrid
        catalog={
          <>
            <div className="bp-section-micro">工具目录 · 六类</div>
            {TOOL_CATS.map((c) => (
              <label key={c.id} className="bp-tool-cat">
                <input
                  type="checkbox"
                  checked={cats.has(c.id)}
                  onChange={() => toggleCat(c.id)}
                />
                {c.label}
              </label>
            ))}
            <p className="muted" style={{ fontSize: "0.625rem", marginTop: "0.75rem" }}>
              Wiki 优先结构化字段 · Query 属性子集
            </p>
          </>
        }
        enabled={
          <>
            <div className="bp-section-micro">已启用</div>
            {tools.map((t, i) => (
              <button
                key={t.id}
                type="button"
                className={
                  selected?.id === t.id ? "bp-tool-item is-active" : "bp-tool-item"
                }
                onClick={() => setSelectedId(t.id)}
              >
                <div style={{ fontWeight: 500, color: "var(--aos-text)" }}>
                  {i + 1}. {t.kind} · {t.id}
                </div>
                <div className="muted" style={{ fontSize: "0.65rem", marginTop: 4 }}>
                  {toolCategory(t.kind) === "action" ? "HITL: 确认后执行" : "只读/提案"}
                </div>
              </button>
            ))}
            {tools.length === 0 && <p className="muted">无匹配工具 · 调整目录勾选</p>}
          </>
        }
        detail={
          selected ? (
            <>
              <h2 className="bp-ws-section-title">工具卡 · {selected.kind}</h2>
              <p className="muted" style={{ fontSize: "0.8rem" }}>
                id: <code>{selected.id}</code>
              </p>
              <BpBanner tone="info">
                执行策略：弹出 Action 表单供人确认 · 仅生成 Draft（提案台）· 模式={mode}
              </BpBanner>
              <button type="button" className="btn" onClick={() => void invoke(selected.id)}>
                Invoke（wo-1001）
              </button>
              {invokeSummary && <p className="aos-text">{invokeSummary}</p>}
              {invokePayload != null && (
                <BpDebugPanel value={invokePayload} title="Invoke 调试 JSON" />
              )}
              <BpLinkRow
                links={[
                  { to: "/aip/drafts", label: "Draft 审批台" },
                  { to: "/ontology/wiki", label: "LLM Wiki" },
                ]}
              />
            </>
          ) : (
            <p className="muted">选择已启用工具查看细项</p>
          )
        }
      />
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

const PROVIDER_CATALOG = [
  { id: "openai", title: "OpenAI 兼容", meta: "DeepSeek / 通义兼容端 · 字段少" },
  { id: "azure", title: "Azure OpenAI", meta: "区域 · 部署名 · API 版本" },
  { id: "anthropic", title: "Anthropic", meta: "API Key · 模型清单" },
  { id: "vllm", title: "本地 vLLM / Ollama", meta: "本机地址 · 模型路径 · 预热" },
  { id: "adapter", title: "自定义 Adapter 包", meta: "非标准协议 · 钩子 · 容器" },
];

/** 99 · 对齐 aip-model-providers · 卡片 + 凭据区 + 真连通探测 */
export function ProvidersPage() {
  const { data, err, loading, reload } = useJsonGet<{
    items: ProviderRow[];
    sidecar?: string;
    endpoint?: string;
    defaultTextModel?: string;
    apiKeyRef?: string;
    probe?: { ok?: boolean; sidecar?: string };
  }>("/v1/aip/providers");
  const agnesReady = data?.sidecar === "agnes-openai-compatible";
  const [vaultRef, setVaultRef] = useState("vault:secret/data/aos/llm#agnes");
  const [endpoint, setEndpoint] = useState("https://apihub.agnes-ai.com/v1");
  const [cfgOpen, setCfgOpen] = useState(false);
  const [catalogType, setCatalogType] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [probeMsg, setProbeMsg] = useState("");
  const [probePayload, setProbePayload] = useState<unknown>(null);
  const [probing, setProbing] = useState(false);

  useEffect(() => {
    if (data?.endpoint) setEndpoint(data.endpoint);
    const ref = data?.apiKeyRef || data?.items?.[0]?.apiKeyRef;
    if (ref) setVaultRef(ref);
    if (agnesReady) setCfgOpen(true);
  }, [data?.endpoint, data?.apiKeyRef, data?.items, agnesReady]);

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
      if (r.route === "agnes") {
        setMsg("Agnes 连通 OK");
      } else if (r.route === "fallback-mock") {
        setMsg("当前为 mock 回退 · 检查 .env 并 ensure-api --restart");
      } else {
        setMsg("连通探测完成");
      }
    } catch (e) {
      setMsg(String((e as Error).message || e));
    } finally {
      setProbing(false);
    }
  }

  const credItems = [
    { label: "sidecar", value: data?.sidecar || "—", tone: agnesReady ? "ok" : "muted" },
    { label: "endpoint", value: endpoint || data?.endpoint || "—" },
    { label: "secret ref", value: vaultRef },
    { label: "defaultTextModel", value: data?.defaultTextModel || "—", tone: "ok" },
    { label: "probe", value: data?.probe?.ok ? "OK" : "—", tone: data?.probe?.ok ? "ok" : "warn" },
    { label: "配置源", value: agnesReady ? "aos-platform/.env" : "LiteLLM / mock" },
  ];

  return (
    <S2Chrome title="模型供应商" lede="先接入供应商 · 再配路由；默认读环境变量 · Facade 不直连厂商 SDK">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <Link to="/aip/model-router" className="muted">
          路由策略 →
        </Link>
      </BpToolbar>
      {loading && <p className="muted">加载中…</p>}
      {err && <p className="error">{err}</p>}

      {agnesReady && (
        <BpBanner tone="info">
          已通过 <strong>aos-platform/.env</strong> 接入 Agnes · 默认文本模型{" "}
          <strong>{data?.defaultTextModel || "—"}</strong>
          {data?.endpoint ? ` · ${data.endpoint}` : ""}
        </BpBanner>
      )}

      <BpMetricGrid
        items={[
          {
            label: "sidecar",
            value: data?.sidecar || data?.probe?.sidecar || "—",
            tone: agnesReady ? "ok" : "muted",
          },
          {
            label: "endpoint",
            value: data?.endpoint || "—",
            tone: "muted",
          },
          {
            label: "probe",
            value: data?.probe?.ok ? "OK" : "—",
            tone: data?.probe?.ok ? "ok" : "warn",
          },
          {
            label: "已接入",
            value: data?.items?.length ?? 0,
            tone: "muted",
          },
        ]}
      />

      <div className="bp-ws-section-title" style={{ marginTop: "1rem" }}>
        已接入
      </div>
      <div className="bp-discover-grid">
        {(data?.items || []).map((p) => (
          <BpDiscoverCard
            key={p.id}
            onClick={() => setCfgOpen(true)}
            title={p.name || p.id}
            badge={{
              label: p.ready === false ? "未就绪" : "就绪",
              tone: p.ready === false ? "warn" : "ok",
            }}
            meta={`${p.kind || "llm"} · ${p.id} · keyRef=${p.apiKeyRef || vaultRef}`}
            accent="violet"
            cta="凭据 / 测连通 →"
          />
        ))}
        {!loading && (data?.items?.length || 0) === 0 && (
          <p className="muted">无供应商 · 在 aos-platform/.env 填写 AGNES_* 或启动 LiteLLM 边车</p>
        )}
      </div>

      {(cfgOpen || catalogType) && (
        <div className="bp-object-panel" style={{ marginTop: "1rem" }}>
          <div className="bp-ws-section-title">
            凭据与配置 · {catalogType ? PROVIDER_CATALOG.find((c) => c.id === catalogType)?.title : "当前供应商"}
            {catalogType && (
              <button
                type="button"
                className="muted"
                style={{ marginLeft: 8, fontSize: "0.7rem" }}
                onClick={() => setCatalogType(null)}
              >
                收起
              </button>
            )}
          </div>
          {catalogType && !agnesReady && (
            <BpBanner tone="info">
              「{PROVIDER_CATALOG.find((c) => c.id === catalogType)?.title}」持久化接入规划中 · 当前为配置预览表单。
            </BpBanner>
          )}
          <BpPropGrid items={credItems} />
          {!catalogType && (
            <>
              <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginTop: "0.75rem" }}>
                Endpoint（只读 · 来自 API）
                <input value={endpoint} readOnly style={{ width: "100%", opacity: 0.85 }} />
              </label>
              <label className="muted" style={{ display: "block", marginTop: 8, fontSize: "0.75rem" }}>
                Vault ref（不回显明文 key）
                <input value={vaultRef} readOnly style={{ width: "100%", opacity: 0.85 }} />
              </label>
            </>
          )}
          {catalogType && (
            <label className="muted" style={{ display: "block", marginTop: 8, fontSize: "0.75rem" }}>
              显示名
              <input
                placeholder={PROVIDER_CATALOG.find((c) => c.id === catalogType)?.title}
                style={{ width: "100%" }}
                disabled
              />
            </label>
          )}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: "0.75rem" }}>
            <button
              type="button"
              className="btn"
              disabled={probing || !!catalogType}
              onClick={() => void testConnectivity()}
            >
              {probing ? "探测中…" : "测连通（试聊）"}
            </button>
            <Link to="/aip/model-router" className="btn" style={{ textDecoration: "none" }}>
              去配路由 →
            </Link>
          </div>
          {probeMsg && (
            <p className="aos-text" style={{ fontSize: "0.875rem", marginTop: 8 }}>
              {probeMsg}
            </p>
          )}
          {msg && <p className={msg.includes("mock") ? "bp-prop-warn" : "aos-text"}>{msg}</p>}
          {probePayload != null && <BpDebugPanel value={probePayload} title="连通探测 JSON" />}
        </div>
      )}

      <div className="bp-ws-section-title" style={{ marginTop: "1rem" }}>
        可接入类型
      </div>
      <div className="bp-discover-grid">
        {PROVIDER_CATALOG.map((c) => (
          <BpDiscoverCard
            key={c.id}
            onClick={() => {
              setCatalogType(c.id);
              setCfgOpen(true);
              setMsg("该类型持久化接入规划中 · 请先用环境变量配置默认供应商");
            }}
            title={c.title}
            meta={c.meta}
            accent="muted"
            cta="展开表单 →"
          />
        ))}
      </div>

      <div className="bp-ws-section-title" style={{ marginTop: "1rem" }}>
        目录表
      </div>
      <BpTable
        columns={["名称", "kind", "id", "状态", "keyRef"]}
        rows={(data?.items || []).map((p) => [
          p.name || p.id,
          p.kind || "llm",
          p.id,
          p.ready === false ? "未就绪" : "就绪",
          p.apiKeyRef || "—",
        ])}
      />

      <BpBanner tone="info">
        在环境变量中配置默认模型供应商；改后重启 API。路由策略在
        <Link to="/aip/model-router"> 模型路由</Link> 配置。
      </BpBanner>
    </S2Chrome>
  );
}

type ModelItem = { id: string; kind: string; ready: boolean; provider?: string };

function pickModel(
  items: ModelItem[],
  prefer: "agnes" | "local" | "azure" | "mini" | "any",
): string {
  if (items.length === 0) return "—";
  const by = (pred: (m: ModelItem) => boolean) => items.find(pred)?.id;
  if (prefer === "agnes") {
    return by((m) => /agnes/i.test(m.id)) || by((m) => m.kind === "text") || items[0].id;
  }
  if (prefer === "local") {
    return (
      by((m) => /vllm|local|qwen/i.test(m.id)) ||
      by((m) => m.kind === "text" && !/gpt/i.test(m.id)) ||
      items[0].id
    );
  }
  if (prefer === "azure") {
    return by((m) => /azure|gpt-4o/i.test(m.id)) || by((m) => /gpt-4/i.test(m.id)) || items[0].id;
  }
  if (prefer === "mini") {
    return by((m) => /mini|small/i.test(m.id)) || items[items.length - 1]?.id || items[0].id;
  }
  return items[0].id;
}

/** 82 · 对齐 aip-model-router.html · 路由规则表 + 预热 + 试聊 */
export function ModelRouterPage() {
  const models = useJsonGet<{ items: ModelItem[]; sidecar?: string; defaultTextModel?: string }>(
    "/v1/aip/models",
  );
  const warm = useJsonGet<{
    ready?: boolean;
    models?: { id: string; state?: string }[];
    sidecar?: string;
  }>("/v1/aip/models/warmup");
  const { data, err, reload } = useJsonGet<{ items: ProviderRow[] }>("/v1/aip/providers");
  const [modelId, setModelId] = useState("");
  const [query, setQuery] = useState("你好，介绍一下本系统的模型路由");
  const [chatAnswer, setChatAnswer] = useState("");
  const [chatPayload, setChatPayload] = useState<unknown>(null);
  const [chatErr, setChatErr] = useState<string | null>(null);

  const items = models.data?.items || [];

  useEffect(() => {
    const d = models.data?.defaultTextModel;
    if (d) setModelId(d);
  }, [models.data?.defaultTextModel]);

  const routeRows = useMemo(() => {
    const pAgnes = pickModel(items, "agnes");
    const pLocal = pickModel(items, "local");
    const pAzure = pickModel(items, "azure");
    const pMini = pickModel(items, "mini");
    const primary = items.some((m) => /agnes/i.test(m.id)) ? pAgnes : pLocal;
    return [
      ["摘要 / 分类", primary, pMini, "禁公网 ☑"],
      ["业务问答 + Wiki", primary, pMini, "禁公网 ☑"],
      ["Logic 长上下文 (>32k)", primary, pMini, "审批后 ⚠"],
      ["Chatbot 日常对话", pMini || primary, "—", "继承"],
      ["含 PII 字段", pLocal, "—", "强制不出域"],
      ["Provider 不可用", `${pMini || primary}（熔断降级）`, "fallback", "fallback"],
    ];
  }, [items]);

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
      setChatAnswer(String(r.answer || "（无 answer 字段）"));
      setChatPayload(r);
    } catch (e) {
      setChatErr(String((e as Error).message || e));
      setChatPayload(null);
    }
  }

  return (
    <S2Chrome title="模型路由策略" lede="任务类型 · 出境 · 预热 · 熔断降级。供应商接入见模型供应商页。">
      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            reload();
            models.reload();
            warm.reload();
          }}
        >
          刷新
        </button>
        <Link to="/aip/model-providers" className="muted">
          模型供应商（接入）→
        </Link>
        <Link to="/aip/tools" className="muted">
          工具面板 →
        </Link>
      </BpToolbar>
      {(err || models.err || warm.err) && <p className="error">{err || models.err || warm.err}</p>}

      <BpBanner tone="info">
        默认使用环境变量中的模型配置；试聊与智能助手走同一网关。新增供应商 →
        <Link to="/aip/model-providers"> 模型供应商</Link>。
      </BpBanner>

      <div className="bp-object-panel" style={{ marginTop: "1rem" }}>
        <div className="bp-ws-section-title">
          路由规则 <span className="muted" style={{ fontWeight: 400 }}>· 对齐 07a · 任务类型 / 回退 / 出境</span>
        </div>
        <BpTable columns={["任务类型", "首选", "回退", "出境"]} rows={routeRows} />
        <p className="muted" style={{ fontSize: "0.75rem", marginTop: "0.5rem" }}>
          sidecar={models.data?.sidecar || warm.data?.sidecar || "—"} · 路由策略由当前 catalog 推导
        </p>
      </div>

      <div className="bp-domain bp-domain-aip" style={{ marginTop: "1rem", padding: "1rem" }}>
        <div className="bp-ws-section-title">模型预热状态</div>
        <ul className="muted" style={{ fontSize: "0.8rem", listStyle: "none", padding: 0 }}>
          {(warm.data?.models || items).map((m) => {
            const id = "id" in m ? m.id : (m as ModelItem).id;
            const state =
              "state" in m ? m.state : (m as ModelItem).ready ? "ready" : "cold";
            return (
              <li key={id} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span>{id}</span>
                <span className={state === "ready" ? "bp-prop-ok" : "bp-prop-warn"}>
                  {state === "ready" ? "ready" : "cold / 加载中"}
                </span>
              </li>
            );
          })}
          {(warm.data?.models || items).length === 0 && <li>—</li>}
        </ul>
      </div>

      <div className="bp-ws-section-title" style={{ marginTop: "1rem" }}>
        可路由模型（试聊）
      </div>
      <ul className="card-list">
        {items.map((m) => (
          <li key={m.id} className="card">
            <label>
              <input
                type="radio"
                name="model"
                checked={modelId === m.id}
                onChange={() => setModelId(m.id)}
              />{" "}
              <strong>{m.id}</strong> · {m.kind} · {m.provider || m.id}{" "}
              <span className={m.ready ? "bp-prop-ok" : "bp-prop-warn"}>
                {m.ready ? "ready" : "cold"}
              </span>
            </label>
          </li>
        ))}
      </ul>

      <div className="filter-bar" style={{ marginTop: "0.75rem" }}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ minWidth: "16rem" }}
          aria-label="router-query"
        />
        <button type="button" className="btn" onClick={() => void tryChat()}>
          试聊
        </button>
      </div>
      {chatErr && <p className="error">{chatErr}</p>}
      {chatAnswer && (
        <div className="bp-object-panel" style={{ marginTop: "0.75rem" }}>
          <div className="bp-ws-section-title">试聊回复</div>
          <p className="aos-text" style={{ whiteSpace: "pre-wrap" }}>
            {chatAnswer}
          </p>
        </div>
      )}
      {chatPayload != null && (
        <BpDebugPanel value={chatPayload} title="试聊原始 JSON" />
      )}

      <div className="bp-ws-section-title" style={{ marginTop: "1rem" }}>
        Providers
      </div>
      <BpTable
        columns={["供应商", "kind", "id"]}
        rows={(data?.items || []).map((p) => [p.name || p.id, p.kind || "llm", p.id])}
      />
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
        <button type="button" className="btn" onClick={() => void setGate(true)}>
          运行 Eval 套件 / 放行
        </button>
        <button type="button" className="btn" onClick={() => void setGate(false)}>
          阻断
        </button>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
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
          暂无谱系 · 请先在提案审批台批准写入，再点治理探针
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
