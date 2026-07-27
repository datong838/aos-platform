import { useEffect, useState } from "react";
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
        if (!cancelled) setForm(row);
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

                {/* Join method 可视化 */}
                <div style={linkStyles.joinVizRow}>
                  <div style={linkStyles.joinVizCol}>
                    <label style={linkStyles.propLabel}>Join method</label>
                    <select
                      className="aos-input"
                      style={{ marginTop: "2px" }}
                      value={form.joinMethod}
                      onChange={(e) => patch("joinMethod", e.target.value as JoinMethod)}
                    >
                      {JOIN_METHODS.map((j) => (
                        <option key={j.value} value={j.value}>
                          {j.label}
                        </option>
                      ))}
                    </select>
                    <p style={linkStyles.joinDesc}>{joinMethodDescription(form.joinMethod)}</p>
                  </div>
                  {/* 可视化图示 */}
                  <div style={linkStyles.joinVizDiagram}>
                    <div style={linkStyles.typeBox}>{form.srcType}</div>
                    <div style={linkStyles.arrowRow}>
                      <span style={linkStyles.arrowIcon}>{cardinalityIcon(form.cardinality)}</span>
                      <div style={linkStyles.arrowLine} />
                      <span style={linkStyles.arrowIcon}>{joinMethodLabel(form.joinMethod)}</span>
                      <div style={linkStyles.arrowLine} />
                      <span style={linkStyles.arrowIcon}>{form.cardinality.startsWith("MANY") ? "◊" : "○"}</span>
                    </div>
                    <div style={linkStyles.typeBox}>{form.dstType}</div>
                  </div>
                  <button
                    type="button"
                    style={linkStyles.swapBtn}
                    onClick={() => setForm(swapDirection(form))}
                    title="交换方向"
                  >
                    ⇄ 交换
                  </button>
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
                <div style={linkStyles.usageRow}>
                  <div style={linkStyles.usageBox}>
                    <div style={linkStyles.usageNum}>0</div>
                    <div style={linkStyles.usageLabel}>Workshop 应用</div>
                  </div>
                  <div style={linkStyles.usageBox}>
                    <div style={linkStyles.usageNum}>0</div>
                    <div style={linkStyles.usageLabel}>AIP 逻辑节点</div>
                  </div>
                  <div style={linkStyles.usageBox}>
                    <div style={linkStyles.usageNum}>0</div>
                    <div style={linkStyles.usageLabel}>管道引用</div>
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
};
