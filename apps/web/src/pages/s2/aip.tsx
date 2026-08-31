import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
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
import { AipOperationalProjectionStrip } from "../../components/aip/AipOperationalProjectionStrip";
import type { ModelRuntimeOverview } from "../../api/aipModelRuntime";
import { MODEL_CONFIG_NO_VAULT } from "../../lib/productCopy";
import {
  aipEvidenceSdk,
  LINEAGE_ROOT_TYPES,
  type AuthorityEvidenceChain,
  type LineageRootType,
  type EvalRunAuthority,
} from "../../api/aipEvidence";
import { aipActionsSdk, type ActionDraftBundle } from "../../api/aipActions";
import { listAssistSubjects, type AssistSubjectOption } from "../../api/aipWorkbench";
import {
  decodeToolsPanelOverlay,
  encodeToolsPanelOverlay,
  type ToolsPanelHitl,
} from "./toolsPanelOverlay";
import {
  buildToolsInvokePayload,
  parseToolsInvokeContext,
  toolsInvokeBlocker,
  validateExactObjectQueryResult,
} from "./toolsInvokeContext";
import {
  businessDisplayName,
  actionDisplayName,
  formatBlockers,
  runtimeModeDisplayName,
  statusDisplayName,
  toolDisplayName,
  toolKindDisplayName,
} from "../../lib/aipChineseLabels";

const TOOL_CATS = [
  { id: "action", label: "写回动作", zh: "须人工确认", defaultOn: true },
  { id: "query", label: "对象查询", zh: "属性子集查询", defaultOn: true },
  { id: "function", label: "业务逻辑", zh: "已发布流程", defaultOn: true },
  { id: "var", label: "应用变量", zh: "更新应用变量", defaultOn: false },
  { id: "cmd", label: "命令", zh: "命令类工具", defaultOn: false },
  { id: "clarify", label: "澄清", zh: "向用户澄清", defaultOn: true },
  { id: "capability", label: "专业能力", zh: "平台代调重能力", defaultOn: true },
  { id: "wiki", label: "Wiki 字段", zh: "结构化 Wiki", defaultOn: true, wiki: true },
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
  if (cat === "action") return "人工确认后执行";
  if (cat === "query") return "属性子集 · 含 Wiki 字段";
  if (cat === "function") return "已发布的业务逻辑";
  if (cat === "clarify") return "暂停 · 向用户要澄清";
  if (cat === "capability") return "写回经受控业务动作 · 由平台代为调用";
  if (cat === "wiki") return "结构化字段优先";
  return "只读 / 可提案";
}

function toolBusinessGroup(kind: string): string {
  const cat = toolCategory(kind);
  if (cat === "query" || cat === "wiki") return "经营事实读取";
  if (cat === "function") return "业务规则与分析";
  if (cat === "action") return "受控业务写回";
  if (cat === "capability") return "内容与媒体生产";
  return "任务协作";
}

function toolRiskLabel(kind: string): string {
  const cat = toolCategory(kind);
  if (cat === "action") return "写操作 · 必须审批";
  if (cat === "capability") return "外部能力 · 沙箱门控";
  return "只读 / 沙箱安全";
}

function toolIoLabel(kind: string): string {
  const cat = toolCategory(kind);
  if (cat === "query") return "对象标识 → 授权业务属性";
  if (cat === "wiki") return "业务对象 → 结构化知识字段";
  if (cat === "function") return "业务输入 → 规则计算结果";
  if (cat === "action") return "变更意图 → 提案与待审草稿";
  if (cat === "capability") return "生产需求 → 受控能力产物";
  return "任务上下文 → 澄清结果";
}

