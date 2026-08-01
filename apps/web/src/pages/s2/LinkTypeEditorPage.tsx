import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { apiDelete, apiGet, apiPost, apiPut } from "../../api/client";
import { S2Chrome } from "./shared";
import { BpBanner, BpToolbar } from "./blueprintUi";

/* ────────────── Types ────────────── */

export type Cardinality = "ONE_TO_ONE" | "ONE_TO_MANY" | "MANY_TO_ONE" | "MANY_TO_MANY";
export type JoinMethod = "foreign_key" | "junction_table" | "shared_key" | "computed";

export type LinkType = {
  id: string;
  name: string;
  srcType: string;
  dstType: string;
  rel: string;
  cardinality: Cardinality;
  joinMethod: JoinMethod;
  expectedEdges: number;
  mdoApproved: boolean;
  published: boolean;
  symmetric: boolean;
  description: string;
  constraints: { field: string; rule: string }[];
};

export type LinkUsageMetric = {
  sources?: Record<string, number>;
  window_days?: number;
};

export type LinkUsageDimension = "workshop" | "aip" | "pipeline";

const LINK_USAGE_SOURCE_ALIASES: Record<LinkUsageDimension, string[]> = {
  workshop: ["workshop", "workshop_app", "workshop_apps"],
  aip: ["aip", "aip_logic", "aip_logic_node", "aip_logic_nodes"],
  pipeline: ["pipeline", "pipelines", "pipeline_reference", "pipeline_references"],
};

/* ────────────── Constants ────────────── */

export const CARDINALITIES: { value: Cardinality; label: string; icon: string }[] = [
  { value: "ONE_TO_ONE", label: "1:1", icon: "→" },
  { value: "ONE_TO_MANY", label: "1:N", icon: "→>" },
  { value: "MANY_TO_ONE", label: "N:1", icon: ">→" },
  { value: "MANY_TO_MANY", label: "N:N", icon: "<>" },
];

export const JOIN_METHODS: { value: JoinMethod; label: string; description: string }[] = [
  { value: "foreign_key", label: "外键关联", description: "目标类型持有源类型的外键" },
  { value: "junction_table", label: "交叉表", description: "独立的 junction table 维护多对多关系" },
  { value: "shared_key", label: "共享主键", description: "两表共享某个业务主键" },
  { value: "computed", label: "计算关联", description: "通过函数或表达式动态计算" },
];

export const LINK_NAV_SECTIONS = [
  { key: "overview", label: "Overview" },
  { key: "security", label: "Security" },
  { key: "datasources", label: "Datasources" },
  { key: "usage", label: "Usage" },
] as const;

/* ────────────── Pure functions ────────────── */

export const emptyForm = (id = ""): LinkType => ({
  id,
  name: "",
  srcType: "WorkOrder",
  dstType: "WorkOrder",
  rel: "related_to",
  cardinality: "MANY_TO_MANY",
  joinMethod: "foreign_key",
  expectedEdges: 0,
  mdoApproved: false,
  published: false,
  symmetric: false,
  description: "",
  constraints: [],
});

export function validateLinkType(form: LinkType): string[] {
  const errors: string[] = [];
  if (!form.id || !form.id.trim()) errors.push("id 不能为空");
  if (form.id && !/^[a-zA-Z_][a-zA-Z0-9_-]*$/.test(form.id))
    errors.push("id 必须以字母或下划线开头，只允许字母、数字、下划线、连字符");
  if (!form.name || !form.name.trim()) errors.push("name 不能为空");
  if (!form.srcType || !form.srcType.trim()) errors.push("srcType 不能为空");
  if (!form.dstType || !form.dstType.trim()) errors.push("dstType 不能为空");
  if (form.srcType === form.dstType && !form.symmetric)
    errors.push("srcType 和 dstType 相同时需要勾选 symmetric（自引用）");
  if (form.expectedEdges < 0) errors.push("expectedEdges 不能为负数");
  return errors;
}

export function isMdoRequired(expectedEdges: number): boolean {
  return expectedEdges > 100_000;
}

