import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPut } from "../../api/client";
import { getOntologyClient } from "../../api/ontologyClient";
import {
  BpBanner,
  BpMetricGrid,
  BpPropGrid,
  BpScoreGrid,
  BpTable,
  BpTabs,
} from "./blueprintUi";

type PropDef = { name: string; type?: string };
type LinkRow = { id: string; name?: string; srcType?: string; dstType?: string; rel?: string };
type ActionRow = { id: string; name: string; objectType?: string };
type ModuleRow = { id: string; name: string; objectType?: string };

/** W3-C2 · 详情 API / 列表派生元数据 */
export type OtDetailMeta = {
  rid?: string;
  apiName?: string;
  primaryKey?: string;
  titleKey?: string;
  displayName?: string;
  pluralName?: string;
  backingDataset?: string;
  syncStrategy?: string;
  storageType?: string;
  createdBy?: string;
  visibility?: string;
};

export type OtMetaKvItem = { label: string; value: string; tone?: "ok" | "warn" | "muted" };

export type LinkGraphNode = { id: string; label: string; role: "center" | "neighbor"; x: number; y: number };
export type LinkGraphEdge = {
  id: string;
  from: string;
  to: string;
  label: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};
export type LinkGraphLayout = { width: number; height: number; nodes: LinkGraphNode[]; edges: LinkGraphEdge[] };

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "properties", label: "Properties" },
  { id: "actions", label: "Action types" },
  { id: "links", label: "Link type graph" },
  { id: "dependents", label: "Dependents" },
  { id: "data", label: "Data" },
  { id: "usage", label: "Usage" },
];

function branchAllowsOverlayWrite(branchId: string, branchReadonly?: boolean): boolean {
  if (branchReadonly) return false;
  if (!branchId || branchId === "main" || branchId === "master") return false;
  return true;
}

function propNames(properties?: PropDef[]): string[] {
  return (properties || []).map((p) => p.name.trim()).filter(Boolean);
}

/** 从列表字段派生元数据（详情 API 失败时降级） */
export function deriveOtDetailMeta(
  typeId: string,
  typeName: string,
  properties?: PropDef[],
): OtDetailMeta {
  const names = propNames(properties);
  const primaryKey = names[0] || "id";
  const titleHit = names.find((n) => /^(title|name|display_name|label)$/i.test(n));
  const titleKey = titleHit || (names[1] || primaryKey);
  const display = (typeName || typeId).trim() || typeId;
  const plural = display.endsWith("s") ? display : `${display}s`;
  return {
    rid: `ri.ontology.main.object-type.${typeId.toLowerCase()}`,
    apiName: typeId,
    primaryKey,
    titleKey,
    displayName: display,
    pluralName: plural,
    backingDataset: `ds/${typeId.toLowerCase()}`,
    syncStrategy: "incremental",
    storageType: "object_storage",
    createdBy: "system",
    visibility: "org",
  };
}

/** 向视觉稿 KV 靠拢（约 12 项，含分支） */
export function buildOtMetaKvItems(input: {
  typeId: string;
  typeName: string;
  branchId: string;
  properties?: PropDef[];
  funnelStage?: string;
  meta?: OtDetailMeta | null;
}): OtMetaKvItem[] {
  const base = deriveOtDetailMeta(input.typeId, input.typeName, input.properties);
  const m = { ...base, ...(input.meta || {}) };
  const funnelTone = input.funnelStage && /live|index|done/i.test(input.funnelStage) ? "ok" : "warn";
  return [
    { label: "RID", value: m.rid || base.rid! },
    { label: "API 名", value: m.apiName || input.typeId },
    { label: "PK", value: m.primaryKey || "id" },
    { label: "TitleKey", value: m.titleKey || "id" },
    { label: "显示名", value: m.displayName || input.typeName },
    { label: "Plural", value: m.pluralName || `${input.typeName}s` },
    { label: "BackingDataset", value: m.backingDataset || `ds/${input.typeId.toLowerCase()}` },
    { label: "Sync 策略", value: m.syncStrategy || "incremental" },
    { label: "存储类型", value: m.storageType || "object_storage" },
    { label: "创建人", value: m.createdBy || "system" },
    { label: "分支", value: input.branchId },
    {
      label: "可见性",
      value: m.visibility || "org",
    },
    {
      label: "管道",
      value: input.funnelStage || "未配置",
      tone: funnelTone === "ok" ? "ok" : "warn",
    },
    { label: "Properties", value: String((input.properties || []).length) },
  ];
}