/** 智能体工具配置：三栏目录、实例配置和受控试跑。 */
export function ToolsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { data, err, reload } = useJsonGet<{
    items: {
      id: string;
      kind: string;
      name?: string;
      nameZh?: string;
      blocked?: boolean;
      blockedReason?: string;
      capabilityId?: string;
      publishedVersion?: number;
    }[];
  }>("/v1/aip/tools");
  const agents = useJsonGet<{
    items?: Array<{
      instanceId?: string;
      id?: string;
      name?: string;
      status?: string;
      overlay?: { displayName?: string };
    }>;
  }>("/v1/aip/agents");
  const defaultCats = useMemo(
    () => TOOL_CATS.filter((c) => c.defaultOn).map((c) => c.id),
    [],
  );
  const [cats, setCats] = useState<Set<string>>(() => new Set(defaultCats));
  const [selectedId, setSelectedId] = useState<string | null>(() => String(searchParams.get("tool") || "").trim() || null);
  const [hitl, setHitl] = useState<ToolsPanelHitl>("form");
  const [invokeSummary, setInvokeSummary] = useState("");
  const [invokePayload, setInvokePayload] = useState<unknown>(null);
  const [localErr, setLocalErr] = useState<string | null>(null);
  const [mode, setMode] = useState("native");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [saving, setSaving] = useState(false);
  const [overlayLoading, setOverlayLoading] = useState(false);
  const [activeInstanceId, setActiveInstanceId] = useState<string>("");
  const [overlayToolItems, setOverlayToolItems] = useState<
    Array<{ id: string; name: string; category: string; enabled: boolean }>
  >([]);
  const [packVersion, setPackVersion] = useState<string | null>(null);
  const [draftObjectType, setDraftObjectType] = useState("");
  const [draftObjectId, setDraftObjectId] = useState("");

  const urlInvokeCtx = useMemo(() => parseToolsInvokeContext(searchParams), [searchParams]);
  const invokeBlocker = toolsInvokeBlocker(urlInvokeCtx, {
    draftObjectType,
    draftObjectId,
  });

  const agentItems = useMemo(() => {
    return (agents.data?.items || [])
      .map((item) => {
        const id = String(item.instanceId || item.id || "").trim();
        if (!id) return null;
        return {
          id,
          label: item.overlay?.displayName || item.name || id,
          status: item.status || "",
        };
      })
      .filter((x): x is { id: string; label: string; status: string } => Boolean(x));
  }, [agents.data]);

  useEffect(() => {
    if (!agentItems.length) {
      setActiveInstanceId("");
      return;
    }
    const fromUrl = String(searchParams.get("instance") || "").trim();
    const preferred =
      (fromUrl && agentItems.find((a) => a.id === fromUrl)?.id) ||
      agentItems.find((a) => a.id.includes("content_officer"))?.id ||
      agentItems[0].id;
    setActiveInstanceId((prev) => (prev && agentItems.some((a) => a.id === prev) ? prev : preferred));
  }, [agentItems, searchParams]);

  useEffect(() => {
    if (!activeInstanceId) return;
    let cancelled = false;
    setOverlayLoading(true);
    setLocalErr(null);
    setSaveMsg("");
    apiGet<{ agent_id?: string; items?: Array<{ id: string; name?: string; category?: string; enabled?: boolean }> }>(
      `/v1/aip/agents/${encodeURIComponent(activeInstanceId)}/tools`,
    )
      .then((r) => {
        if (cancelled) return;
        if (r.agent_id && r.agent_id !== activeInstanceId) {
          throw new Error("Overlay 响应实例错配");
        }
        const decoded = decodeToolsPanelOverlay(r.items as never, {
          defaultCategories: defaultCats,
        });
        setCats(decoded.categories);
        setMode(decoded.mode);
        setHitl(decoded.hitl);
        setOverlayToolItems(decoded.toolItems);
        const pack = (r.items || []).find((i) => String(i.id) === "panel.cfg.pack");
        setPackVersion(pack ? String(pack.name || "") : null);
      })
      .catch((e) => {
        if (cancelled) return;
        setLocalErr(`Overlay 加载失败：${String((e as Error).message || e)}`);
        setCats(new Set(defaultCats));
        setMode("native");
        setHitl("form");
        setOverlayToolItems([]);
        setPackVersion(null);
      })
      .finally(() => {
        if (!cancelled) setOverlayLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeInstanceId, defaultCats]);

  const tools = useMemo(() => {
    type ToolRow = {
      id: string;
      kind: string;
      name?: string;
      nameZh?: string;
      blocked?: boolean;
      blockedReason?: string;
      capabilityId?: string;
      publishedVersion?: number;
    };
    const catalog = (data?.items || []).filter((t) => cats.has(toolCategory(t.kind)));
    const byId = new Map<string, ToolRow>(
      catalog.map((t) => [
        t.id,
        {
          id: t.id,
          kind: t.kind,
          name: t.name,
          nameZh: t.nameZh,
          blocked: t.blocked,
          blockedReason: t.blockedReason,
          capabilityId: t.capabilityId,
          publishedVersion: (t as { publishedVersion?: number }).publishedVersion,
        },
      ]),
    );
    for (const item of overlayToolItems) {
      if (item.category && !cats.has(item.category)) continue;
      if (!byId.has(item.id)) {
        byId.set(item.id, {
          id: item.id,
          kind: item.category || "tool",
          name: item.name,
        });
      }
    }
    return Array.from(byId.values());
  }, [data, cats, overlayToolItems]);

  const selected = tools.find((t) => t.id === selectedId) || tools[0] || null;
  const selectedCat = selected ? toolCategory(selected.kind) : null;
  const currentAgent = agentItems.find((a) => a.id === activeInstanceId) || null;

  function toolsLink(path: string, toolId = selected?.id || "") {
    const next = new URLSearchParams();
    if (activeInstanceId) next.set("instance", activeInstanceId);
    if (toolId) next.set("tool", toolId);
    const objectType = urlInvokeCtx?.objectType || draftObjectType;
    const objectId = urlInvokeCtx?.objectId || draftObjectId;
    if (objectType) next.set("objectType", objectType);
    if (objectId) next.set("objectId", objectId);
    const query = next.toString();
    return query ? `${path}?${query}` : path;
  }

  function selectInstance(id: string) {
    setActiveInstanceId(id);
    const next = new URLSearchParams(searchParams);
    if (id) next.set("instance", id);
    else next.delete("instance");
    setSearchParams(next, { replace: true });
  }

  function toggleCat(id: string) {
    setCats((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  }

  async function saveToolsConfig() {
    if (!activeInstanceId) {
      setLocalErr("请先选择数字同事实例；工具配置按当前实例单独保存，不再写入全局配置");
      return;
    }
    setSaving(true);
    setSaveMsg("");
    setLocalErr(null);
    try {
      const enabledTools = tools.map((t) => ({
        id: t.id,
        name: t.name || t.id,
        category: toolCategory(t.kind),
      }));
      const items = encodeToolsPanelOverlay({ tools: enabledTools, mode, hitl });
      if (packVersion) {
        items.push({
          id: "panel.cfg.pack",
          name: packVersion,
          category: "panel",
          enabled: true,
        });
      }
      const written = await apiPut<{ agent_id?: string; items?: unknown[] }>(
        `/v1/aip/agents/${encodeURIComponent(activeInstanceId)}/tools`,
        { items },
      );
      if (written.agent_id && written.agent_id !== activeInstanceId) {
        throw new Error("实例配置写回目标不一致");
      }
      const reread = await apiGet<{ agent_id?: string; items?: unknown[] }>(
        `/v1/aip/agents/${encodeURIComponent(activeInstanceId)}/tools`,
      );
      if (reread.agent_id && reread.agent_id !== activeInstanceId) {
        throw new Error("实例配置回读目标不一致");
      }
      setSaveMsg(`已保存到当前数字同事实例 · ${currentAgent?.label || "已选实例"}`);
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
    const payload = buildToolsInvokePayload(urlInvokeCtx, {
      draftObjectType,
      draftObjectId,
    });
    if (!payload) {
      setLocalErr(invokeBlocker || "缺少精确的试跑业务上下文");
      return;
    }
    try {
      const r = await apiPost<Record<string, unknown>>(
        `/v1/aip/tools/${encodeURIComponent(id)}/invoke`,
        payload,
      );
      setInvokePayload(r);
      if (r.requiresDraft === true) {
        const proposal = r.proposal as { actionTypeId?: string; objectType?: string; objectId?: string; status?: string } | undefined;
        setInvokeSummary(
          `写回提案已形成 · ${proposal?.actionTypeId || id} · ${proposal?.objectType || payload.objectType}/${proposal?.objectId || payload.objectId} · 下一步进入草稿审批`,
        );
      } else if (r.ok === false || r.blocked === true) {
        const msg =
          typeof (r.result as { message?: string } | undefined)?.message === "string"
            ? String((r.result as { message?: string }).message)
            : "工具门禁拒绝直接成功";
        setInvokeSummary(`诚实失败 · ${id} · ${msg}`);
        setLocalErr(msg);
      } else {
        if (id === "query.objects") {
          const exactError = validateExactObjectQueryResult(r, payload.objectId);
          if (exactError) {
            setInvokeSummary(`诚实失败 · ${id} · ${exactError}`);
            setLocalErr(exactError);
            return;
          }
        }
        setInvokeSummary(`试跑完成 · ${id} · ${payload.objectType}/${payload.objectId}`);
      }
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
    }
  }

  function InvokeButton({ toolId }: { toolId: string }) {
    return (
      <button
        type="button"
        className="btn-outline-cyan"
        disabled={Boolean(invokeBlocker)}
        title={invokeBlocker || undefined}
        onClick={() => void invoke(toolId)}
      >
        试跑
      </button>
    );
  }

  function renderDetail() {
    if (!selected || !selectedCat) {
      return <p className="muted">选择已启用工具查看细项</p>;
    }

    if (selectedCat === "action") {
      return (
        <>
          <h2 className="bp-tool-detail-title">受控写回动作</h2>
          <p className="bp-tool-detail-meta">经人工确认和草稿审批后写回业务系统。</p>
          <details><summary>技术标识（审计用）</summary><code>{selected.id}</code>{selected.name ? ` · ${selected.name}` : ""}</details>
          <p className="error" data-testid="tools-action-draft-gate" style={{ fontSize: "0.8rem" }}>
            {selected.blockedReason ||
              "写回必须经过人工确认、草稿审批和交付凭证；本面板不能直接写入生产数据。"}
          </p>
          <fieldset className="bp-tool-strategy">
            <legend>执行策略（不绕过草稿审批）</legend>
            <label>
              <input
                type="radio"
                name="hitl"
                checked={hitl === "auto"}
                onChange={() => setHitl("auto")}
              />
              对话中自动提交草稿（仍须审批）
            </label>
            <label>
              <input
                type="radio"
                name="hitl"
                checked={hitl === "form"}
                onChange={() => setHitl("form")}
              />
              弹出写回表单供人确认
            </label>
            <label>
              <input
                type="radio"
                name="hitl"
                checked={hitl === "draft"}
                onChange={() => setHitl("draft")}
              />
              仅生成草稿（不写生产）
            </label>
          </fieldset>
          <div className="mp-cfg-actions" style={{ marginTop: "0.75rem" }}>
            <InvokeButton toolId={selected.id} />
            <Link to={toolsLink("/aip/drafts")} className="btn-nav" data-testid="tools-action-drafts-link">
              进入草稿审批 →
            </Link>
          </div>
          <ol className="aos-text" style={{ fontSize: "0.72rem", paddingLeft: 18 }}>
            <li>工具试跑形成精确写回提案，不修改生产对象</li>
            <li>草稿审批台补充变更字段并提交职责分离审批</li>
            <li>批准后才允许执行，并以交付凭证确认结果</li>
          </ol>
        </>
      );
    }

    if (selectedCat === "query") {
      return (
        <>
          <h2 className="bp-tool-detail-title">业务对象查询</h2>
          <p className="bp-tool-detail-meta">只读取当前组织和工作区授权的业务属性。</p>
          <div className="bp-tool-chips">
            <span className="bp-tool-chip">☑ 对象标识</span>
            <span className="bp-tool-chip">☑ 业务状态</span>
            <span className="bp-tool-chip is-wiki">☑ 知识风险等级</span>
            <span className="bp-tool-chip">☐ 原始载荷</span>
          </div>
          <details><summary>技术标识（审计用）</summary><code>{selected.id}</code></details>
          <Link to="/ontology/wiki" className="btn-nav">
            打开知识库 →
          </Link>
        </>
      );
    }

    if (selectedCat === "function") {
      const blocked = Boolean(selected.blocked);
      return (
        <>
          <h2 className="bp-tool-detail-title">{toolDisplayName(selected)}</h2>
          <p className="bp-tool-detail-meta">已发布的业务逻辑工具；试跑仍受当前对象、权限和运行就绪门控制。</p>
          <details><summary>技术标识（审计用）</summary><code>{selected.id}</code>{selected.publishedVersion != null ? ` · 发布版本 ${selected.publishedVersion}` : ""}</details>
          {blocked ? (
            <p className="error" data-testid="tools-function-blocked" style={{ fontSize: "0.8rem" }}>
              {selected.blockedReason || "尚未绑定已发布的业务逻辑，当前不可使用。"}
            </p>
          ) : (
            <p className="muted" style={{ fontSize: "0.75rem" }}>
              已绑定发布版本，可继续进行受控试跑。
            </p>
          )}
          <div className="mp-cfg-actions">
            <Link to={toolsLink("/aip/logic")} className="btn-nav-accent">
              打开业务逻辑编排 →
            </Link>
            <InvokeButton toolId={selected.id} />
          </div>
        </>
      );
    }

    if (selectedCat === "clarify") {
      return (
        <>
          <h2 className="bp-tool-detail-title">信息补充确认</h2>
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
          <h2 className="bp-tool-detail-title">知识字段读取</h2>
          <p className="muted" style={{ fontSize: "0.8rem", color: "#fdba74" }}>
            结构化字段优先 · Agent 不扫全文向量库
          </p>
          <div className="bp-tool-chips">
            <span className="bp-tool-chip is-wiki">知识风险等级</span>
            <span className="bp-tool-chip is-wiki">商品规格知识</span>
          </div>
          <Link to="/ontology/wiki" className="btn-nav">
            打开知识库 →
          </Link>
        </>
      );
    }

    if (selectedCat === "capability") {
      const blocked = Boolean(selected.blocked);
      return (
        <>
          <h2 className="bp-tool-detail-title">{toolDisplayName(selected)}</h2>
          <p className="bp-tool-detail-meta">由平台代为调用的专业能力；结果回写仍须经过受控动作。</p>
          <details><summary>技术标识（审计用）</summary><code>{selected.capabilityId || selected.id}</code></details>
          {blocked ? (
            <p className="error" data-testid="tools-capability-blocked" style={{ fontSize: "0.8rem" }}>
              {selected.blockedReason || "专业能力暂不可代调"}
            </p>
          ) : (
            <p className="muted" style={{ fontSize: "0.75rem" }}>
              LLM 只请求；平台代调。产物进媒体集；状态写回须经 Action。
            </p>
          )}
          <div className="mp-cfg-actions">
            <Link to="/aip/capabilities" className="btn-nav">
              打开重能力接入 →
            </Link>
            <InvokeButton toolId={selected.id} />
          </div>
        </>
      );
    }

    return (
      <>
        <h2 className="bp-tool-detail-title">{toolDisplayName(selected)}</h2>
        <p className="bp-tool-detail-meta">{toolKindDisplayName(selected.kind)}</p>
        <details><summary>技术标识（审计用）</summary><code>{selected.id}</code></details>
        <InvokeButton toolId={selected.id} />
      </>
    );
  }

  return (
    <S2Chrome
      title="智能体工具配置"
      lede="为每个数字同事配置可使用的查询、业务逻辑和专业能力；平台按当前组织权限代为调用。"
    >
      <AipOperationalProjectionStrip />
      <div
        data-testid="tools-ops-stats"
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, margin: "0 0 12px" }}
      >
        {[
          { label: "工具总数", value: String((data?.items || []).length) },
          { label: "筛选命中", value: String(tools.length) },
          { label: "分类开", value: String(cats.size) },
          { label: "调用方式", value: runtimeModeDisplayName(mode) },
          { label: "人工确认", value: runtimeModeDisplayName(hitl) },
          { label: "同事", value: currentAgent ? "已绑" : "未绑" },
          { label: "默认工具包", value: packVersion ? businessDisplayName(packVersion, "当前智能体工具包") : "—" },
        ].map((s) => (
          <div key={s.label} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{s.value}</div>
          </div>
        ))}
      </div>
      <div data-testid="tools-overlay-authority">
        <BpBanner tone="info">
          配置来源：当前数字同事实例（与智能体配置页使用同一份数据）· 当前{" "}
          {currentAgent?.label || "未选择数字同事"}
          {overlayLoading ? " · 加载中…" : ""}
        </BpBanner>
      </div>
      <div data-testid="tools-invoke-context" className="card" style={{ padding: 12, marginBottom: 12 }}>
        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>受控试跑对象</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
          <label className="muted" style={{ fontSize: "0.65rem" }}>
            业务对象类型
            <input
              aria-label="tools-object-type"
              value={urlInvokeCtx?.objectType || draftObjectType}
              onChange={(e) => setDraftObjectType(e.target.value)}
              disabled={Boolean(urlInvokeCtx)}
              placeholder="如订单、商品或工单"
              style={{ marginLeft: 6, minWidth: 120 }}
            />
          </label>
          <label className="muted" style={{ fontSize: "0.65rem" }}>
            真实对象标识
            <input
              aria-label="tools-object-id"
              value={urlInvokeCtx?.objectId || draftObjectId}
              onChange={(e) => setDraftObjectId(e.target.value)}
              disabled={Boolean(urlInvokeCtx)}
              placeholder="请输入真实业务对象标识"
              style={{ marginLeft: 6, minWidth: 160 }}
            />
          </label>
          <button
            type="button"
            className="btn-outline-cyan"
            data-testid="tools-invoke"
            disabled={Boolean(invokeBlocker) || !selected}
            title={invokeBlocker || (!selected ? "请先选择工具" : undefined)}
            onClick={() => selected && void invoke(selected.id)}
          >
            试跑当前工具
          </button>
          <Link to="/aip/assist" className="btn-nav" style={{ fontSize: "0.7rem" }}>
            从智能助手带入任务上下文 →
          </Link>
        </div>
        {invokeBlocker ? (
          <p className="error" data-testid="tools-invoke-blocker" style={{ marginTop: 8, fontSize: "0.75rem" }}>
            {invokeBlocker}
          </p>
        ) : (
          <p className="muted" style={{ marginTop: 8, fontSize: "0.7rem" }}>
            已绑定 {(urlInvokeCtx?.objectType || draftObjectType)}/{(urlInvokeCtx?.objectId || draftObjectId)}
          </p>
        )}
      </div>
      <BpToolbar>
        <label className="muted" style={{ fontSize: "0.65rem", display: "inline-flex", alignItems: "center", gap: 8 }}>
          数字同事实例
          <select
            className="bp-tool-select"
            data-testid="tools-instance-select"
            value={activeInstanceId}
            onChange={(e) => selectInstance(e.target.value)}
            aria-label="tools-instance"
            disabled={!agentItems.length}
          >
            {!agentItems.length ? <option value="">无可用实例</option> : null}
            {agentItems.map((a) => (
              <option key={a.id} value={a.id}>
                {a.label}
              </option>
            ))}
          </select>
        </label>
        <label className="muted" style={{ fontSize: "0.65rem", display: "inline-flex", alignItems: "center", gap: 8 }}>
          调用模式
          <select
            className="bp-tool-select"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            aria-label="tool-mode"
          >
            <option value="native">并行调用</option>
            <option value="prompted">逐项调用</option>
          </select>
        </label>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <Link to="/aip/capabilities" className="btn-nav">
          重能力 →
        </Link>
        <Link to={toolsLink("/aip/maturity")} className="btn-nav">
          ← 成熟度
        </Link>
        <Link to={toolsLink("/aip/logic")} className="btn-nav-accent">
          业务逻辑编排 →
        </Link>
        <Link
          to={activeInstanceId ? `/aip/studio?instance=${encodeURIComponent(activeInstanceId)}` : "/aip/studio"}
          className="btn-nav"
          data-testid="tools-to-studio-link"
        >
          智能体配置 →
        </Link>
      </BpToolbar>
      {(err || localErr || agents.err) && <p className="error">{err || localErr || agents.err}</p>}

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
              <span className="bp-tag bp-tag-ok">{statusDisplayName(currentAgent.status || "unknown")}</span>
              <span className="bp-tag bp-tag-warn">需要人工确认</span>
            </>
          ) : (
            <Link to="/aip/studio" className="bp-tag bp-tag-warn">前往智能体配置</Link>
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
                  aria-label={`${c.label}（${c.zh}）`}
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
                  aria-label={`${c.label}（${c.zh}）`}
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
              优先使用结构化知识字段和授权属性子集
            </p>
            <Link to="/aip/capabilities" className="bp-tool-cat is-capability-entry">
              <span className="bp-tool-cat-text">
                <span className="bp-tool-cat-label">登记专业能力 →</span>
                <span className="bp-tool-cat-zh">平台代调 · 写回须人工确认</span>
              </span>
            </Link>
          </>
        }
        enabled={
          <>
            <div className="bp-section-micro">已启用</div>
            {tools.map((t) => {
              const cat = toolCategory(t.kind);
              const active = selected?.id === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  className={`bp-tool-item${active ? " is-active" : ""}${cat === "capability" ? " is-capability" : ""}`}
                  onClick={() => {
                    setSelectedId(t.id);
                    const next = new URLSearchParams(searchParams);
                    next.set("tool", t.id);
                    if (activeInstanceId) next.set("instance", activeInstanceId);
                    setSearchParams(next, { replace: true });
                    setInvokeSummary("");
                    setInvokePayload(null);
                    setAdvancedOpen(false);
                  }}
                >
                  <div style={{ fontWeight: 500, color: "var(--aos-text)", fontSize: "0.875rem" }}>
                    {toolDisplayName(t)}
                  </div>
                  <div
                    className="muted"
                    style={{
                      fontSize: "0.65rem",
                      marginTop: 4,
                      color: cat === "action" && active ? "#fde68a" : undefined,
                    }}
                  >
                    {toolSubtitle(t.kind)} · {toolBusinessGroup(t.kind)} · {toolRiskLabel(t.kind)}
                  </div>
                </button>
              );
            })}
            {tools.length === 0 && <p className="muted">无匹配工具 · 调整目录勾选</p>}
          </>
        }
        detail={
          <>
            <div className="bp-quality-score" data-testid="tools-quality-unscored">
              <div className="bp-quality-score-header">
                <div className="bp-quality-score-title">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                  </svg>
                  <span>质量评分</span>
                </div>
                <div className="bp-quality-score-value">
                  <span className="bp-quality-score-num" style={{ fontSize: "1rem" }}>未评分</span>
                </div>
              </div>
              <div className="bp-quality-score-tip">
                尚未绑定权威评测套件和真实用例，因此不显示推测分数。请到{" "}
                <Link to="/aip/evals">评测门控</Link> 完成绑定后查看结果。
              </div>
            </div>
            {renderDetail()}
            {selected && (
              <div className="card" data-testid="tools-business-contract" style={{ padding: 10, marginTop: 10, fontSize: "0.72rem" }}>
                <strong>业务能力合同</strong>
                <div style={{ marginTop: 6 }}>能力域：{toolBusinessGroup(selected.kind)}</div>
                <div>风险：{toolRiskLabel(selected.kind)}</div>
                <div>输入输出：{toolIoLabel(selected.kind)}</div>
                <div>适用数字同事：{currentAgent?.label || "请选择数字同事实例"}</div>
              </div>
            )}
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
          支持受控写回、业务逻辑、专业能力和对象查询。可前往{" "}
          <Link to="/aip/studio">智能体配置</Link> 进行试聊。
        </span>
        <button
          type="button"
          className="btn-nav-accent"
          data-testid="tools-save-overlay"
          disabled={saving || !activeInstanceId || overlayLoading}
          onClick={() => void saveToolsConfig()}
        >
          {saving ? "保存中…" : "保存当前实例配置"}
        </button>
      </div>
      {saveMsg && (
        <p className="bp-prop-ok" data-testid="tools-save-msg" style={{ fontSize: "0.7rem", marginTop: 6 }}>
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
  config?: {
    displayName?: string;
    baseUrl?: string;
    secretRef?: string;
    models?: string[];
    revision?: number;
  };
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

function canonicalRuntimeProjection(data: ModelRuntimeOverview | null, error: string | null) {
  const resolutions = data?.resolutions ?? [];
  const total = resolutions.length;
  const ready = resolutions.filter((item) => item.readiness === "ready").length;
  const blockers = Array.from(
    new Set(resolutions.flatMap((item) => item.blockerCodes ?? [])),
  );
  return {
    total,
    ready,
    blockers,
    isReady: !error && total > 0 && ready === total,
  };
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
  const runtimeApi = useJsonGet<ModelRuntimeOverview>("/v1/aip/model-runtime/overview");
  const runtimeProjection = canonicalRuntimeProjection(runtimeApi.data, runtimeApi.err);
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
  const credentialPlugin = activePluginId
    ? pluginItems.find((p) => p.id === activePluginId) || null
    : selectedId
      ? pluginItems.find(
          (p) =>
            p.installed &&
            [...(p.enabledModels || []), ...(p.defaultModels || [])].includes(selectedId),
        ) || null
      : null;
  const boundLabel = keyUpdatedAt
    ? `已更新 · ${new Date(keyUpdatedAt).toLocaleString()}`
    : secretBoundLabel(secretRef || credentialPlugin?.config?.secretRef || selected?.apiKeyRef || apiVaultRef);
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
      if (!runtimeProjection.isReady) {
        setMsg("权威模型运行链尚未全部就绪，禁止切换兼容默认网关");
        return;
      }
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
      ? plugin.config?.secretRef || `vault:secret/data/aos/llm#${plugin.id}`
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

  async function persistCredentialRef(nextRef: string, action: "保存" | "轮换" | "撤销") {
    setSaveMsg("");
    setMsg("");
    const stamped = keyUpdatedAt || new Date().toISOString();
    setKeyUpdatedAt(stamped);
    const ref = nextRef.trim();

    const targetPlugin = credentialPlugin;
    if (targetPlugin) {
      try {
        const saved = await apiPut<{ config?: LlmPlugin["config"] }>(
          `/v1/aip/llm-provider-plugins/${encodeURIComponent(targetPlugin.id)}/config`, {
          displayName: targetPlugin.config?.displayName || displayName,
          baseUrl: targetPlugin.config?.baseUrl || (formKind === "vllm" ? localUrl : baseUrl),
          secretRef: ref,
          models: targetPlugin.config?.models || targetPlugin.enabledModels || targetPlugin.defaultModels || [],
          ready: action === "撤销" ? false : Boolean(targetPlugin.ready),
          expectedVersion: targetPlugin.config?.revision || 0,
        });
        const reread = await apiGet<{ items: LlmPlugin[] }>("/v1/aip/llm-provider-plugins");
        const confirmed = reread.items.find((item) => item.id === targetPlugin.id);
        if (
          confirmed?.config?.secretRef !== ref ||
          confirmed.config.revision !== saved.config?.revision
        ) {
          throw new Error("凭据引用写入后重读不一致");
        }
        setSecretRef(ref);
        setKeyUpdatedAt(new Date().toISOString());
        pluginsApi.setData(reread);
        setSaveMsg(`opaque 凭据引用已${action}并重读确认 · v${confirmed.config.revision} · 未触发模型调用${action === "撤销" ? " · Provider 已取消就绪" : ""}`);
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
    setSaveMsg(`当前供应商未匹配到已安装插件，凭据引用${action}仅保留为会话草稿`);
  }

  async function saveCredentials() {
    const ref = secretRef.trim() || (activePluginId ? `vault:secret/data/aos/llm#${activePluginId}` : apiVaultRef);
    await persistCredentialRef(ref, "保存");
  }

  async function rotateCredentials() {
    if (!secretRef.trim()) {
      setMsg("请先填写密钥库生成的新 opaque 引用，再执行轮换");
      return;
    }
    await persistCredentialRef(secretRef, "轮换");
  }

  async function revokeCredentials() {
    await persistCredentialRef("", "撤销");
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
        lede="在线填写供应商插件清单；发布后进入可安装目录，并按受控流程完成安装。"
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
            <span>插件标识（小写字母与连字符）</span>
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
            <span>支持内容类型（文字、图片、视频，逗号分隔）</span>
            <input value={studioMods} onChange={(e) => setStudioMods(e.target.value)} />
          </label>
          <label className="mp-field">
            <span>接口兼容类型</span>
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
            <span>默认服务地址</span>
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
        lede="仅绑定由安全后端维护的 opaque 凭据引用；本页不接收、传输或回显明文密钥。"
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
          </div>
          <p className="muted" style={{ fontSize: "0.75rem", marginTop: "0.75rem" }}>
            请先在企业密钥库、AOS 安全存储或本机钥匙串中维护密钥，再在此绑定不透明引用。已匹配安装插件时采用版本校验保存并重读；不会读取密钥正文或触发模型调用。
          </p>
          <div className="mp-cfg-actions">
            <button type="button" className="btn-primary" onClick={() => void saveCredentials()}>
              保存凭据引用
            </button>
            <button type="button" className="btn-nav" onClick={() => void rotateCredentials()}>
              轮换至新引用
            </button>
            <button type="button" className="btn-nav" onClick={() => void revokeCredentials()}>
              撤销凭据引用
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
                  <span>服务地址</span>
                  <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
                </label>
                <div className="mp-field mp-field-span">
                  <span className="muted" style={{ fontSize: "0.75rem" }}>
                    接口密钥
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
                    接口密钥
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
                    接口密钥
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
                  <span>本机兼容服务地址</span>
                  <input value={localUrl} onChange={(e) => setLocalUrl(e.target.value)} />
                </label>
                <label className="mp-field">
                  <span>模型 ID / 路径</span>
                  <input value={modelPath} onChange={(e) => setModelPath(e.target.value)} />
                </label>
                <label className="mp-field">
                  <span>图形处理器设备</span>
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
                <div className="mp-adapter-title">模型适配器</div>
                <label className="mp-field mp-field-span">
                  <span>显示名</span>
                  <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
                </label>
                <label className="mp-field mp-field-span">
                  <span>执行产物来源（容器或数据接口）</span>
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
                  { label: "服务地址", value: baseUrl || apiEndpoint || "—" },
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
      title="模型供应商"
      lede="每种供应商对应一个插件：先安装，再填类型化配置；运行时经平台网关，不直连厂商。"
    >
      <BpArchitectureBar activeLayer="L1" />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, margin: "10px 0 12px" }}>
        {[
          ["权威供应商", runtimeApi.data?.providers?.length ?? "—"],
          ["权威路由", `${runtimeProjection.ready}/${runtimeProjection.total}`],
          ["已安装插件", installedPlugins.length],
          ["目录待装", catalogPlugins.length],
        ].map(([name, count]) => (
          <div key={String(name)} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{name}</div>
            <div style={{ fontSize: 22, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{count}</div>
          </div>
        ))}
      </div>
      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            reload();
            pluginsApi.reload();
            gatewayApi.reload();
            runtimeApi.reload();
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
          适配器管理
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
      <BpBanner tone={runtimeProjection.isReady ? "info" : "warn"}>
        <strong>权威模型运行状态：</strong>{" "}
        {runtimeApi.err
          ? `读取失败（${runtimeApi.err}），兼容网关只读。`
          : `${runtimeProjection.ready}/${runtimeProjection.total} 条路由已就绪。`}
        {!runtimeProjection.isReady && (
          <>
            {runtimeProjection.blockers.length
              ? ` 阻断：${formatBlockers(runtimeProjection.blockers)}。`
              : " 当前没有可核验的就绪解析结果。"}
            {" "}下方旧网关与插件状态仅作兼容诊断，不代表供应商当前可运行。
          </>
        )}
      </BpBanner>

      <section className="mp-section">
        <div className="mp-section-head">
          <h2 className="mp-section-title">兼容默认网关（非权威运行链）</h2>
          <span className="mp-section-hint">
            仅用于旧网关兼容 · 权威运行链未全部就绪时禁止切换
          </span>
        </div>
        <div className="mp-gateway-bar">
          <label className="mp-field">
            <span className="mp-field-label">当前默认</span>
            <select
              className="mp-input"
              value={gwChoice}
              onChange={(e) => setGwChoice(e.target.value)}
              title={!runtimeProjection.isReady ? "请先在模型路由页补齐权威供应商、路由和健康证据" : gwBusy ? "正在保存默认网关" : !(gatewayApi.data?.options || []).length ? "当前没有可选择的兼容网关" : "选择兼容默认网关"}
              disabled={
                gwBusy ||
                !(gatewayApi.data?.options || []).length ||
                !runtimeProjection.isReady
              }
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
            disabled={gwBusy || !gwChoice || !runtimeProjection.isReady}
            title={!runtimeProjection.isReady ? "请先在模型路由页补齐权威供应商、路由和健康证据" : gwBusy ? "正在保存默认网关" : !gwChoice ? "请先选择兼容默认网关" : "保存兼容默认网关"}
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
          <h2 className="mp-section-title">兼容网关发现 / 已安装插件</h2>
          <span className="mp-section-hint">
            插件 {pluginsApi.data?.totals?.installed ?? installedPlugins.length} · 兼容发现{" "}
            {data?.items?.length || 0}
          </span>
        </div>
        <div className="mp-card-grid">
          {(data?.items || []).map((p) => {
            return (
              <div key={`rt-${p.id}`} className="mp-provider-card is-warn">
                <div className="mp-provider-card-head">
                  <div>
                    <div className="mp-provider-name">{p.name || p.id}</div>
                    <div className="mp-provider-meta">{providerMeta(p)} · 兼容网关发现</div>
                  </div>
                  <span className="mp-badge-warn">非运行权威</span>
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
                    title="旧网关由环境或边车托管；是否可运行必须以权威解析结果为准"
                    style={{ opacity: 0.85, cursor: "default" }}
                    data-testid="provider-runtime-hosted-badge"
                  >
                    兼容来源：环境/边车
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
                  {p.ready ? "插件配置就绪" : "已安装"}
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
                    取消插件就绪
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn-nav-accent"
                    onClick={() => void enablePluginReady(p)}
                  >
                    启用插件就绪
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

type CircuitDraft = {
  config: GlobalCircuitConfig;
  version: number;
  updatedAt: string;
  activated: false;
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

function sameCanonicalJson(left: unknown, right: unknown): boolean {
  const canonical = (value: unknown): unknown => {
    if (Array.isArray(value)) return value.map(canonical);
    if (value && typeof value === "object") {
      return Object.fromEntries(
        Object.entries(value as Record<string, unknown>)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([key, item]) => [key, canonical(item)]),
      );
    }
    return value;
  };
  return JSON.stringify(canonical(left)) === JSON.stringify(canonical(right));
}

function sameRouterItems(left: V2RouteRule[], right: V2RouteRule[]): boolean {
  return sameCanonicalJson(left, right);
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
  const routerApi = useJsonGet<RouterConfig>("/api/models/router/draft");
  const warm = useJsonGet<{
    ready?: boolean;
    models?: { id: string; state?: string }[];
    sidecar?: string;
  }>("/v1/aip/models/warmup");
  const runtimeApi = useJsonGet<ModelRuntimeOverview>("/v1/aip/model-runtime/overview");
  const runtimeProjection = canonicalRuntimeProjection(runtimeApi.data, runtimeApi.err);
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
  const configEditable = confirmedVersion != null && routeRows.length > 0 && !routerApi.err;

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
    if (!configEditable || confirmedVersion == null) {
      setLocalErr("路由配置尚未完成权威读取，暂不能保存");
      return;
    }
    setSaving(true);
    setLocalErr(null);
    setSaveMsg("");
    try {
      const saved = await apiPut<RouterConfig>("/api/models/router/draft", {
        items: routeRows,
        expectedVersion: confirmedVersion,
      });
      if (saved.version <= confirmedVersion) {
        throw new Error("保存回包版本未递增，未确认成功");
      }
      const reread = await apiGet<RouterConfig>("/api/models/router/draft");
      if (reread.version !== saved.version || !sameRouterItems(reread.items, saved.items)) {
        throw new Error("写入已提交，但配置重读与保存回包不一致");
      }
      setRouteRows(reread.items);
      setConfirmedVersion(reread.version);
      routerApi.setData(reread);
      setSaveMsg(`路由配置草稿已保存并重读确认 · v${reread.version} · 未激活运行`);
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
    } finally {
      setSaving(false);
    }
  }

  async function runCircuitDrill() {
    setDrillMsg("");
    setLocalErr(null);
    if (!runtimeProjection.isReady) {
      setLocalErr("权威模型运行链尚未全部就绪，禁止熔断演练");
      return;
    }
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
    if (!runtimeProjection.isReady) {
      setChatErr("权威模型运行链尚未全部就绪，禁止试聊");
      return;
    }
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
                    disabled={!runtimeProjection.isReady}
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
            <button
              type="button"
              className="btn-primary"
              disabled={!runtimeProjection.isReady}
              onClick={() => void tryChat()}
            >
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
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, margin: "10px 0 12px" }}>
        {[
          ["路由规则", routeRows.length],
          ["候选模型", items.length],
          ["配置版本", confirmedVersion ?? "—"],
          ["预热就绪", warm.data?.ready ? "是" : "否"],
        ].map(([name, count]) => (
          <div key={String(name)} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{name}</div>
            <div style={{ fontSize: 22, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{count}</div>
          </div>
        ))}
      </div>
      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            models.reload();
            routerApi.reload();
            warm.reload();
            runtimeApi.reload();
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
            ? "路由配置服务尚未响应；请重启 AOS 服务后点刷新"
            : models.err || warm.err || routerApi.err || localErr}
        </p>
      )}

      <BpBanner tone={runtimeProjection.isReady ? "info" : "warn"}>
        <strong>权威模型运行状态：</strong>{" "}
        {runtimeApi.err
          ? `读取失败（${runtimeApi.err}）。`
          : `${runtimeProjection.ready}/${runtimeProjection.total} 条路由已就绪。`}
        {!runtimeProjection.isReady && (
          <>
            {runtimeProjection.blockers.length
              ? ` 阻断：${formatBlockers(runtimeProjection.blockers)}。`
              : " 当前没有可核验的就绪解析结果。"}
            {" "}路由配置仍可编辑并保存；熔断演练、路由测试和试聊继续失败关闭。
          </>
        )}
      </BpBanner>

      <p className="mr-hint">
        本页配置与运行分门：配置完成权威读取后即可维护；只有 Provider Health、价格、评测等运行证据全部就绪时，才允许演练、路由测试和试聊。
      </p>

      <div className="mr-rules-card">
        <div className="mr-rules-head">
          <h2 className="mr-rules-title">路由规则</h2>
          <span className="mr-rules-meta">
            任务类型 / 回退 / 出境 · {configEditable ? "草稿可编辑" : "等待草稿读取"} · 草稿版本 v{confirmedVersion ?? "—"}
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
                  <td>{businessDisplayName(r.task, "业务任务")}</td>
                  {r.span ? (
                    <td className="mr-egress-bad" colSpan={2}>
                      <span className="mr-span-label">熔断降级 → </span>
                      <select
                        className="mr-select"
                        value={r.primary}
                        disabled={!configEditable}
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
                          disabled={!configEditable}
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
                          disabled={!configEditable}
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
                      disabled={!configEditable}
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
            disabled={
              saving ||
              routeRows.length === 0 ||
              confirmedVersion == null ||
              !configEditable
            }
            onClick={() => void saveRoutes()}
          >
            {saving ? "保存中…" : "保存配置草稿"}
          </button>
          <button
            type="button"
            className="btn-nav"
            disabled={
              confirmedVersion == null ||
              routeRows.length === 0 ||
              !runtimeProjection.isReady
            }
            title={!runtimeProjection.isReady ? "请先补齐权威模型供应商、路由和健康证据" : confirmedVersion == null ? "请先读取权威路由配置" : routeRows.length === 0 ? "当前没有可演练的路由规则" : "按当前精确配置执行隔离熔断演练"}
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
        runtimeReady={runtimeProjection.isReady}
      />
    </S2Chrome>
  );
}

/** Phase B · 权重分配 / 全局熔断配置 / Fallback 链 / 路由测试 */
function ModelRouterPanels({
  routeRows,
  configVersion,
  runtimeReady,
}: {
  routeRows: V2RouteRule[];
  configVersion: number | null;
  runtimeReady: boolean;
}) {
  const [activePanel, setActivePanel] = useState<"weights" | "circuit" | "fallback" | "test">(
    "weights",
  );
  const circuitApi = useJsonGet<CircuitDraft>("/api/models/router/draft/circuit-config");
  const [circuitDraft, setCircuitDraft] = useState<GlobalCircuitConfig | null>(null);
  const [circuitVersion, setCircuitVersion] = useState<number | null>(null);
  const [circuitSaving, setCircuitSaving] = useState(false);
  const [circuitMsg, setCircuitMsg] = useState("");
  const [testRouteId, setTestRouteId] = useState("");
  const [testPrompt, setTestPrompt] = useState("你好，介绍一下本系统的模型路由");
  const [testResult, setTestResult] = useState<RouteTestResult | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [testErr, setTestErr] = useState<string | null>(null);

  const v2Rules = routeRows;
  const circuitCfg = circuitDraft || circuitApi.data?.config || {
    error_rate_threshold_pct: 10,
    latency_p99_ms: 3000,
    cooldown_seconds: 30,
    half_open_probes: 3,
  };

  useEffect(() => {
    if (!circuitDraft && circuitApi.data) {
      setCircuitDraft(circuitApi.data.config);
      setCircuitVersion(circuitApi.data.version);
    }
  }, [circuitApi.data]);

  useEffect(() => {
    if (!testRouteId && v2Rules.length > 0) {
      setTestRouteId(v2Rules[0].id);
    }
  }, [v2Rules]);

  async function saveCircuitConfig() {
    if (!circuitDraft || circuitVersion == null || circuitApi.err) {
      setCircuitMsg("熔断配置尚未完成权威读取，暂不能保存");
      return;
    }
    setCircuitSaving(true);
    setCircuitMsg("");
    try {
      const saved = await apiPut<CircuitDraft>("/api/models/router/draft/circuit-config", {
        config: circuitDraft,
        expectedVersion: circuitVersion,
      });
      const reread = await apiGet<CircuitDraft>("/api/models/router/draft/circuit-config");
      if (
        reread.version !== saved.version ||
        !sameCanonicalJson(reread.config, saved.config)
      ) {
        throw new Error("熔断配置写入后重读不一致");
      }
      setCircuitDraft(reread.config);
      setCircuitVersion(reread.version);
      circuitApi.setData(reread);
      setCircuitMsg(`熔断配置草稿已保存并重读确认 · v${reread.version} · 未激活运行`);
    } catch (e) {
      setCircuitMsg(String((e as Error).message || e));
    } finally {
      setCircuitSaving(false);
    }
  }

  async function runRouteTest() {
    if (!testRouteId || configVersion == null || !runtimeReady) {
      setTestErr("权威模型运行链尚未全部就绪，禁止路由测试");
      return;
    }
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
          {tabBtn("fallback", "故障回退链")}
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
                    {businessDisplayName(rule.task, "业务任务")}
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
                  disabled={Boolean(circuitApi.err)}
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
                <input
                  type="number"
                  aria-label="5xx 错误率阈值数值"
                  min={1}
                  max={50}
                  value={circuitCfg.error_rate_threshold_pct ?? 10}
                  onChange={(e) => setCircuitDraft({ ...circuitCfg, error_rate_threshold_pct: Number(e.target.value) })}
                  style={{ width: "4rem", textAlign: "right" }}
                />
                <span>%</span>
              </div>
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
              <span style={{ color: "#6b7280" }}>延迟 p99 阈值</span>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="range"
                  disabled={Boolean(circuitApi.err)}
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
                <input
                  type="number"
                  aria-label="延迟 p99 阈值数值"
                  min={500}
                  max={10000}
                  step={500}
                  value={circuitCfg.latency_p99_ms ?? 3000}
                  onChange={(e) => setCircuitDraft({ ...circuitCfg, latency_p99_ms: Number(e.target.value) })}
                  style={{ width: "5rem", textAlign: "right" }}
                />
                <span>ms</span>
              </div>
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
              <span style={{ color: "#6b7280" }}>熔断时长</span>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="range"
                  disabled={Boolean(circuitApi.err)}
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
                <input
                  type="number"
                  aria-label="熔断时长数值"
                  min={10}
                  max={300}
                  step={10}
                  value={circuitCfg.cooldown_seconds ?? 30}
                  onChange={(e) => setCircuitDraft({ ...circuitCfg, cooldown_seconds: Number(e.target.value) })}
                  style={{ width: "4.5rem", textAlign: "right" }}
                />
                <span>s</span>
              </div>
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
              <span style={{ color: "#6b7280" }}>半开探测请求数</span>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="range"
                  disabled={Boolean(circuitApi.err)}
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
                <input
                  type="number"
                  aria-label="半开探测请求数值"
                  min={1}
                  max={20}
                  value={circuitCfg.half_open_probes ?? 3}
                  onChange={(e) => setCircuitDraft({ ...circuitCfg, half_open_probes: Number(e.target.value) })}
                  style={{ width: "4rem", textAlign: "right" }}
                />
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
              disabled={circuitSaving || Boolean(circuitApi.err) || circuitVersion == null}
              onClick={() => void saveCircuitConfig()}
            >
              {circuitSaving ? "保存中…" : "保存熔断配置草稿"}
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
                  {businessDisplayName(rule.task, "业务任务")}
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
              disabled={!runtimeReady}
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
              disabled={!runtimeReady}
              onChange={(e) => setTestPrompt(e.target.value)}
              style={{ flex: 1, minWidth: "16rem" }}
              aria-label="test-prompt"
            />
            <button
              type="button"
              className="btn-primary"
              disabled={testLoading || !testRouteId || configVersion == null || !runtimeReady}
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
          {circuitApi.err === "Not Found" ? "熔断配置服务尚未响应；请刷新或检查 AOS 服务" : circuitApi.err}
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

export type EvalTargetInventoryItem = {
  key: string;
  targetType: "业务逻辑" | "原子技能" | "数字同事" | "模型";
  displayName: string;
  assetId: string;
  revision: string;
  contentHash: string;
  evidenceState: "可直接评测" | "需独立执行" | "缺精确版本";
  executionPlan: string;
  costEvidence: string;
  href: string;
};

type EvalTargetInventorySources = {
  graphs: Array<{ id: string; name: string; revision: number; graph_hash: string }>;
  skills: unknown[];
  agents: unknown[];
  models: unknown[];
};

function evalRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function evalExactHash(value: unknown): string {
  const candidate = String(value || "").trim();
  return /^[0-9a-f]{64}$/i.test(candidate) ? candidate : "";
}

export function buildEvalTargetInventory(sources: EvalTargetInventorySources): EvalTargetInventoryItem[] {
  const rows: EvalTargetInventoryItem[] = sources.graphs.map((graph) => ({
    key: `logic:${graph.id}@${graph.revision}`,
    targetType: "业务逻辑",
    displayName: businessDisplayName(graph.name),
    assetId: graph.id,
    revision: String(graph.revision),
    contentHash: evalExactHash(graph.graph_hash),
    evidenceState: evalExactHash(graph.graph_hash) ? "可直接评测" : "缺精确版本",
    executionPlan: evalExactHash(graph.graph_hash)
      ? "选择套件后由内部确定性执行器运行并检查门控"
      : "先回到业务逻辑编排保存精确修订与 SHA-256",
    costEvidence: "内部确定性 Logic；不调用模型供应商，模型费用不适用",
    href: "/aip/logic",
  }));

  for (const raw of sources.skills) {
    const skill = evalRecord(raw);
    const id = String(skill.skillId || "").trim();
    const revision = Number(skill.revision || 0);
    if (!id) continue;
    const hash = evalExactHash(skill.contentHash);
    rows.push({
      key: `skill:${id}@${revision || "unknown"}`,
      targetType: "原子技能",
      displayName: businessDisplayName(String(skill.displayName || skill.canonicalLogicId || id)),
      assetId: id,
      revision: revision > 0 ? String(revision) : "",
      contentHash: hash,
      evidenceState: revision > 0 && hash ? "需独立执行" : "缺精确版本",
      executionPlan: revision > 0 && hash
        ? "在技能发布前绑定评测套件、数据集和裁判版本，形成不可变 EvalRun"
        : "先补齐技能精确修订和 SHA-256，再建立 EvalRun",
      costEvidence: "尚无该技能 EvalRun usage 证据；不得显示为零费用",
      href: "/aip/skill-publish",
    });
  }

  for (const raw of sources.agents) {
    const item = evalRecord(raw);
    const template = evalRecord(item.template);
    const id = String(template.templateId || "").trim();
    const revision = Number(template.revision || 0);
    if (!id) continue;
    const hash = evalExactHash(template.contentHash);
    rows.push({
      key: `agent:${id}@${revision || "unknown"}`,
      targetType: "数字同事",
      displayName: businessDisplayName(String(template.displayName || id)),
      assetId: id,
      revision: revision > 0 ? String(revision) : "",
      contentHash: hash,
      evidenceState: revision > 0 && hash ? "需独立执行" : "缺精确版本",
      executionPlan: revision > 0 && hash
        ? "按模板精确版本执行角色任务集，记录样本、失败项、工具调用与 EvalRun"
        : "先补齐数字同事模板精确修订和 SHA-256",
      costEvidence: "尚无该数字同事 EvalRun usage 证据；不得推算费用",
      href: "/aip/agent-registry",
    });
  }

  for (const raw of sources.models) {
    const model = evalRecord(raw);
    const registration = evalRecord(model.registration);
    const id = String(model.id || model.model || "").trim();
    if (!id) continue;
    const revision = String(model.revision || registration.revision || "").trim();
    const hash = evalExactHash(model.contentHash || registration.contentHash);
    rows.push({
      key: `model:${id}@${revision || "unknown"}`,
      targetType: "模型",
      displayName: businessDisplayName(String(model.displayName || model.model || id)),
      assetId: id,
      revision,
      contentHash: hash,
      evidenceState: revision && hash ? "需独立执行" : "缺精确版本",
      executionPlan: revision && hash
        ? "通过受控模型路由执行质量、延迟和费用评测，保存供应商回包证据"
        : "模型目录仅证明发现；需先形成注册修订、SHA-256 与受控路由",
      costEvidence: "缺同次运行 usage 与价格权威；不展示虚假费用数字",
      href: "/aip/model-catalog",
    });
  }
  return rows;
}

export function exactEvalRegressionHistory(
  history: EvalReport[],
  target: { id: string; revision: number; graph_hash: string },
): EvalReport[] {
  return history.filter((item) => (
    item.target_type === "logic_graph"
    && item.target_id === target.id
    && item.target_revision === target.revision
    && item.target_hash === target.graph_hash
  ));
}

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
  const [searchParams] = useSearchParams();
  const suiteFromUrl = String(searchParams.get("suite") || "").trim();
  const proposalFromUrl = String(searchParams.get("proposal") || "").trim();
  const suitesApi = useJsonGet<{ items: EvalSuiteSummary[] }>("/v1/evals/suites");
  const graphsApi = useJsonGet<{ items: Array<{ id: string; name: string; revision: number; graph_hash: string; persisted: boolean }> }>("/v1/aip/logic/graphs");
  const [suiteId, setSuiteId] = useState(suiteFromUrl);
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
  const [targetInventory, setTargetInventory] = useState<EvalTargetInventoryItem[]>([]);
  const [inventoryState, setInventoryState] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [inventoryMessage, setInventoryMessage] = useState("");
  const [regressionHistory, setRegressionHistory] = useState<EvalReport[]>([]);
  const [historyState, setHistoryState] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [historyMessage, setHistoryMessage] = useState("");

  const suites = suitesApi.data?.items || [];
  const graphs = graphsApi.data?.items || [];
  const selectedSuite = suites.find((suite) => suite.id === suiteId) || null;
  const selectedGraph = graphs.find((graph) => graph.id === targetId) || null;

  useEffect(() => {
    if (suiteFromUrl) {
      setSuiteId(suiteFromUrl);
      return;
    }
    if (!suiteId && suites[0]?.id) setSuiteId(suites[0].id);
  }, [suiteFromUrl, suiteId, suites]);
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
      setAuthorityError("请输入真实评测运行标识");
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

  async function loadTargetInventory() {
    setInventoryState("loading");
    setInventoryMessage("");
    try {
      const results = await Promise.allSettled([
        apiGet<{ items?: unknown[] }>("/v1/aip/skills?limit=200"),
        apiGet<{ items?: unknown[] }>("/v1/aip/agent-registry"),
        (async () => {
          try {
            const admin = await apiGet<{ items?: unknown[] }>("/v1/aip/model-admin/models");
            if ((admin.items || []).length > 0) return admin;
          } catch {
            // 权威管理目录不可读时继续读取发现目录；两者都失败才由 allSettled 记录缺证。
          }
          return apiGet<{ items?: unknown[] }>("/v1/aip/model-catalog");
        })(),
      ]);
      const failed = results.filter((item) => item.status === "rejected").length;
      const items = buildEvalTargetInventory({
        graphs,
        skills: results[0].status === "fulfilled" ? results[0].value.items || [] : [],
        agents: results[1].status === "fulfilled" ? results[1].value.items || [] : [],
        models: results[2].status === "fulfilled" ? results[2].value.items || [] : [],
      });
      setTargetInventory(items);
      setInventoryState(failed === results.length ? "error" : "loaded");
      setInventoryMessage(
        failed > 0
          ? `已读取 ${items.length} 个目标；${failed} 类权威目录读取失败，缺失部分保持缺证。`
          : `已读取 ${items.length} 个真实评测目标。`,
      );
    } catch (error) {
      setTargetInventory([]);
      setInventoryState("error");
      setInventoryMessage(`评测目标读取失败：${String((error as Error).message || error)}`);
    }
  }

  async function loadRegressionHistory() {
    if (!suiteId || !selectedGraph) return;
    setHistoryState("loading");
    setHistoryMessage("");
    setRegressionHistory([]);
    try {
      const response = await apiGet<{ items?: EvalReport[] }>(`/v1/evals/${encodeURIComponent(suiteId)}/history`);
      const exact = exactEvalRegressionHistory(response.items || [], selectedGraph);
      setRegressionHistory(exact);
      setHistoryState("loaded");
      setHistoryMessage(
        exact.length > 0
          ? `已读取当前 Logic 精确修订的 ${exact.length} 次回归。`
          : "该套件尚无绑定当前 Logic 精确修订的回归记录。",
      );
    } catch (error) {
      setHistoryState("error");
      setHistoryMessage(`回归历史读取失败：${String((error as Error).message || error)}`);
    }
  }

  return (
    <S2Chrome title="评测门控" lede="自动化业务逻辑上线前必须通过真实评测；未达标时禁止发布或自动执行。">
      <AipOperationalProjectionStrip />
      <div
        data-testid="evals-ops-stats"
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, margin: "0 0 12px" }}
      >
        {[
          { label: "套件数", value: String(suites.length) },
          { label: "图目标", value: String(graphs.length) },
          { label: "门控", value: gate ? (gate.gate_passed ? "通过" : "未过") : "未跑" },
          { label: "通过率", value: report ? `${Math.round((report.pass_rate || 0) * 100)}%` : "—" },
          { label: "用例", value: report ? `${report.passed}/${report.total}` : "—" },
          { label: "权威运行", value: authorityState === "loaded" ? "已读取" : authorityState === "error" ? "失败" : authorityState === "loading" ? "读取中" : "暂无" },
        ].map((s) => (
          <div key={s.label} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{s.value}</div>
          </div>
        ))}
      </div>
      <BpToolbar>
        <select
          aria-label="评测套件"
          className="aos-input"
          value={suiteId}
          onChange={(event) => {
            setSuiteId(event.target.value);
            setReport(null);
            setGate(null);
            setMsg("");
            setRegressionHistory([]);
            setHistoryState("idle");
            setHistoryMessage("");
          }}
        >
          <option value="">选择评测套件</option>
          {suites.map((suite) => (
            <option key={suite.id} value={suite.id}>{businessDisplayName(suite.name)}</option>
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
            setRegressionHistory([]);
            setHistoryState("idle");
            setHistoryMessage("");
          }}
        >
          <option value="">选择已保存业务逻辑</option>
          {graphs.map((graph) => (
            <option key={graph.id} value={graph.id}>{businessDisplayName(graph.name)} · 修订 {graph.revision}</option>
          ))}
        </select>
        <span className="aos-text">实际执行绑定已保存业务逻辑的精确修订与内容摘要，不接受独立目标表达式</span>
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
        <button type="button" className="btn" disabled={inventoryState === "loading"} onClick={() => void loadTargetInventory()}>
          {inventoryState === "loading" ? "读取目标中…" : "读取全部评测目标"}
        </button>
        <button type="button" className="btn" disabled={!suiteId || !selectedGraph || historyState === "loading"} onClick={() => void loadRegressionHistory()}>
          {historyState === "loading" ? "读取历史中…" : "加载回归历史"}
        </button>
        <Link to="/aip/maturity" className="btn-nav">
          ← 成熟度
        </Link>
      </BpToolbar>
      {suitesApi.loading && <p className="aos-text">正在读取评测套件…</p>}
      {!suitesApi.loading && !suitesApi.err && suites.length === 0 && (
        <p className="error">暂无评测套件，可创建下方基础套件后运行真实评测。</p>
      )}
      {msg && <p className="aos-text" role="status">{msg}</p>}
      {(suitesApi.err || graphsApi.err || runErr) && <p className="error" role="alert">{runErr || suitesApi.err || graphsApi.err}</p>}

      <BpBanner tone="info">
        <strong>快速开始</strong> · 套件“{QUICK_START_EVAL_SUITE.name}” · 用例：输入 x=1，期望 2（精确匹配） · 门控阈值 100%。
        创建动作会真实保存评测套件，但不会生成评测报告；运行时必须绑定已保存业务逻辑的精确版本。
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
            label: "评测门控检查",
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

      <section style={{ border: "1px solid var(--aos-border)", padding: 16, marginTop: 16 }} data-testid="eval-target-inventory">
        <h3 style={{ marginTop: 0 }}>全量评测目标与执行计划</h3>
        <p className="aos-text">
          业务逻辑、原子技能、数字同事和模型分别核验精确版本。只有当前内部执行器支持的 Logic 可在本页直接运行；其他目标必须形成独立 EvalRun，不能以目录登记替代评测。
        </p>
        {inventoryMessage && <p className={inventoryState === "error" ? "error" : "aos-text"} role="status">{inventoryMessage}</p>}
        {targetInventory.length > 0 ? (
          <BpTable
            columns={["目标类型", "业务名称", "精确版本", "评测状态", "执行计划", "费用证据", "治理入口"]}
            rows={targetInventory.map((item) => [
              item.targetType,
              item.displayName,
              item.revision && item.contentHash
                ? <>修订 {item.revision}<details><summary>SHA-256</summary><code>{item.contentHash}</code></details></>
                : "缺精确修订或 SHA-256",
              item.evidenceState,
              item.executionPlan,
              item.costEvidence,
              <Link to={item.href}>处理 →</Link>,
            ])}
          />
        ) : (
          <BpBanner tone="info">点击“读取全部评测目标”后，从四类权威目录构建执行清单；页面不会预置演示目标。</BpBanner>
        )}
      </section>

      <section style={{ border: "1px solid var(--aos-border)", padding: 16, marginTop: 16 }} data-testid="eval-regression-history">
        <h3 style={{ marginTop: 0 }}>精确版本回归比较</h3>
        {historyMessage && <p className={historyState === "error" ? "error" : "aos-text"} role="status">{historyMessage}</p>}
        {regressionHistory.length > 0 ? (
          <BpTable
            columns={["运行时间", "通过率", "失败用例", "门控结论", "变化"]}
            rows={regressionHistory.map((item, index) => {
              const previous = index > 0 ? regressionHistory[index - 1] : null;
              const delta = previous ? item.pass_rate - previous.pass_rate : null;
              return [
                item.run_at,
                `${(item.pass_rate * 100).toFixed(1)}%`,
                String(item.failed),
                item.gate_passed ? "通过" : "未通过",
                delta == null ? "基线" : `${delta >= 0 ? "+" : ""}${(delta * 100).toFixed(1)} 个百分点`,
              ];
            })}
          />
        ) : (
          <BpBanner tone="info">选择评测套件和已保存业务逻辑后加载历史；只比较相同 target revision/hash，禁止跨版本混算。</BpBanner>
        )}
        <p className="aos-text">评测失败须回到业务逻辑、技能、数字同事或模型治理入口整改后再跑；豁免必须来自权威审批记录，本页不提供手工豁免或绿灯。</p>
      </section>

      <BpBanner tone="warn">
        <span data-testid="evals-chain-banner">
        <strong>真实门控口径</strong> · 本页不提供手工绿灯。只有服务端门控检查返回通过才显示评测通过；受控自动化仍须草稿审批与其他发布护栏 ·{" "}
        <Link
          to={proposalFromUrl ? `/aip/drafts?proposal=${encodeURIComponent(proposalFromUrl)}` : "/aip/drafts"}
          data-testid="evals-jump-drafts"
        >
          查看草稿审批 →
        </Link>
        {proposalFromUrl && (
          <>
            {" · "}
            <Link
              to={`/aip/lineage?rootType=action&rootId=${encodeURIComponent(proposalFromUrl)}`}
              data-testid="evals-jump-lineage"
            >
              决策谱系 →
            </Link>
          </>
        )}
        {gate?.gate_passed && (
          <>
            {" · "}
            <Link to="/aip/studio">智能体配置试运行 →</Link>
          </>
        )}
        {suiteFromUrl && (
          <span className="aos-text"> · 深链套件 <code>{suiteFromUrl}</code></span>
        )}
        </span>
      </BpBanner>

      <section style={{ border: "1px solid var(--aos-border)", padding: 16, marginTop: 16 }} data-testid="eval-authority-reader">
        <h3 style={{ marginTop: 0 }}>权威评测运行核查</h3>
        <p className="aos-text">旧评测入口保持兼容；此处只读不可变的评测运行引用，不允许手工修改状态或版本摘要。</p>
        <BpToolbar>
          <input
            aria-label="eval-authority-run-id"
            value={authorityRunId}
            onChange={(event) => setAuthorityRunId(event.target.value)}
            placeholder="输入真实评测运行标识"
          />
          <button type="button" className="btn" onClick={() => void readAuthorityRun()} disabled={authorityState === "loading"}>
            {authorityState === "loading" ? "读取中…" : "读取权威评测运行"}
          </button>
        </BpToolbar>
        {authorityState === "idle" && !authorityError && <p className="aos-text">尚未选择权威评测运行。</p>}
        {authorityError && <p className="error" role="alert">权威评测运行读取失败：{authorityError}</p>}
        {authorityRun && (
          <BpTable
            columns={["运行标识", "状态", "评测套件版本", "目标版本", "数据集版本", "裁判版本"]}
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
          { to: "/aip/logic", label: "业务逻辑编排" },
          {
            to: proposalFromUrl ? `/aip/drafts?proposal=${encodeURIComponent(proposalFromUrl)}` : "/aip/drafts",
            label: "草稿审批台",
          },
          {
            to: proposalFromUrl
              ? `/aip/lineage?rootType=action&rootId=${encodeURIComponent(proposalFromUrl)}`
              : "/aip/lineage",
            label: "决策谱系",
          },
        ]}
      />
    </S2Chrome>
  );
}

const LINEAGE_EVENT_LABELS: Record<string, string> = {
  input: "接收业务输入",
  planned: "形成执行计划",
  proposed: "提出受控动作",
  drafted: "生成待审草稿",
  approved: "审批通过",
  rejected: "审批驳回",
  withdrawn: "发起人撤回",
  leased: "取得执行租约",
  executing: "开始受控执行",
  applied: "业务结果已确认",
  failed: "执行失败",
  unknown: "结果待对账",
  reconciled: "完成结果对账",
  compensated: "完成补偿处置",
  evaluated: "完成质量评测",
  published: "完成受控发布",
};

function lineageEventDisplayName(value: string): string {
  return LINEAGE_EVENT_LABELS[value.toLowerCase()] || businessDisplayName(value, "业务事件");
}

function lineageSourceDisplayName(value: string | null): string {
  if (!value) return "权威业务记录";
  const labels: Record<string, string> = {
    task: "经营任务",
    task_run: "任务运行",
    action: "受控动作",
    action_proposal: "受控动作提案",
    approval: "审批记录",
    lease: "执行租约",
    receipt: "交付凭证",
    evidence: "业务证据",
    eval_run: "评测运行",
    usage: "资源用量凭证",
    publication: "发布记录",
    research_job: "研究任务",
  };
  return labels[value.toLowerCase()] || businessDisplayName(value, "权威业务记录");
}

function lineageQualityDisplayName(value: string): string {
  return value === "measured" ? "权威实测" : value === "estimated" ? "估算证据" : "质量待核验";
}

function lineageSubjectSummary(subject: Record<string, unknown>): string {
  for (const key of ["displayName", "name", "title", "purpose", "objectType", "resourceType"]) {
    const value = subject[key];
    if (typeof value === "string" && value.trim()) return businessDisplayName(value, value);
  }
  return "关联业务对象";
}

export function DecisionLineagePage() {
  const [searchParams] = useSearchParams();
  const rootTypeFromUrl = String(searchParams.get("rootType") || "").trim();
  const rootIdFromUrl = String(searchParams.get("rootId") || "").trim();
  const proposalFromUrl = String(searchParams.get("proposal") || "").trim();
  const initialRootType = (LINEAGE_ROOT_TYPES.includes(rootTypeFromUrl as LineageRootType)
    ? rootTypeFromUrl
    : "task_run") as LineageRootType;
  const [rootType, setRootType] = useState<LineageRootType>(initialRootType);
  const [rootId, setRootId] = useState(rootIdFromUrl);
  const [chain, setChain] = useState<AuthorityEvidenceChain | null>(null);
  const [recentActions, setRecentActions] = useState<ActionDraftBundle[]>([]);
  const [recentRuns, setRecentRuns] = useState<AssistSubjectOption[]>([]);
  const [recentState, setRecentState] = useState<"loading" | "loaded" | "error">("loading");
  const [loadState, setLoadState] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [localErr, setLocalErr] = useState<string | null>(null);
  const [keyword, setKeyword] = useState("");
  const [eventFilter, setEventFilter] = useState("all");

  async function load(nextType: LineageRootType = rootType, nextId: string = rootId) {
    const target = nextId.trim();
    if (!target) {
      setLocalErr("请输入真实 Root ID");
      setLoadState("idle");
      return;
    }
    setLocalErr(null);
    setChain(null);
    setLoadState("loading");
    try {
      setChain(await aipEvidenceSdk.evidenceChain(nextType, target));
      setLoadState("loaded");
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
      setLoadState("error");
    }
  }

  useEffect(() => {
    let active = true;
    setRecentState("loading");
    void Promise.all([aipActionsSdk.list(30), listAssistSubjects(30)]).then(([actions, runs]) => {
      if (!active) return;
      setRecentActions(actions.items);
      setRecentRuns(runs.items);
      setRecentState("loaded");
    }).catch(() => {
      if (!active) return;
      setRecentActions([]);
      setRecentRuns([]);
      setRecentState("error");
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (rootTypeFromUrl && LINEAGE_ROOT_TYPES.includes(rootTypeFromUrl as LineageRootType)) {
      setRootType(rootTypeFromUrl as LineageRootType);
    }
    if (rootIdFromUrl) setRootId(rootIdFromUrl);
  }, [rootTypeFromUrl, rootIdFromUrl]);

  useEffect(() => {
    if (!rootIdFromUrl) return;
    const type = (LINEAGE_ROOT_TYPES.includes(rootTypeFromUrl as LineageRootType)
      ? rootTypeFromUrl
      : rootType) as LineageRootType;
    void load(type, rootIdFromUrl);
    // deep-link auto query once per URL change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rootTypeFromUrl, rootIdFromUrl]);

  const events = chain?.events ?? [];
  const lineageId = chain?.lineageId ?? null;
  const eventTypes = useMemo(() => Array.from(new Set(events.map((event) => event.eventType))).sort(), [events]);
  const filteredEvents = useMemo(() => {
    const query = keyword.trim().toLowerCase();
    return events.filter((event) => {
      if (eventFilter !== "all" && event.eventType !== eventFilter) return false;
      if (!query) return true;
      return [event.eventType, event.sourceKind, event.sourceId, event.subject && JSON.stringify(event.subject), event.artifact && JSON.stringify(event.artifact)]
        .filter(Boolean).join(" ").toLowerCase().includes(query);
    });
  }, [eventFilter, events, keyword]);
  const chainProposalId =
    rootType === "action" && rootId.trim()
      ? rootId.trim()
      : proposalFromUrl || "";
  const selectedAction = recentActions.find((item) => item.proposal.id === (rootType === "action" ? rootId : ""));
  const rootLabel = selectedAction
    ? `${actionDisplayName(selectedAction.proposal.actionType.actionTypeId)} · ${selectedAction.proposal.purpose}`
    : rootType === "task_run" ? "任务运行" : rootType === "action" ? "受控动作" : rootType === "eval_run" ? "评测运行" : rootType === "publication" ? "发布记录" : rootType === "research_job" ? "研究任务" : "历史决策谱系";

  return (
    <S2Chrome
      title="决策谱系"
      lede="从服务端权威事件还原任务运行、受控动作、评测、发布与研究任务之间的因果链；无真实标识时保持空态，不伪造链路。"
    >
      <div
        data-testid="lineage-ops-stats"
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, margin: "0 0 12px" }}
      >
        {[
          { label: "当前业务记录", value: rootLabel },
          { label: "加载态", value: loadState === "loaded" ? "已载" : loadState === "loading" ? "读取中" : loadState === "error" ? "失败" : "空闲" },
          { label: "事件数", value: String(events.length) },
          { label: "观测记录", value: chain ? String(chain.spans.length) : "—" },
          { label: "用量凭证", value: chain ? String(chain.usageReceipts.length) : "—" },
          { label: "证据闭环", value: lineageId && chain?.spans.length && chain?.usageReceipts.length ? "完整" : "待补证" },
        ].map((s) => (
          <div key={s.label} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{s.value}</div>
          </div>
        ))}
      </div>
      {(rootIdFromUrl || chainProposalId) && (
        <BpBanner tone="info">
          <span data-testid="lineage-chain-banner">
          已从关联页面带入查询起点
          <details><summary>技术标识（审计用）</summary><code>{rootType}/{rootId.trim() || rootIdFromUrl}</code>{chainProposalId ? <> · 提案 <code>{chainProposalId}</code></> : null}</details>
          </span>
        </BpBanner>
      )}
      <section className="card" style={{ padding: 16, marginBottom: 12 }} data-testid="lineage-business-selector">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div>
            <strong>选择最近业务记录</strong>
            <div className="muted" style={{ marginTop: 4 }}>从真实任务运行或受控动作进入因果链，技术标识不占用主阅读层。</div>
          </div>
          <span className="muted">{recentState === "loading" ? "读取中…" : recentState === "error" ? "最近记录读取失败，可用高级定位" : `任务运行 ${recentRuns.length} 条 · 受控动作 ${recentActions.length} 条`}</span>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          <select
            aria-label="lineage-task-run-record"
            value={rootType === "task_run" ? rootId : ""}
            onChange={(event) => {
              setRootType("task_run");
              setRootId(event.target.value);
              setChain(null);
              setLoadState("idle");
            }}
            style={{ minWidth: "min(26rem, 100%)", flex: "1 1 22rem" }}
          >
            <option value="">请选择最近任务运行</option>
            {recentRuns.map((item) => (
              <option key={item.subject.taskRunRef.resourceId} value={item.subject.taskRunRef.resourceId}>
                {item.taskTitle} · {statusDisplayName(item.runStatus)} · {item.owner}
              </option>
            ))}
          </select>
          <select
            aria-label="lineage-business-record"
            value={rootType === "action" ? rootId : ""}
            onChange={(event) => {
              setRootType("action");
              setRootId(event.target.value);
              setChain(null);
              setLoadState("idle");
            }}
            style={{ minWidth: "min(26rem, 100%)", flex: "1 1 22rem" }}
          >
            <option value="">请选择最近受控动作</option>
            {recentActions.map((item) => (
              <option key={item.proposal.id} value={item.proposal.id}>
                {actionDisplayName(item.proposal.actionType.actionTypeId)} · {item.proposal.purpose} · {statusDisplayName(item.proposal.status)}
              </option>
            ))}
          </select>
          <button type="button" className="btn" onClick={() => void load(rootType, rootId)} disabled={loadState === "loading" || !rootId.trim()}>
            {loadState === "loading" ? "读取中…" : "查看业务因果链"}
          </button>
        </div>
        {selectedAction && (
          <div style={{ display: "flex", gap: 10, marginTop: 10, flexWrap: "wrap" }} data-testid="lineage-selected-action-links">
            <Link to={`/aip/drafts?proposal=${encodeURIComponent(selectedAction.proposal.id)}`}>查看审批与结果 →</Link>
            {selectedAction.proposal.taskId && <Link to={`/aip/assist?taskId=${encodeURIComponent(selectedAction.proposal.taskId)}${selectedAction.proposal.runId ? `&runId=${encodeURIComponent(selectedAction.proposal.runId)}` : ""}`}>返回业务任务 →</Link>}
            {selectedAction.proposal.taskId && <Link to={`/aip/logic?taskId=${encodeURIComponent(selectedAction.proposal.taskId)}${selectedAction.proposal.runId ? `&runId=${encodeURIComponent(selectedAction.proposal.runId)}` : ""}`}>查看业务逻辑与运行 →</Link>}
          </div>
        )}
      </section>
      <details className="card" style={{ padding: "12px 16px", marginBottom: 12 }} data-testid="lineage-advanced-locator">
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>高级定位：Task、Run、评测、发布或研究记录</summary>
      <BpToolbar>
        <label className="muted">
          起点类型{" "}
          <select value={rootType} onChange={(event) => setRootType(event.target.value as LineageRootType)} aria-label="lineage-root-type">
            {LINEAGE_ROOT_TYPES.map((type) => <option key={type} value={type}>{type === "task_run" ? "任务运行" : type === "action" ? "受控动作" : type === "eval_run" ? "评测运行" : type === "publication" ? "发布记录" : type === "research_job" ? "研究任务" : "历史决策谱系"}</option>)}
          </select>
        </label>
        <label className="muted">
          起点标识{" "}
          <input
            value={rootId}
            onChange={(e) => setRootId(e.target.value)}
            placeholder="输入真实业务记录标识"
            aria-label="lineage-root-id"
            style={{ minWidth: "12rem" }}
          />
        </label>
        <button type="button" className="btn" onClick={() => void load()} disabled={loadState === "loading"}>
          {loadState === "loading" ? "查询中…" : "查询权威谱系"}
        </button>
      </BpToolbar>
      </details>

      {loadState === "idle" && !localErr && <BpBanner tone="info">请选择最近业务动作，或展开高级定位读取真实 Task、Run、评测、发布或研究记录；页面不会展示示例链路或固定步骤。</BpBanner>}
      {loadState === "loaded" && events.length === 0 && <BpBanner tone="warn"><span data-testid="lineage-empty">该业务记录暂无权威谱系事件。</span></BpBanner>}
      {localErr && <BpBanner tone="warn"><span data-testid="lineage-error">谱系读取失败：{localErr}</span></BpBanner>}

      {chain && events.length > 0 && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,minmax(0,1fr))", gap: 10, marginTop: 12 }} data-testid="lineage-evidence-segments">
            {[
              { label: "权威业务事件", value: `${events.length} 条`, ok: true, note: "目标、任务、审批与结果的不可变事实" },
              { label: "运行观测证据", value: chain.spans.length ? `${chain.spans.length} 条` : "缺少观测证据", ok: chain.spans.length > 0, note: "仅接受服务端 exact lineageId 对应的 Span" },
              { label: "资源用量凭证", value: chain.usageReceipts.length ? `${chain.usageReceipts.length} 条` : "缺少用量凭证", ok: chain.usageReceipts.length > 0, note: "Token、成本、时延或工具单位 Receipt" },
            ].map((segment) => (
              <div key={segment.label} className="card" style={{ padding: 14, borderLeft: `3px solid ${segment.ok ? "var(--aos-green-600)" : "var(--aos-amber)"}` }}>
                <div className="muted" style={{ fontSize: 12 }}>{segment.label}</div>
                <strong style={{ display: "block", marginTop: 4 }}>{segment.value}</strong>
                <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>{segment.note}</div>
              </div>
            ))}
          </div>
          <BpToolbar>
            <label className="muted">搜索因果节点 <input aria-label="lineage-keyword" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="业务名称、来源或对象" /></label>
            <label className="muted">事件类型 <select aria-label="lineage-event-filter" value={eventFilter} onChange={(event) => setEventFilter(event.target.value)}><option value="all">全部事件</option>{eventTypes.map((type) => <option key={type} value={type}>{lineageEventDisplayName(type)}</option>)}</select></label>
            <span className="muted">显示 {filteredEvents.length}/{events.length} 条</span>
          </BpToolbar>
        </>
      )}

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
          {filteredEvents.length} 个权威事件
          <details><summary>谱系技术标识（审计用）</summary><code>{lineageId}</code> · {rootType}/{rootId}</details>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
          {filteredEvents.map((event) => (
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
                步骤 {event.sequence}<br />{lineageEventDisplayName(event.eventType)}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ color: "var(--aos-text)", fontSize: 14 }}>{lineageSourceDisplayName(event.sourceKind)}{event.subject ? ` · ${lineageSubjectSummary(event.subject)}` : ""}</div>
                <div style={{ fontSize: 12, color: "var(--aos-muted)", marginTop: 4 }}>
                  {lineageQualityDisplayName(event.quality)} · 发生 {new Date(event.occurredAt).toLocaleString()} · 观测 {new Date(event.observedAt).toLocaleString()}
                </div>
                <details style={{ fontSize: 11, color: "var(--aos-muted)", marginTop: 4, overflowWrap: "anywhere" }}>
                  <summary>技术标识（审计用）</summary>
                  <code>source={event.sourceId || "—"} · event={event.eventId} · payload={event.payloadHash.slice(0, 12)}…{event.sourceHash ? ` · sourceHash=${event.sourceHash.slice(0, 12)}…` : ""}</code>
                </details>
              </div>
            </div>
          ))}
        </div>
      </div>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: "1rem", flexWrap: "wrap" }} data-testid="lineage-chain-links">
        {lineageId ? (
          <Link
            to={`/aip/observability?lineageId=${encodeURIComponent(lineageId)}&rootType=${encodeURIComponent(rootType)}&rootId=${encodeURIComponent(rootId.trim())}`}
            style={{
              padding: "6px 12px",
              fontSize: 12,
              borderRadius: 2,
              border: "1px solid var(--aos-green-border)",
              color: "var(--aos-green-600)",
              textDecoration: "none",
            }}
            data-testid="lineage-jump-observability"
          >
            查看精确可观测证据 →
          </Link>
        ) : (
          <span
            data-testid="lineage-observability-blocked"
            title="请先成功读取真实谱系；禁止根据业务记录标识猜测谱系标识"
            style={{ padding: "6px 12px", fontSize: 12, border: "1px solid var(--aos-border)", color: "var(--aos-muted)" }}
          >
            可观测证据（需先读取谱系）
          </span>
        )}
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
          data-testid="lineage-jump-evals"
        >
          评测门控
        </Link>
        <Link
          to={chainProposalId ? `/aip/drafts?proposal=${encodeURIComponent(chainProposalId)}` : "/aip/drafts"}
          style={{
            padding: "6px 12px",
            fontSize: 12,
            borderRadius: 2,
            border: "1px solid var(--aos-amber-border)",
            color: "var(--aos-amber-700)",
            textDecoration: "none",
          }}
          data-testid="lineage-jump-drafts"
        >
          草稿审批台 →
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

export function LegacyProviderDetailPage() {
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
                        <span title="仅有追踪标识不足以定位权威决策谱系；请从决策谱系进入可观测性">{l.trace_id.slice(0, 8)}</span>
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