export function cardinalityLabel(card: Cardinality): string {
  return CARDINALITIES.find((c) => c.value === card)?.label ?? card;
}

export function cardinalityIcon(card: Cardinality): string {
  return CARDINALITIES.find((c) => c.value === card)?.icon ?? "?";
}

export function joinMethodLabel(method: JoinMethod): string {
  return JOIN_METHODS.find((j) => j.value === method)?.label ?? method;
}

export function joinMethodDescription(method: JoinMethod): string {
  return JOIN_METHODS.find((j) => j.value === method)?.description ?? "";
}

export function checkScaleWarning(form: LinkType): { warn: boolean; message: string } {
  if (isMdoRequired(form.expectedEdges) && !form.mdoApproved) {
    return {
      warn: true,
      message: `expectedEdges (${form.expectedEdges}) > 100k 且未勾选 MDO 批准，保存会被服务端拒绝（LINK_SCALE_BLOCKED）。`,
    };
  }
  return { warn: false, message: "" };
}

export function estimateStorage(form: LinkType): string {
  const edges = form.expectedEdges;
  if (edges === 0) return "0 MB";
  const perEdge = 64; // bytes
  const total = edges * perEdge;
  if (total < 1024) return `${total} B`;
  if (total < 1024 * 1024) return `${(total / 1024).toFixed(1)} KB`;
  if (total < 1024 * 1024 * 1024) return `${(total / 1024 / 1024).toFixed(1)} MB`;
  return `${(total / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export function swapDirection(form: LinkType): LinkType {
  return {
    ...form,
    srcType: form.dstType,
    dstType: form.srcType,
  };
}

/** 只读取 API 明确提供的来源维度；缺失维度不是 0。 */
export function getLinkUsageDimension(
  usage: LinkUsageMetric | null,
  dimension: LinkUsageDimension,
): number | null {
  const sources = usage?.sources;
  if (!sources || typeof sources !== "object") return null;
  const normalized = new Map(
    Object.entries(sources).map(([key, value]) => [
      key.trim().toLowerCase().replace(/[\s-]+/g, "_"),
      value,
    ]),
  );
  for (const alias of LINK_USAGE_SOURCE_ALIASES[dimension]) {
    if (!normalized.has(alias)) continue;
    const value = normalized.get(alias);
    return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
  }
  return null;
}

/** API 缺字段时填默认，保证可视化与 CRUD 表单可降级。 */
export function normalizeLinkType(row: Partial<LinkType> & { id?: string }): LinkType {
  const base = emptyForm(row.id || "");
  return {
    ...base,
    ...row,
    id: row.id ?? base.id,
    name: row.name ?? base.name,
    srcType: (row.srcType && String(row.srcType).trim()) || base.srcType,
    dstType: (row.dstType && String(row.dstType).trim()) || base.dstType,
    rel: row.rel ?? base.rel,
    cardinality: (row.cardinality as Cardinality) || base.cardinality,
    joinMethod: (row.joinMethod as JoinMethod) || base.joinMethod,
    expectedEdges: typeof row.expectedEdges === "number" ? row.expectedEdges : base.expectedEdges,
    mdoApproved: Boolean(row.mdoApproved),
    published: Boolean(row.published),
    symmetric: Boolean(row.symmetric),
    description: row.description ?? base.description,
    constraints: Array.isArray(row.constraints) ? row.constraints : [],
  };
}

export function truncateLabel(text: string, max = 18): string {
  const t = (text || "").trim() || "—";
  return t.length > max ? `${t.slice(0, max - 1)}…` : t;
}

export type LinkRelationLayout = {
  width: number;
  height: number;
  src: { x: number; y: number; label: string };
  dst: { x: number; y: number; label: string };
  edge: { x1: number; y1: number; x2: number; y2: number; cardLabel: string; relLabel: string };
  summary: { src: string; dst: string; card: string; join: string; symmetric: boolean; rel: string };
};

/** 双节点 + 边布局（向 ontology-link 视觉稿靠拢，不必 1:1）。 */
export function buildLinkRelationLayout(form: Pick<LinkType, "srcType" | "dstType" | "rel" | "cardinality" | "joinMethod" | "symmetric">): LinkRelationLayout {
  const width = 420;
  const height = 120;
  const y = height / 2;
  const srcX = 70;
  const dstX = 350;
  const nodeHalf = 44;
  return {
    width,
    height,
    src: { x: srcX, y, label: truncateLabel(form.srcType) },
    dst: { x: dstX, y, label: truncateLabel(form.dstType) },
    edge: {
      x1: srcX + nodeHalf,
      y1: y,
      x2: dstX - nodeHalf,
      y2: y,
      cardLabel: cardinalityLabel(form.cardinality),
      relLabel: truncateLabel(form.rel || "link", 16),
    },
    summary: {
      src: form.srcType || "—",
      dst: form.dstType || "—",
      card: cardinalityLabel(form.cardinality),
      join: joinMethodLabel(form.joinMethod),
      symmetric: Boolean(form.symmetric),
      rel: form.rel || "link",
    },
  };
}

/* ────────────── Viz ────────────── */

function LinkRelationViz({ form }: { form: LinkType }) {
  let layout: LinkRelationLayout;
  try {
    layout = buildLinkRelationLayout(form);
  } catch {
    return (
      <div className="w4-c8a-viz-fallback" aria-label="link relation fallback">
        <code>{form.srcType || "—"}</code>
        <span> → </span>
        <code>{form.dstType || "—"}</code>
        <span className="w4-c8a-badge">{cardinalityLabel(form.cardinality)}</span>
      </div>
    );
  }
  const midX = (layout.edge.x1 + layout.edge.x2) / 2;
  const midY = layout.edge.y1;
  return (
    <div className="w4-c8a-viz" aria-label="link relation graph">
      <svg
        className="w4-c8a-svg"
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        role="img"
        aria-label={`${layout.summary.src} ${layout.summary.card} ${layout.summary.dst}`}
      >
        <defs>
          <marker id="w4c8a-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" className="w4-c8a-arrow" />
          </marker>
        </defs>
        <line
          className="w4-c8a-edge"
          x1={layout.edge.x1}
          y1={layout.edge.y1}
          x2={layout.edge.x2}
          y2={layout.edge.y2}
          markerEnd="url(#w4c8a-arrow)"
        />
        <rect
          className="w4-c8a-card-pill"
          x={midX - 22}
          y={midY - 22}
          width={44}
          height={18}
          rx={3}
        />
        <text className="w4-c8a-card-text" x={midX} y={midY - 10} textAnchor="middle" dominantBaseline="central">
          {layout.edge.cardLabel}
        </text>
        <text className="w4-c8a-rel-text" x={midX} y={midY + 16} textAnchor="middle">
          {layout.edge.relLabel}
        </text>
        <g transform={`translate(${layout.src.x}, ${layout.src.y})`}>
          <rect className="w4-c8a-node is-src" x={-44} y={-16} width={88} height={32} rx={4} />
          <text className="w4-c8a-node-label" textAnchor="middle" dominantBaseline="central">
            {layout.src.label}
          </text>
        </g>
        <g transform={`translate(${layout.dst.x}, ${layout.dst.y})`}>
          <rect className="w4-c8a-node is-dst" x={-44} y={-16} width={88} height={32} rx={4} />
          <text className="w4-c8a-node-label" textAnchor="middle" dominantBaseline="central">
            {layout.dst.label}
          </text>
        </g>
      </svg>
      <div className="w4-c8a-summary">
        <code>{layout.summary.src}</code>
        <span className="w4-c8a-badge">{layout.summary.card}</span>
        <code>{layout.summary.dst}</code>
        <span className="w4-c8a-muted">· {layout.summary.join}</span>
        {layout.summary.symmetric && <span className="w4-c8a-badge is-amber">对称</span>}
      </div>
    </div>
  );
}

/* ────────────── Component ────────────── */

export function LinkTypeEditorPage() {
  const { linkId = "new" } = useParams();
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const isNew = linkId === "new";
  const [form, setForm] = useState<LinkType>(() => emptyForm(isNew ? "" : linkId));
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [activeSection, setActiveSection] = useState<string>("overview");
  const [usage, setUsage] = useState<LinkUsageMetric | null>(null);
  const [usageLoading, setUsageLoading] = useState(false);
  const [usageErr, setUsageErr] = useState("");
  const usageRequestRef = useRef(0);

  const loadUsage = useCallback(async () => {
    if (isNew) return;
    const requestId = ++usageRequestRef.current;
    setUsageLoading(true);
    setUsageErr("");
    try {
      const next = await apiGet<LinkUsageMetric>(
        `/v1/ontology/usage/link-types/${encodeURIComponent(linkId)}`,
      );
      if (requestId === usageRequestRef.current) setUsage(next);
    } catch (e) {
      if (requestId === usageRequestRef.current) {
        setUsage(null);
        setUsageErr(String((e as Error).message || e));
      }
    } finally {
      if (requestId === usageRequestRef.current) setUsageLoading(false);
    }
  }, [isNew, linkId]);

  useEffect(() => {
    setUsage(null);
    setUsageErr("");
    if (activeSection === "usage" && !isNew) void loadUsage();
  }, [activeSection, isNew, linkId, loadUsage]);

  useEffect(() => {
    if (isNew) {
      setForm(emptyForm(""));
      const src = sp.get("src") || "WorkOrder";
      const dst = sp.get("dst") || src;
      setForm((f) => ({ ...f, srcType: src, dstType: dst }));
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const row = await apiGet<LinkType>(`/v1/ontology/link-types/${encodeURIComponent(linkId)}`);
        if (!cancelled) setForm(normalizeLinkType(row));
      } catch (e) {
        if (!cancelled) setErr(String((e as Error).message || e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [linkId, isNew, sp]);

  function patch<K extends keyof LinkType>(key: K, value: LinkType[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function save() {
    setBusy(true);
    setMsg("");
    setErr("");
    try {
      const errors = validateLinkType(form);
      if (errors.length > 0) throw new Error(errors.join("; "));
      const scaleCheck = checkScaleWarning(form);
      if (scaleCheck.warn) throw new Error(scaleCheck.message);
      const body = { ...form, id: form.id.trim(), name: form.name.trim() };
      if (isNew) {
        await apiPost("/v1/ontology/link-types", body);
        setMsg(`已创建 ${form.id}`);
        navigate(`/ontology/link-types/${encodeURIComponent(form.id)}`, { replace: true });
      } else {
        await apiPut(`/v1/ontology/link-types/${encodeURIComponent(form.id)}`, body);
        setMsg("已保存");
      }
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (isNew) return;
    if (!window.confirm(`删除 Link Type ${form.id}？不级联删除 graph_edge。`)) return;
    setBusy(true);
    setErr("");
    try {
      await apiDelete(`/v1/ontology/link-types/${encodeURIComponent(form.id)}`);
      navigate("/ontology");
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  const scaleWarn = checkScaleWarning(form);
  const storageEst = estimateStorage(form);

  return (
    <S2Chrome
      title={isNew ? "新建 Link Type" : `Link Type · ${form.id}`}
      lede="元数据编辑 · 规模红线需 MDO 批准 · 不级联实例边"
    >
      <div className="ont-page">
        <BpToolbar>
          <Link to="/ontology" className="btn-nav">
            ← 发现
          </Link>
          <button type="button" className="btn-primary" disabled={busy} onClick={() => void save()}>
            {busy ? "保存中…" : isNew ? "创建" : "保存"}
          </button>
          {!isNew && (
            <button type="button" className="btn" disabled={busy} onClick={() => void remove()}>
              删除
            </button>
          )}
        </BpToolbar>
        {msg && <p className="bp-prop-ok">{msg}</p>}
        {err && <p className="error">{err}</p>}
        {scaleWarn.warn && <BpBanner tone="warn">{scaleWarn.message}</BpBanner>}

        <div style={linkStyles.layout}>
          {/* 左侧导航 */}
          <aside style={linkStyles.sideNav}>
            <Link to="/ontology" style={linkStyles.backLink}>
              ← Home
            </Link>
            <div style={linkStyles.typeNameRow}>
              <span style={linkStyles.typeIcon}>🔗</span>
              <span style={linkStyles.typeName}>{form.name || form.id || "新建 Link"}</span>
            </div>
            <div style={linkStyles.navSection}>
              {LINK_NAV_SECTIONS.map((sec) => (
                <button
                  key={sec.key}
                  type="button"
                  style={activeSection === sec.key ? linkStyles.navItemActive : linkStyles.navItem}
                  onClick={() => setActiveSection(sec.key)}
                >
                  {sec.label}
                </button>
              ))}
            </div>
          </aside>

          {/* 右侧主区 */}
          <section style={linkStyles.main}>
            {/* 信息卡 */}
            <div style={linkStyles.infoCard}>
              <div style={linkStyles.infoRow}>
                <div style={linkStyles.infoKey}>Description</div>
                <div style={linkStyles.infoValue}>{form.description || "（无描述）"}</div>
              </div>
              <div style={linkStyles.infoRow}>
                <div style={linkStyles.infoKey}>Cardinality</div>
                <div style={linkStyles.infoValue}>
                  {cardinalityIcon(form.cardinality)} {cardinalityLabel(form.cardinality)} ·{" "}
                  {joinMethodLabel(form.joinMethod)}
                </div>
              </div>
              <div style={linkStyles.infoRow}>
                <div style={linkStyles.infoKey}>连接路径</div>
                <div style={linkStyles.infoValue}>
                  <code style={linkStyles.monoText}>{form.srcType}</code>
                  {" → "}
                  <code style={linkStyles.monoText}>{form.dstType}</code>
                  {form.symmetric && (
                    <span style={linkStyles.symmetricBadge}>对称</span>
                  )}
                </div>
              </div>
              <div style={linkStyles.infoRow}>
                <div style={linkStyles.infoKey}>RID</div>
                <div style={linkStyles.infoValue}>
                  <code style={linkStyles.monoText}>
                    {form.id ? `ri.ontology.main.link-type.${form.id}` : "（新建后生成）"}
                  </code>
                </div>
              </div>
              <div style={linkStyles.infoRow}>
                <div style={linkStyles.infoKey}>预估存储</div>
                <div style={linkStyles.infoValue}>{storageEst}</div>
              </div>
            </div>

            {/* Configuration: Join method 可视化 + 类型选择器 */}
            {activeSection === "overview" && (
              <div style={linkStyles.sectionCard}>
                <h3 style={linkStyles.sectionTitle}>Configuration</h3>

                {/* 基本表单 */}
                <div className="ont-form-grid" style={{ marginTop: "0.5rem" }}>
                  <label className="ont-form-field">
                    <span>id</span>
                    <input
                      className="aos-input"
                      value={form.id}
                      disabled={!isNew}
                      onChange={(e) => patch("id", e.target.value)}
                      placeholder="lt-related-to"
                    />
                  </label>
                  <label className="ont-form-field">
                    <span>name</span>
                    <input className="aos-input" value={form.name} onChange={(e) => patch("name", e.target.value)} />
                  </label>
                  <label className="ont-form-field">
                    <span>rel</span>
                    <input className="aos-input" value={form.rel} onChange={(e) => patch("rel", e.target.value)} />
                  </label>
                  <label className="ont-form-field">
                    <span>cardinality</span>
                    <select
                      className="aos-input"
                      value={form.cardinality}
                      onChange={(e) => patch("cardinality", e.target.value as Cardinality)}
                    >
                      {CARDINALITIES.map((c) => (
                        <option key={c.value} value={c.value}>
                          {c.label} ({c.value})
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                {/* Join method 卡片 */}
                <div className="w4-c8a-join" style={{ marginTop: "0.75rem" }}>
                  <label style={linkStyles.propLabel}>Join method</label>
                  <div className="w4-c8a-join-cards" role="listbox" aria-label="join method">
                    {JOIN_METHODS.map((j) => (
                      <button
                        key={j.value}
                        type="button"
                        role="option"
                        aria-selected={form.joinMethod === j.value}
                        className={
                          form.joinMethod === j.value
                            ? "w4-c8a-join-card is-selected"
                            : "w4-c8a-join-card"
                        }
                        onClick={() => patch("joinMethod", j.value)}
                      >
                        <span className="w4-c8a-join-name">{j.label}</span>
                        <span className="w4-c8a-join-desc">{j.description}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* SVG 关系可视化 */}
                <div className="w4-c8a-viz-wrap">
                  <div className="w4-c8a-viz-head">
                    <span>关系图</span>
                    <button
                      type="button"
                      className="w4-c8a-swap"
                      onClick={() => setForm(swapDirection(form))}
                      title="交换方向"
                    >
                      ⇄ 交换
                    </button>
                  </div>
                  <LinkRelationViz form={form} />
                </div>

                {/* 类型A/B 选择器 */}
                <div style={linkStyles.typeSelectorRow}>
                  <label className="ont-form-field">
                    <span>srcType（源类型 A）</span>
                    <input className="aos-input" value={form.srcType} onChange={(e) => patch("srcType", e.target.value)} />
                  </label>
                  <label className="ont-form-field">
                    <span>dstType（目标类型 B）</span>
                    <input className="aos-input" value={form.dstType} onChange={(e) => patch("dstType", e.target.value)} />
                  </label>
                </div>

                <label className="ont-form-field ont-form-span">
                  <span>description</span>
                  <input
                    className="aos-input"
                    value={form.description}
                    onChange={(e) => patch("description", e.target.value)}
                  />
                </label>
              </div>
            )}

            {activeSection === "security" && (
              <div style={linkStyles.sectionCard}>
                <h3 style={linkStyles.sectionTitle}>Security & Scale</h3>
                <label className="ont-form-field">
                  <span>expectedEdges</span>
                  <input
                    className="aos-input"
                    type="number"
                    value={form.expectedEdges}
                    onChange={(e) => patch("expectedEdges", Number(e.target.value) || 0)}
                  />
                </label>
                <div style={{ display: "flex", gap: 16, marginTop: 12, flexWrap: "wrap" }}>
                  <label className="ont-form-check">
                    <input
                      type="checkbox"
                      checked={form.mdoApproved}
                      onChange={(e) => patch("mdoApproved", e.target.checked)}
                    />
                    MDO 批准（大规模边）
                  </label>
                  <label className="ont-form-check">
                    <input
                      type="checkbox"
                      checked={form.published}
                      onChange={(e) => patch("published", e.target.checked)}
                    />
                    已发布
                  </label>
                  <label className="ont-form-check">
                    <input
                      type="checkbox"
                      checked={form.symmetric}
                      onChange={(e) => patch("symmetric", e.target.checked)}
                    />
                    对称关系（自引用）
                  </label>
                </div>
                {scaleWarn.warn && (
                  <div style={linkStyles.warnBox}>
                    <strong>⚠ 规模红线警告</strong>
                    <p style={{ fontSize: "0.7rem", marginTop: "2px" }}>{scaleWarn.message}</p>
                  </div>
                )}
              </div>
            )}

            {activeSection === "datasources" && (
              <div style={linkStyles.sectionCard}>
                <h3 style={linkStyles.sectionTitle}>Datasources</h3>
                <p style={linkStyles.mutedText}>
                  关联关系的数据来源：可选择外键字段、junction table 或计算表达式。
                </p>
                <div style={linkStyles.dsRow}>
                  <span style={linkStyles.dsLabel}>Join method:</span>
                  <code style={linkStyles.monoText}>{joinMethodLabel(form.joinMethod)}</code>
                </div>
                <div style={linkStyles.dsRow}>
                  <span style={linkStyles.dsLabel}>预估存储:</span>
                  <code style={linkStyles.monoText}>{storageEst}</code>
                </div>
              </div>
            )}

            {activeSection === "usage" && (
              <div style={linkStyles.sectionCard}>
                <h3 style={linkStyles.sectionTitle}>Usage</h3>
                <p style={linkStyles.mutedText}>
                  查看 Link Type 在 Workshop、AIP Logic 和管道中的使用情况。
                </p>
                <BpToolbar>
                  <button
                    type="button"
                    className="btn-nav"
                    disabled={isNew || usageLoading}
                    onClick={() => void loadUsage()}
                  >
                    {usageLoading ? "刷新中…" : "刷新 Usage"}
                  </button>
                  <span className="muted">
                    {isNew
                      ? "创建后可读取真实 Usage"
                      : usage
                        ? `API 统计窗口 ${usage.window_days ?? "—"} 天`
                        : "尚无可确认的 Usage 数据"}
                  </span>
                </BpToolbar>
                {usageErr && <BpBanner tone="warn">Usage 读取失败：{usageErr}</BpBanner>}
                <div style={linkStyles.usageRow}>
                  <div style={linkStyles.usageBox} data-testid="link-usage-workshop">
                    <div style={linkStyles.usageNum}>
                      {getLinkUsageDimension(usage, "workshop") ?? "—"}
                    </div>
                    <div style={linkStyles.usageLabel}>Workshop 应用</div>
                    {getLinkUsageDimension(usage, "workshop") == null && (
                      <div style={linkStyles.usageHint}>接口未提供</div>
                    )}
                  </div>
                  <div style={linkStyles.usageBox} data-testid="link-usage-aip">
                    <div style={linkStyles.usageNum}>
                      {getLinkUsageDimension(usage, "aip") ?? "—"}
                    </div>
                    <div style={linkStyles.usageLabel}>AIP 逻辑节点</div>
                    {getLinkUsageDimension(usage, "aip") == null && (
                      <div style={linkStyles.usageHint}>接口未提供</div>
                    )}
                  </div>
                  <div style={linkStyles.usageBox} data-testid="link-usage-pipeline">
                    <div style={linkStyles.usageNum}>
                      {getLinkUsageDimension(usage, "pipeline") ?? "—"}
                    </div>
                    <div style={linkStyles.usageLabel}>管道引用</div>
                    {getLinkUsageDimension(usage, "pipeline") == null && (
                      <div style={linkStyles.usageHint}>接口未提供</div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </S2Chrome>
  );
}

/* ────────────── Styles ────────────── */

const linkStyles: Record<string, React.CSSProperties> = {
  layout: { display: "flex", gap: "0.75rem", minHeight: "60vh" },
  sideNav: { width: 200, flexShrink: 0, borderRight: "1px solid var(--aos-border)", padding: "0.5rem" },
  backLink: { display: "flex", alignItems: "center", gap: "4px", fontSize: "0.75rem", color: "var(--aos-text-secondary)", textDecoration: "none", marginBottom: "0.5rem" },
  typeNameRow: { display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" },
  typeIcon: { fontSize: "1.1rem" },
  typeName: { fontWeight: 600, fontSize: "0.85rem", color: "var(--aos-text)" },
  navSection: { display: "flex", flexDirection: "column" as const, gap: "1px" },
  navItem: { display: "flex", alignItems: "center", gap: "6px", padding: "5px 8px", fontSize: "0.75rem", border: "none", background: "transparent", color: "var(--aos-text-secondary)", cursor: "pointer", borderRadius: "4px", textAlign: "left" as const },
  navItemActive: { display: "flex", alignItems: "center", gap: "6px", padding: "5px 8px", fontSize: "0.75rem", border: "none", background: "var(--aos-accent-light)", color: "var(--aos-accent)", cursor: "pointer", borderRadius: "4px", fontWeight: 600, textAlign: "left" as const },
  main: { flex: 1, minWidth: 0 },
  infoCard: { border: "1px solid var(--aos-border)", borderRadius: "2px", background: "var(--aos-surface)", marginBottom: "0.75rem" },
  infoRow: { display: "flex", padding: "0.4rem 0.75rem", borderBottom: "1px solid var(--aos-border)", gap: "0.5rem", alignItems: "center" },
  infoKey: { width: 120, fontSize: "0.7rem", fontWeight: 600, color: "var(--aos-text-secondary)", flexShrink: 0 },
  infoValue: { flex: 1, fontSize: "0.75rem", color: "var(--aos-text-secondary)", display: "flex", alignItems: "center", gap: "4px", flexWrap: "wrap" },
  monoText: { fontFamily: "ui-monospace, monospace", fontSize: "0.72rem", color: "var(--aos-accent-hover)" },
  symmetricBadge: { padding: "1px 4px", borderRadius: "3px", background: "var(--aos-amber-bg)", color: "var(--aos-amber-text)", fontSize: "0.6rem" },
  sectionCard: { border: "1px solid var(--aos-border)", borderRadius: "2px", background: "var(--aos-surface)", padding: "0.75rem" },
  sectionTitle: { fontSize: "0.85rem", fontWeight: 600, color: "var(--aos-text)", marginBottom: "0.5rem" },
  mutedText: { fontSize: "0.75rem", color: "var(--aos-text-tertiary)" },
  joinVizRow: { display: "flex", alignItems: "flex-start", gap: "1rem", marginTop: "0.75rem", flexWrap: "wrap" },
  joinVizCol: { flex: "1 1 200px" },
  propLabel: { display: "block", fontSize: "0.7rem", fontWeight: 500, color: "var(--aos-text-secondary)", marginBottom: "2px" },
  joinDesc: { fontSize: "0.65rem", color: "var(--aos-text-tertiary)", marginTop: "4px" },
  joinVizDiagram: { display: "flex", alignItems: "center", gap: "0.5rem", flex: "1 1 300px" },
  typeBox: { padding: "6px 12px", border: "1px solid var(--aos-accent-border)", borderRadius: "2px", background: "var(--aos-accent-light)", fontSize: "0.7rem", fontWeight: 600, color: "var(--aos-accent-hover)" },
  arrowRow: { display: "flex", alignItems: "center", gap: "2px" },
  arrowIcon: { fontSize: "0.65rem", fontWeight: 600, color: "var(--aos-text-secondary)" },
  arrowLine: { width: 20, height: 2, background: "var(--aos-border-strong)" },
  swapBtn: { padding: "4px 10px", fontSize: "0.7rem", border: "1px solid var(--aos-border-strong)", borderRadius: "2px", background: "var(--aos-surface)", color: "var(--aos-text-secondary)", cursor: "pointer", flexShrink: 0 },
  typeSelectorRow: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", marginTop: "0.75rem" },
  warnBox: { marginTop: "0.75rem", padding: "0.5rem 0.75rem", border: "1px solid var(--aos-amber-border)", borderRadius: "2px", background: "var(--aos-amber-bg)" },
  dsRow: { display: "flex", alignItems: "center", gap: "0.5rem", padding: "4px 0", fontSize: "0.75rem" },
  dsLabel: { fontWeight: 500, color: "var(--aos-text-secondary)", width: 120 },
  usageRow: { display: "flex", gap: "0.75rem", marginTop: "0.5rem" },
  usageBox: { flex: 1, textAlign: "center" as const, padding: "1rem", border: "1px solid var(--aos-border)", borderRadius: "2px", background: "var(--aos-surface-hover)" },
  usageNum: { fontSize: "1.5rem", fontWeight: 700, color: "var(--aos-accent)" },
  usageLabel: { fontSize: "0.7rem", color: "var(--aos-text-secondary)", marginTop: "4px" },
  usageHint: { fontSize: "0.65rem", color: "var(--aos-text-tertiary)", marginTop: "2px" },
};