/** 简单环形布局：中心 OT + 邻居节点/边 */
export function buildLinkGraphLayout(
  typeId: string,
  links: LinkRow[],
  opts?: { width?: number; height?: number },
): LinkGraphLayout {
  const width = opts?.width ?? 420;
  const height = opts?.height ?? 220;
  const cx = width / 2;
  const cy = height / 2;
  const nodes: LinkGraphNode[] = [{ id: typeId, label: typeId, role: "center", x: cx, y: cy }];
  const edges: LinkGraphEdge[] = [];
  if (links.length === 0) return { width, height, nodes, edges };

  const neighborIds: string[] = [];
  for (const l of links) {
    const other = l.srcType === typeId ? l.dstType : l.srcType;
    if (other && other !== typeId && !neighborIds.includes(other)) neighborIds.push(other);
  }
  const radius = Math.min(width, height) * 0.36;
  neighborIds.forEach((nid, i) => {
    const angle = (Math.PI * 2 * i) / Math.max(neighborIds.length, 1) - Math.PI / 2;
    nodes.push({
      id: nid,
      label: nid,
      role: "neighbor",
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    });
  });
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  for (const l of links) {
    const from = l.srcType || typeId;
    const to = l.dstType || typeId;
    const a = byId[from];
    const b = byId[to];
    if (!a || !b) continue;
    edges.push({
      id: l.id,
      from,
      to,
      label: l.rel || "link",
      x1: a.x,
      y1: a.y,
      x2: b.x,
      y2: b.y,
    });
  }
  return { width, height, nodes, edges };
}

function LinkTypeGraphViz({
  typeId,
  links,
}: {
  typeId: string;
  links: LinkRow[];
}) {
  const layout = useMemo(() => buildLinkGraphLayout(typeId, links), [typeId, links]);
  if (links.length === 0) {
    return <p className="muted w3-c2-link-empty">暂无 Link Type</p>;
  }
  return (
    <div className="w3-c2-link-graph" aria-label="link type graph">
      <svg
        className="w3-c2-link-svg"
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        role="img"
        aria-label={`${typeId} link graph`}
      >
        {layout.edges.map((e) => {
          const mx = (e.x1 + e.x2) / 2;
          const my = (e.y1 + e.y2) / 2;
          return (
            <g key={e.id}>
              <line className="w3-c2-link-edge" x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2} markerEnd="url(#w3c2-arrow)" />
              <text className="w3-c2-link-edge-label" x={mx} y={my - 6} textAnchor="middle">
                {e.label}
              </text>
            </g>
          );
        })}
        <defs>
          <marker id="w3c2-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" className="w3-c2-link-arrow" />
          </marker>
        </defs>
        {layout.nodes.map((n) => (
          <g key={n.id} transform={`translate(${n.x}, ${n.y})`}>
            <rect
              className={n.role === "center" ? "w3-c2-link-node is-center" : "w3-c2-link-node"}
              x={-44}
              y={-14}
              width={88}
              height={28}
              rx={4}
            />
            <text className="w3-c2-link-node-label" textAnchor="middle" dominantBaseline="central">
              {n.label}
            </text>
          </g>
        ))}
      </svg>
      <ul className="w3-c2-link-list">
        {links.map((l) => (
          <li key={l.id}>
            <code>{l.srcType || "—"}</code>
            <span className="w3-c2-link-rel">{l.rel || "link"}</span>
            <code>{l.dstType || "—"}</code>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ObjectTypeDetailPanel({
  typeId,
  typeName,
  description,
  published,
  properties,
  branchId,
  branchReadonly,
  instanceCount,
  funnelStage,
  objects,
  onOpenInstance,
  detail,
  neighbors,
  onBranchSaved,
  onMetaSaved,
}: {
  typeId: string;
  typeName: string;
  description?: string;
  published?: boolean;
  properties?: PropDef[];
  branchId: string;
  branchReadonly?: boolean;
  instanceCount: number;
  funnelStage?: string;
  objects: Record<string, unknown>[];
  onOpenInstance: (id: string) => void;
  detail: Record<string, unknown> | null;
  neighbors: { id?: string; type?: string; rel?: string }[];
  onBranchSaved?: () => void;
  onMetaSaved?: () => void;
}) {
  const [tab, setTab] = useState("overview");
  const [links, setLinks] = useState<LinkRow[]>([]);
  const [actions, setActions] = useState<ActionRow[]>([]);
  const [modules, setModules] = useState<ModuleRow[]>([]);
  const [metricsTotal, setMetricsTotal] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editStatus, setEditStatus] = useState("");
  const [editBusy, setEditBusy] = useState(false);
  const [editMsg, setEditMsg] = useState("");
  const [editErr, setEditErr] = useState("");
  const [metaName, setMetaName] = useState(typeName);
  const [metaDesc, setMetaDesc] = useState(description || "");
  const [metaPublish, setMetaPublish] = useState(!!published);
  const [draftProps, setDraftProps] = useState<PropDef[]>(properties || []);
  const [metaBusy, setMetaBusy] = useState(false);
  const [metaMsg, setMetaMsg] = useState("");
  const [metaErr, setMetaErr] = useState("");
  const [otMeta, setOtMeta] = useState<OtDetailMeta | null>(null);
  const canEditBranch = branchAllowsOverlayWrite(branchId, branchReadonly);

  useEffect(() => {
    setTab("overview");
  }, [typeId]);

  useEffect(() => {
    setMetaName(typeName);
    setMetaDesc(description || "");
    setMetaPublish(!!published);
    setDraftProps(properties || []);
    setMetaMsg("");
    setMetaErr("");
  }, [typeId, typeName, description, published, properties]);

  useEffect(() => {
    if (!detail) {
      setEditTitle("");
      setEditStatus("");
      setEditMsg("");
      setEditErr("");
      return;
    }
    setEditTitle(String(detail.title ?? ""));
    setEditStatus(String(detail.status ?? ""));
    setEditMsg("");
    setEditErr("");
  }, [detail]);

  async function saveMeta() {
    setMetaBusy(true);
    setMetaMsg("");
    setMetaErr("");
    try {
      const cleaned = draftProps
        .map((p) => ({ name: p.name.trim(), type: (p.type || "string").trim() || "string" }))
        .filter((p) => p.name);
      await apiPut(`/v1/ontology/object-types/${encodeURIComponent(typeId)}`, {
        name: metaName.trim() || typeId,
        description: metaDesc,
        properties: cleaned,
        publish: metaPublish,
      });
      setMetaMsg("已保存 Object Type 元数据");
      onMetaSaved?.();
    } catch (e) {
      setMetaErr(String((e as Error).message || e));
    } finally {
      setMetaBusy(false);
    }
  }

  async function saveBranchOverlay() {
    if (!detail?.id || !canEditBranch) return;
    setEditBusy(true);
    setEditMsg("");
    setEditErr("");
    try {
      const props: Record<string, unknown> = { ...detail };
      delete props.id;
      delete props.type;
      delete props.branch;
      props.title = editTitle;
      props.status = editStatus;
      await getOntologyClient().putObject(
        typeId,
        String(detail.id),
        { props, op: "upsert" },
        { branch: branchId },
      );
      setEditMsg(`已写入分支 overlay · ${branchId}`);
      onBranchSaved?.();
    } catch (e) {
      setEditErr(String((e as Error).message || e));
    } finally {
      setEditBusy(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [lt, at, mod, met] = await Promise.all([
          apiGet<{ items: LinkRow[] }>("/v1/ontology/link-types"),
          apiGet<{ items: ActionRow[] }>("/v1/actions/types"),
          apiGet<{ items: ModuleRow[] }>("/v1/modules"),
          apiGet<{ totals?: { count?: number } }>("/v1/metrics"),
        ]);
        if (cancelled) return;
        setLinks(
          (lt.items || []).filter(
            (l) => l.srcType === typeId || l.dstType === typeId,
          ),
        );
        setActions((at.items || []).filter((a) => a.objectType === typeId));
        setModules((mod.items || []).filter((m) => m.objectType === typeId));
        setMetricsTotal(met.totals?.count ?? null);
      } catch {
        if (!cancelled) {
          setLinks([]);
          setActions([]);
          setModules([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [typeId]);

  /* W3-C2 · 详情元数据；失败降级为前端派生 */
  useEffect(() => {
    let cancelled = false;
    setOtMeta(null);
    (async () => {
      try {
        const d = await apiGet<OtDetailMeta & { id?: string }>(
          `/v1/ontology/object-types/${encodeURIComponent(typeId)}`,
        );
        if (cancelled) return;
        setOtMeta({
          rid: d.rid,
          apiName: d.apiName,
          primaryKey: d.primaryKey,
          titleKey: d.titleKey,
          displayName: d.displayName,
          pluralName: d.pluralName,
          backingDataset: d.backingDataset,
          syncStrategy: d.syncStrategy,
          storageType: d.storageType,
          createdBy: d.createdBy,
          visibility: d.visibility,
        });
      } catch {
        if (!cancelled) setOtMeta(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [typeId]);

  const props = draftProps;
  const metaKvItems = useMemo(
    () =>
      buildOtMetaKvItems({
        typeId,
        typeName,
        branchId,
        properties: props,
        funnelStage,
        meta: otMeta,
      }),
    [typeId, typeName, branchId, props, funnelStage, otMeta],
  );
  const detailProps =
    detail &&
    Object.entries(detail)
      .filter(([k]) => !k.startsWith("_"))
      .slice(0, 8)
      .map(([k, v]) => ({ label: k, value: String(v ?? "—") }));

  const funnelTone = funnelStage && /live|index|done/i.test(funnelStage) ? "ok" : "warn";

  return (
    <div className="bp-object-panel" style={{ marginTop: "1rem" }}>
      <div className="bp-object-title">
        {typeName}{" "}
        <span className="muted" style={{ fontSize: "0.75rem", fontWeight: 400 }}>
          ({typeId}) @ {branchId}
        </span>
      </div>

      <BpTabs tabs={TABS} active={tab} onChange={setTab} />

      {tab === "overview" && (
        <div className="ont-overview">
          {/* ① Metadata · 对齐 ontology-object */}
          <section className="ont-meta-card">
            <div className="ont-meta-eyebrow">
              <span>① Metadata</span>
              <span className="muted">· Object type 元数据</span>
            </div>
            <div className="ont-meta-head">
              <div>
                <div className="muted" style={{ fontSize: "0.7rem" }}>
                  显示名
                </div>
                <input
                  className="aos-input ont-meta-title-input"
                  value={metaName}
                  onChange={(e) => setMetaName(e.target.value)}
                  aria-label="object type name"
                />
                <p className="muted" style={{ fontSize: "0.75rem", margin: "0.25rem 0 0" }}>
                  英文名 / API: <code>{typeId}</code>
                </p>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                <span className={`bp-tag bp-tag-${metaPublish ? "ok" : "warn"}`}>
                  {metaPublish ? "已发布" : "草稿"}
                </span>
                <span className={`bp-tag bp-tag-${funnelTone}`}>
                  Funnel: {funnelStage || "未配置"}
                </span>
                <span className="bp-tag">{instanceCount} 实例</span>
              </div>
            </div>
            <label className="ont-form-field" style={{ display: "block", marginTop: 8 }}>
              <span className="muted" style={{ fontSize: "0.7rem" }}>
                描述
              </span>
              <input
                className="aos-input"
                value={metaDesc}
                onChange={(e) => setMetaDesc(e.target.value)}
                placeholder="Object Type 描述"
              />
            </label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 8, alignItems: "center" }}>
              <label className="ont-form-check">
                <input
                  type="checkbox"
                  checked={metaPublish}
                  onChange={(e) => setMetaPublish(e.target.checked)}
                />
                发布（需至少 1 个 property）
              </label>
              <button
                type="button"
                className="btn-primary"
                disabled={metaBusy}
                onClick={() => void saveMeta()}
              >
                {metaBusy ? "保存中…" : "保存元数据"}
              </button>
              <button type="button" className="bp-action-link" onClick={() => setTab("properties")}>
                编辑 Properties →
              </button>
            </div>
            {metaMsg && <p className="bp-prop-ok">{metaMsg}</p>}
            {metaErr && <p className="error">{metaErr}</p>}
            <BpPropGrid items={metaKvItems} />
          </section>

          <div className="ont-overview-grid">
            <div className="ont-ov-card">
              <div className="ont-ov-card-head">
                <h3>
                  <span className="ont-ov-num">②</span> Properties
                </h3>
                <button type="button" className="bp-action-link" onClick={() => setTab("properties")}>
                  查看全部 →
                </button>
              </div>
              <ul className="ont-ov-list">
                {props.slice(0, 4).map((p, i) => (
                  <li key={p.name}>
                    <code>{p.name}</code>
                    <span className="muted">
                      {p.type || "string"}
                      {i === 0 ? " · PK" : ""}
                    </span>
                  </li>
                ))}
                {props.length === 0 && <li className="muted">暂无</li>}
              </ul>
            </div>
            <div className="ont-ov-card">
              <div className="ont-ov-card-head">
                <h3>
                  <span className="ont-ov-num">③</span> Action types
                </h3>
                <button type="button" className="bp-action-link" onClick={() => setTab("actions")}>
                  打开 →
                </button>
              </div>
              <ul className="ont-ov-list">
                {actions.slice(0, 4).map((a) => (
                  <li key={a.id}>
                    <Link to={`/ontology/action-types/${encodeURIComponent(a.id)}`}>· {a.name}</Link>
                  </li>
                ))}
                {actions.length === 0 && <li className="muted">暂无</li>}
              </ul>
            </div>
            <div className="ont-ov-card">
              <div className="ont-ov-card-head">
                <h3>
                  <span className="ont-ov-num">④</span> Link type graph
                </h3>
                <Link
                  to={`/ontology/link-types/${links[0] ? encodeURIComponent(links[0].id) : "new"}?src=${encodeURIComponent(typeId)}`}
                  className="bp-action-link"
                >
                  {links[0] ? "打开编辑器 →" : "新建 Link →"}
                </Link>
              </div>
              <LinkTypeGraphViz typeId={typeId} links={links} />
            </div>
            <div className="ont-ov-card">
              <div className="ont-ov-card-head">
                <h3>
                  <span className="ont-ov-num">⑥</span> Data · Funnel
                </h3>
                <Link to={`/ontology/funnel?type=${encodeURIComponent(typeId)}`} className="bp-action-link">
                  Pipeline →
                </Link>
              </div>
              <p className="muted" style={{ fontSize: "0.8rem", margin: 0 }}>
                {funnelStage ? `Stage: ${funnelStage}` : "未配置 Funnel"}
              </p>
              <button type="button" className="bp-action-link" style={{ marginTop: 8 }} onClick={() => setTab("data")}>
                打开 Data Tab →
              </button>
            </div>
          </div>

          <Link
            to={
              objects[0]?.id
                ? `/ontology/wiki?type=${encodeURIComponent(typeId)}&id=${encodeURIComponent(String(objects[0].id))}`
                : `/ontology/wiki?type=${encodeURIComponent(typeId)}`
            }
            className="ont-wiki-cta"
          >
            <div>
              <div className="ont-wiki-eyebrow">谛听增强 · WIKI</div>
              <div className="aos-text" style={{ fontSize: "0.875rem", fontWeight: 500 }}>
                LLM Wiki 知识卡片（双向绑定）
              </div>
              <p className="muted" style={{ fontSize: "0.75rem", margin: "0.25rem 0 0" }}>
                {objects[0]?.id
                  ? `Object 旁挂载活 Wiki · 写经 Draft · 默认实例 ${String(objects[0].id)}`
                  : "当前分支暂无实例 · 打开后自行选择对象"}
              </p>
            </div>
            <span className="ont-wiki-go">打开 Wiki →</span>
          </Link>
        </div>
      )}

      {tab === "properties" && (
        <div className="ont-props-editor">
          <p className="muted" style={{ fontSize: "0.8rem", margin: "0 0 0.5rem" }}>
            增删改属性后点保存 · 首行常视为 PK（不强制）· 勾选发布时须至少一行属性
          </p>
          <div className="ont-form-grid" style={{ marginBottom: 8 }}>
            {draftProps.map((p, i) => (
              <div key={i} className="ont-prop-row" style={{ display: "contents" }}>
                <label className="ont-form-field">
                  <span>
                    name{i === 0 ? " · PK" : ""}
                  </span>
                  <input
                    className="aos-input"
                    value={p.name}
                    onChange={(e) => {
                      const next = [...draftProps];
                      next[i] = { ...next[i], name: e.target.value };
                      setDraftProps(next);
                    }}
                  />
                </label>
                <label className="ont-form-field">
                  <span>type</span>
                  <input
                    className="aos-input"
                    value={p.type || "string"}
                    onChange={(e) => {
                      const next = [...draftProps];
                      next[i] = { ...next[i], type: e.target.value };
                      setDraftProps(next);
                    }}
                  />
                </label>
                <div className="ont-form-field" style={{ justifyContent: "flex-end" }}>
                  <span className="muted" style={{ fontSize: "0.7rem" }}>
                    &nbsp;
                  </span>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => setDraftProps(draftProps.filter((_, j) => j !== i))}
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
            <button
              type="button"
              className="btn-nav"
              onClick={() => setDraftProps([...draftProps, { name: "", type: "string" }])}
            >
              ＋ 属性
            </button>
            <label className="ont-form-check">
              <input
                type="checkbox"
                checked={metaPublish}
                onChange={(e) => setMetaPublish(e.target.checked)}
              />
              一并发布
            </label>
            <button
              type="button"
              className="btn-primary"
              disabled={metaBusy}
              onClick={() => void saveMeta()}
            >
              {metaBusy ? "保存中…" : "保存 Properties"}
            </button>
          </div>
          {metaMsg && <p className="bp-prop-ok">{metaMsg}</p>}
          {metaErr && <p className="error">{metaErr}</p>}
        </div>
      )}

      {tab === "actions" && (
        <>
          <div style={{ marginBottom: 8 }}>
            <Link
              to={`/ontology/action-types/new?ot=${encodeURIComponent(typeId)}`}
              className="btn-nav"
            >
              ＋ 新建 Action Type
            </Link>
          </div>
          {actions.length === 0 && <p className="muted">该 Object Type 暂无 Action Type</p>}
          <ul className="card-list">
            {actions.map((a) => (
              <li key={a.id} className="card">
                <strong>{a.name}</strong>
                <span className="muted" style={{ marginLeft: 8 }}>
                  {a.id}
                </span>
                <Link
                  to={`/ontology/action-types/${encodeURIComponent(a.id)}`}
                  className="bp-action-link"
                  style={{ marginLeft: 12 }}
                >
                  编辑 →
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}

      {tab === "links" && (
        <>
          <div style={{ marginBottom: 8 }}>
            <Link
              to={`/ontology/link-types/new?src=${encodeURIComponent(typeId)}`}
              className="btn-nav"
            >
              ＋ 新建 Link Type
            </Link>
          </div>
          <LinkTypeGraphViz typeId={typeId} links={links} />
          {links.length > 0 && (
            <BpTable
              columns={["id", "rel", "src", "dst", ""]}
              rows={links.map((l) => [
                l.id,
                l.rel || "—",
                l.srcType || "—",
                l.dstType || "—",
                <Link key={l.id} to={`/ontology/link-types/${encodeURIComponent(l.id)}`} className="bp-action-link">
                  编辑 →
                </Link>,
              ])}
            />
          )}
        </>
      )}

      {tab === "dependents" && (
        <>
          {modules.length === 0 && (
            <p className="muted">暂无绑定该类型的 Workshop Module（objectType 匹配）</p>
          )}
          <BpTable
            columns={["依赖", "类型", ""]}
            rows={[
              ...modules.map((m) => [
                m.name,
                "Workshop Module",
                <Link key={m.id} to="/workshop/inbox">
                  打开 →
                </Link>,
              ]),
              ["Funnel Pipeline", "Data", <Link key="f" to={`/ontology/funnel?type=${encodeURIComponent(typeId)}`}>Pipeline →</Link>],
            ]}
          />
        </>
      )}

      {tab === "data" && (
        <>
          <BpBanner tone="info">
            <strong>Datasources</strong>
            <p className="muted" style={{ margin: "0.5rem 0 0", fontSize: "0.875rem" }}>
              Backing 单一原则 · 实例 {instanceCount} · Funnel {funnelStage || "—"}
            </p>
            <Link
              to={`/ontology/funnel?type=${encodeURIComponent(typeId)}`}
              className="btn-nav"
              style={{ marginTop: 8, display: "inline-block" }}
            >
              查看 Funnel 四阶段 →
            </Link>
          </BpBanner>
          <div className="bp-ws-section-title" style={{ marginTop: "1rem" }}>
            实例 @ {branchId}
          </div>
          <ul className="card-list">
            {objects.map((o) => (
              <li key={String(o.id)} className="card">
                <button
                  type="button"
                  className="nav-link"
                  onClick={() => onOpenInstance(String(o.id))}
                >
                  {String(o.id)} · {String(o.title || "")}
                </button>
              </li>
            ))}
          </ul>
          {objects.length === 0 && <p className="muted">该类型暂无实例</p>}
          {detail && detailProps && (
            <div className="bp-object-panel" style={{ marginTop: "0.75rem" }}>
              <div className="bp-object-title">{String(detail.id)}</div>
              <BpPropGrid items={detailProps} />
              {canEditBranch ? (
                <div className="ont-branch-edit" style={{ marginTop: "0.75rem" }}>
                  <p className="muted" style={{ margin: "0 0 0.5rem", fontSize: "0.8rem" }}>
                    开发分支可写 overlay（不经 Draft）。生产/只读分支请走 Action。
                  </p>
                  <div className="ont-form-grid">
                    <label className="ont-form-field">
                      <span>title</span>
                      <input
                        className="aos-input"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                      />
                    </label>
                    <label className="ont-form-field">
                      <span>status</span>
                      <input
                        className="aos-input"
                        value={editStatus}
                        onChange={(e) => setEditStatus(e.target.value)}
                      />
                    </label>
                  </div>
                  <button
                    type="button"
                    className="btn-primary"
                    style={{ marginTop: 8 }}
                    disabled={editBusy}
                    onClick={() => void saveBranchOverlay()}
                  >
                    {editBusy ? "保存中…" : `保存到分支 ${branchId}`}
                  </button>
                  {editMsg && <p className="bp-prop-ok">{editMsg}</p>}
                  {editErr && <p className="error">{editErr}</p>}
                </div>
              ) : (
                <p className="muted" style={{ marginTop: "0.5rem", fontSize: "0.8rem" }}>
                  当前分支只读/生产 · 实例写回请走 Draft / Action
                </p>
              )}
              {neighbors.length > 0 && (
                <BpTable
                  columns={["id", "type", "rel"]}
                  rows={neighbors.map((n) => [
                    String(n.id ?? "—"),
                    String(n.type ?? "—"),
                    String(n.rel ?? "—"),
                  ])}
                />
              )}
            </div>
          )}
        </>
      )}

      {tab === "usage" && (
        <>
          <BpScoreGrid
            items={[
              {
                value: metricsTotal != null ? String(metricsTotal) : "—",
                label: "API 请求（进程累计）",
                hint: "非 OT 专属 · 进程累计请求",
                tone: "warn",
              },
              {
                value: String(instanceCount),
                label: "实例数",
                hint: "当前分支",
                tone: "ok",
              },
              {
                value: String(actions.length),
                label: "Action types",
                hint: "可写回入口",
                tone: "ok",
              },
            ]}
          />
          <p className="muted" style={{ fontSize: "0.75rem" }}>
            Usage 为进程累计 metrics + 当前分支实例数，非 30 天专属统计。
          </p>
          <BpMetricGrid
            items={[
              { label: "Workshop 模块", value: modules.length, tone: modules.length ? "ok" : "muted" },
              { label: "Link types", value: links.length, tone: links.length ? "ok" : "muted" },
            ]}
          />
        </>
      )}
    </div>
  );
}
