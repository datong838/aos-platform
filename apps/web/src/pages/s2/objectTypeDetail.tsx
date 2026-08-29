import { useEffect, useMemo, useRef, useState } from "react";
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

type OtDetailResponse = OtDetailMeta & {
  id?: string;
  name?: string;
  description?: string;
  published?: boolean;
  properties?: PropDef[];
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
  { id: "overview", label: "概览" },
  { id: "properties", label: "属性" },
  { id: "actions", label: "业务动作" },
  { id: "links", label: "关系图" },
  { id: "dependents", label: "依赖" },
  { id: "data", label: "数据" },
  { id: "usage", label: "使用统计" },
];

function branchAllowsOverlayWrite(branchId: string, branchReadonly?: boolean): boolean {
  if (branchReadonly) return false;
  if (!branchId || branchId === "main" || branchId === "master") return false;
  return true;
}

/** 只保留列表响应明确提供的标识和显示名，不推导存储或治理事实。 */
export function deriveOtDetailMeta(
  typeId: string,
  typeName: string,
  _properties?: PropDef[],
): OtDetailMeta {
  return {
    apiName: typeId,
    displayName: (typeName || typeId).trim() || typeId,
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
  const m = input.meta || {};
  const funnelTone = input.funnelStage && /live|index|done/i.test(input.funnelStage) ? "ok" : "warn";
  const items: OtMetaKvItem[] = [
    { label: "对象类型标识", value: input.typeId },
    { label: "显示名称", value: m.displayName || input.typeName },
    { label: "分支", value: input.branchId },
    { label: "属性数", value: String((input.properties || []).length) },
    { label: "业务漏斗", value: businessFunnelLabel(input.funnelStage), tone: funnelTone === "ok" ? "ok" : "warn" },
  ];
  const explicit: Array<[string, string | undefined]> = [
    ["资源标识", m.rid],
    ["接口名称", m.apiName],
    ["主键", m.primaryKey],
    ["标题字段", m.titleKey],
    ["复数名称", m.pluralName],
    ["承载数据集", m.backingDataset],
    ["同步策略", m.syncStrategy],
    ["存储类型", m.storageType],
    ["创建人", m.createdBy],
    ["可见范围", m.visibility],
  ];
  explicit.forEach(([label, value]) => {
    if (value) items.push({ label, value });
  });
  return items;
}

export function businessObjectDescription(input: string): string {
  return input
    .replace(/^\s*(?:Phase|阶段)\s*[A-Z0-9+.-]+\s*[·:：-]?\s*/i, "")
    .replace(/\bObject\s*Type\b/gi, "对象类型")
    .replace(/\bObject\b/gi, "对象")
    .replace(/\bWiki\b/gi, "知识页")
    .replace(/\bDraft\b/gi, "草稿审批")
    .trim();
}

function businessFunnelLabel(stage?: string): string {
  if (!stage) return "未配置";
  if (/error|fail/i.test(stage)) return "异常";
  if (/hydration/i.test(stage)) return "语义准备中";
  if (/index/i.test(stage)) return "索引中";
  if (/live/i.test(stage)) return "已生效";
  if (/done/i.test(stage)) return "已完成";
  return "状态待确认";
}

export function businessObjectLabel(
  row: Record<string, unknown>,
  typeName: string,
  index = 0,
): string {
  const explicit = row._displayLabel || row.displayLabel || row.title || row.name;
  if (explicit) return String(explicit);
  const businessCode = row.orderNo || row.order_no || row.code || row.number;
  if (businessCode) return `${typeName || "业务对象"} · ${String(businessCode)}`;
  const sourceLabel = row._sourceRecordLabel;
  if (sourceLabel) return `${typeName || "业务对象"} · ${String(sourceLabel)}`;
  return `第 ${index + 1} 条业务实例`;
}

const BUSINESS_DETAIL_LABELS: Record<string, string> = {
  orderNo: "订单号",
  order_no: "订单号",
  totalAmount: "订单金额",
  total_amount: "订单金额",
  currency: "币种",
  status: "数据状态",
  payStatus: "支付状态",
  orderStatus: "订单状态",
  deliveryStatus: "配送状态",
  memberId: "会员标识",
  customerName: "客户名称",
  shopId: "店铺标识",
  createdAt: "创建时间",
  updatedAt: "更新时间",
  code: "业务编码",
  number: "业务编号",
  title: "标题",
  name: "名称",
};

export function businessDetailItems(row: Record<string, unknown>): OtMetaKvItem[] {
  return Object.entries(BUSINESS_DETAIL_LABELS)
    .filter(([key]) => row[key] !== undefined && row[key] !== null && row[key] !== "")
    .slice(0, 10)
    .map(([key, label]) => ({ label, value: String(row[key]) }));
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
      label: l.name || l.rel || "关系",
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
    return <p className="muted w3-c2-link-empty">暂无关系类型</p>;
  }
  return (
    <div className="w3-c2-link-graph" aria-label="对象关系图">
      <svg
        className="w3-c2-link-svg"
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        role="img"
        aria-label={`${typeId} 对象关系图`}
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
  const requestScopeRef = useRef("");
  requestScopeRef.current = `${typeId}\u0000${branchId}`;
  const canEditBranch = branchAllowsOverlayWrite(branchId, branchReadonly);

  function applyDetailSnapshot(snapshot: OtDetailResponse) {
    setMetaName(snapshot.name || typeId);
    setMetaDesc(snapshot.description || "");
    setMetaPublish(Boolean(snapshot.published));
    setDraftProps(snapshot.properties || []);
    setOtMeta({
      rid: snapshot.rid,
      apiName: snapshot.apiName,
      primaryKey: snapshot.primaryKey,
      titleKey: snapshot.titleKey,
      displayName: snapshot.displayName,
      pluralName: snapshot.pluralName,
      backingDataset: snapshot.backingDataset,
      syncStrategy: snapshot.syncStrategy,
      storageType: snapshot.storageType,
      createdBy: snapshot.createdBy,
      visibility: snapshot.visibility,
    });
  }

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
    setMetaBusy(false);
  }, [typeId, typeName, description, published, properties]);

  useEffect(() => {
    if (!detail) {
      setEditTitle("");
      setEditStatus("");
      setEditMsg("");
      setEditErr("");
      setEditBusy(false);
      return;
    }
    setEditTitle(String(detail.title ?? ""));
    setEditStatus(String(detail.status ?? ""));
    setEditMsg("");
    setEditErr("");
    setEditBusy(false);
  }, [detail]);

  async function saveMeta() {
    const requestScope = requestScopeRef.current;
    setMetaBusy(true);
    setMetaMsg("");
    setMetaErr("");
    let writeCommitted = false;
    try {
      const cleaned = draftProps
        .map((p) => ({ name: p.name.trim(), type: (p.type || "string").trim() || "string" }))
        .filter((p) => p.name);
      const expected = {
        name: metaName.trim() || typeId,
        description: metaDesc,
        properties: cleaned,
        publish: metaPublish,
      };
      const written = await apiPut<OtDetailResponse & { publish?: boolean }>(
        `/v1/ontology/object-types/${encodeURIComponent(typeId)}`,
        expected,
      );
      writeCommitted = true;
      if (
        written.id !== typeId ||
        written.name !== expected.name ||
        (written.description || "") !== expected.description ||
        Boolean(written.published ?? written.publish) !== expected.publish ||
        JSON.stringify(written.properties || []) !== JSON.stringify(expected.properties)
      ) {
        throw new Error("写入回包与提交内容不一致");
      }
      if (requestScopeRef.current !== requestScope) return;
      const verified = await apiGet<OtDetailResponse>(
        `/v1/ontology/object-types/${encodeURIComponent(typeId)}`,
      );
      if (
        verified.id !== typeId ||
        verified.name !== expected.name ||
        (verified.description || "") !== expected.description ||
        Boolean(verified.published) !== expected.publish ||
        JSON.stringify(verified.properties || []) !== JSON.stringify(expected.properties)
      ) {
        throw new Error("详情重读结果与提交内容不一致");
      }
      if (requestScopeRef.current !== requestScope) return;
      applyDetailSnapshot(verified);
      setMetaMsg("已保存并重读对象类型详情");
      onMetaSaved?.();
    } catch (e) {
      if (requestScopeRef.current !== requestScope) return;
      const detail = String((e as Error).message || e);
      setMetaErr(writeCommitted ? `写入已提交但详情重读失败（verify_failed）：${detail}` : detail);
    } finally {
      if (requestScopeRef.current === requestScope) setMetaBusy(false);
    }
  }

  async function saveBranchOverlay() {
    if (!detail?.id || !canEditBranch) return;
    const requestScope = requestScopeRef.current;
    setEditBusy(true);
    setEditMsg("");
    setEditErr("");
    let writeCommitted = false;
    try {
      const props: Record<string, unknown> = { ...detail };
      delete props.id;
      delete props.type;
      delete props.branch;
      props.title = editTitle;
      props.status = editStatus;
      const written = await getOntologyClient().putObject(
        typeId,
        String(detail.id),
        { props, op: "upsert" },
        { branch: branchId },
      );
      writeCommitted = true;
      if (
        written.ok !== true ||
        written.objectType !== typeId ||
        written.objectId !== String(detail.id) ||
        written.branch !== branchId
      ) {
        throw new Error("写入回包与目标对象或分支不一致");
      }
      if (requestScopeRef.current !== requestScope) return;
      const verified = await apiGet<OtDetailResponse>(
        `/v1/ontology/object-types/${encodeURIComponent(typeId)}`,
      );
      if (verified.id !== typeId) throw new Error("详情重读目标不一致");
      if (requestScopeRef.current !== requestScope) return;
      applyDetailSnapshot(verified);
      setEditMsg(`已写入分支定制并重读对象类型详情 · ${branchId}`);
      onBranchSaved?.();
    } catch (e) {
      if (requestScopeRef.current !== requestScope) return;
      const detailMessage = String((e as Error).message || e);
      setEditErr(writeCommitted ? `写入已提交但详情重读失败（verify_failed）：${detailMessage}` : detailMessage);
    } finally {
      if (requestScopeRef.current === requestScope) setEditBusy(false);
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
        const d = await apiGet<OtDetailResponse>(
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
  const detailProps = detail ? businessDetailItems(detail) : null;
  const detailAuditProps =
    detail &&
    Object.entries(detail)
      .filter(([k]) => !k.startsWith("_"))
      .slice(0, 16)
      .map(([k, v]) => ({ label: k, value: String(v ?? "—") }));

  const funnelTone = funnelStage && /live|index|done/i.test(funnelStage) ? "ok" : "warn";

  return (
    <div className="bp-object-panel" style={{ marginTop: "1rem" }}>
      <div className="bp-object-title">
        {typeName}
        <details style={{ display: "inline-block", marginLeft: 10, fontSize: "0.75rem", fontWeight: 400 }}>
          <summary>审计上下文</summary>
          <code>{typeId}</code> · 分支 <code>{branchId}</code>
        </details>
      </div>

      <BpTabs tabs={TABS} active={tab} onChange={setTab} />

      {tab === "overview" && (
        <div className="ont-overview">
          {/* ① 对象概览 */}
          <section className="ont-meta-card">
            <div className="ont-meta-eyebrow">
              <span>① 对象概览</span>
              <span className="muted">· 当前对象类型</span>
            </div>
            <div className="ont-meta-head">
              <div>
                <div className="muted" style={{ fontSize: "0.7rem" }}>
                  显示名
                </div>
                <strong>{metaName}</strong>
                <p className="muted" style={{ fontSize: "0.75rem", margin: "0.25rem 0 0" }}>
                  {businessObjectDescription(metaDesc) || "暂无业务说明"}
                </p>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                <span className={`bp-tag bp-tag-${metaPublish ? "ok" : "warn"}`}>
                  {metaPublish ? "已发布" : "草稿"}
                </span>
                <span className={`bp-tag bp-tag-${funnelTone}`}>
                  业务漏斗：{businessFunnelLabel(funnelStage)}
                </span>
                <span className="bp-tag">{instanceCount} 个实例</span>
              </div>
            </div>
            <details style={{ marginTop: 10 }}>
              <summary>编辑对象信息</summary>
              <label className="ont-form-field" style={{ display: "block", marginTop: 8 }}>
                <span className="muted" style={{ fontSize: "0.7rem" }}>显示名称</span>
                <input className="aos-input ont-meta-title-input" value={metaName} onChange={(e) => setMetaName(e.target.value)} aria-label="对象类型显示名称" />
              </label>
              <label className="ont-form-field" style={{ display: "block", marginTop: 8 }}>
                <span className="muted" style={{ fontSize: "0.7rem" }}>业务说明</span>
                <input className="aos-input" value={metaDesc} onChange={(e) => setMetaDesc(e.target.value)} placeholder="对象类型业务说明" />
              </label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 8, alignItems: "center" }}>
                <label className="ont-form-check">
                  <input type="checkbox" checked={metaPublish} onChange={(e) => setMetaPublish(e.target.checked)} />
                  发布（至少需要一个属性）
                </label>
                <button type="button" className="btn-primary" disabled={metaBusy} onClick={() => void saveMeta()}>
                  {metaBusy ? "保存中…" : "保存对象信息"}
                </button>
                <button type="button" className="bp-action-link" onClick={() => setTab("properties")}>
                  编辑属性 →
                </button>
              </div>
            </details>
            {metaMsg && <p className="bp-prop-ok">{metaMsg}</p>}
            {metaErr && <p className="error">{metaErr}</p>}
            <details style={{ marginTop: 10 }}>
              <summary>审计信息</summary>
              <BpPropGrid items={metaKvItems} />
            </details>
          </section>

          <div className="ont-overview-grid">
            <div className="ont-ov-card">
              <div className="ont-ov-card-head">
                <h3>
                  <span className="ont-ov-num">②</span> 属性
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
                  <span className="ont-ov-num">③</span> 业务动作
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
                  <span className="ont-ov-num">④</span> 关系图
                </h3>
                <Link
                  to={`/ontology/link-types/${links[0] ? encodeURIComponent(links[0].id) : "new"}?src=${encodeURIComponent(typeId)}`}
                  className="bp-action-link"
                >
                  {links[0] ? "打开编辑器 →" : "新建关系 →"}
                </Link>
              </div>
              <LinkTypeGraphViz typeId={typeId} links={links} />
            </div>
            <div className="ont-ov-card">
              <div className="ont-ov-card-head">
                <h3>
                  <span className="ont-ov-num">⑥</span> 数据与业务漏斗
                </h3>
                <Link to={`/ontology/funnel?type=${encodeURIComponent(typeId)}`} className="bp-action-link">
                  查看业务漏斗 →
                </Link>
              </div>
              <p className="muted" style={{ fontSize: "0.8rem", margin: 0 }}>
                业务漏斗：{businessFunnelLabel(funnelStage)}
              </p>
              <button type="button" className="bp-action-link" style={{ marginTop: 8 }} onClick={() => setTab("data")}>
                查看数据 →
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
              <div className="ont-wiki-eyebrow">智能知识</div>
              <div className="aos-text" style={{ fontSize: "0.875rem", fontWeight: 500 }}>
                智能知识卡片（双向绑定）
              </div>
              <p className="muted" style={{ fontSize: "0.75rem", margin: "0.25rem 0 0" }}>
                {objects[0]?.id
                  ? "已选择首个读取到的实例 · 编辑需经草稿审批"
                  : "当前分支暂无实例 · 打开后选择对象"}
              </p>
            </div>
            <span className="ont-wiki-go">打开知识页 →</span>
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
                    属性标识{i === 0 ? " · 主键候选" : ""}
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
                  <span>数据类型</span>
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
              {metaBusy ? "保存中…" : "保存属性"}
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
              ＋ 新建业务动作
            </Link>
          </div>
          {actions.length === 0 && <p className="muted">该对象类型暂无业务动作</p>}
          <ul className="card-list">
            {actions.map((a) => (
              <li key={a.id} className="card">
                <strong>{a.name}</strong>
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
              ＋ 新建关系类型
            </Link>
          </div>
          <LinkTypeGraphViz typeId={typeId} links={links} />
          {links.length > 0 && (
            <BpTable
              columns={["关系名称", "来源对象", "目标对象", ""]}
              rows={links.map((l) => [
                l.name || l.rel || "未命名关系",
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
            <p className="muted">暂无绑定该对象类型的工作台应用</p>
          )}
          <BpTable
            columns={["依赖", "类型", ""]}
            rows={[
              ...modules.map((m) => [
                m.name,
                "工作台应用",
                <Link key={m.id} to="/workshop/inbox">
                  打开 →
                </Link>,
              ]),
              ["业务漏斗", "数据", <Link key="f" to={`/ontology/funnel?type=${encodeURIComponent(typeId)}`}>打开 →</Link>],
            ]}
          />
        </>
      )}

      {tab === "data" && (
        <>
          <BpBanner tone="info">
            <strong>数据来源</strong>
            <p className="muted" style={{ margin: "0.5rem 0 0", fontSize: "0.875rem" }}>
              单一承载原则 · 实例 {instanceCount} · 业务漏斗 {businessFunnelLabel(funnelStage)}
            </p>
            <Link
              to={`/ontology/funnel?type=${encodeURIComponent(typeId)}`}
              className="btn-nav"
              style={{ marginTop: 8, display: "inline-block" }}
            >
              查看业务漏斗四阶段 →
            </Link>
          </BpBanner>
          <div className="bp-ws-section-title" style={{ marginTop: "1rem" }}>
            实例 · 当前分支
          </div>
          <ul className="card-list">
            {objects.map((o, index) => (
              <li key={String(o.id)} className="card">
                <button
                  type="button"
                  className="nav-link"
                  onClick={() => onOpenInstance(String(o.id))}
                >
                  {businessObjectLabel(o, typeName, index)}
                </button>
              </li>
            ))}
          </ul>
          {objects.length === 0 && <p className="muted">该类型暂无实例</p>}
          {detail && detailProps && (
            <div className="bp-object-panel" style={{ marginTop: "0.75rem" }}>
              <div className="bp-object-title">{businessObjectLabel(detail, typeName)}</div>
              <BpPropGrid items={detailProps} />
              {detailAuditProps && (
                <details style={{ marginTop: 10 }}>
                  <summary>原始字段审计</summary>
                  <BpPropGrid items={detailAuditProps} />
                </details>
              )}
              {canEditBranch ? (
                <div className="ont-branch-edit" style={{ marginTop: "0.75rem" }}>
                  <p className="muted" style={{ margin: "0 0 0.5rem", fontSize: "0.8rem" }}>
                    当前开发分支允许保存定制内容；生产或只读分支需经草稿审批或业务动作。
                  </p>
                  <div className="ont-form-grid">
                    <label className="ont-form-field">
                      <span>标题</span>
                      <input
                        className="aos-input"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                      />
                    </label>
                    <label className="ont-form-field">
                      <span>状态</span>
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
                  当前分支只读或为生产分支，实例变更需经草稿审批或业务动作
                </p>
              )}
              {neighbors.length > 0 && (
                <details style={{ marginTop: 10 }}>
                  <summary>关联对象审计</summary>
                  <BpTable
                    columns={["对象标识", "对象类型", "关系"]}
                    rows={neighbors.map((n) => [
                      String(n.id ?? "—"),
                      String(n.type ?? "—"),
                      String(n.rel ?? "—"),
                    ])}
                  />
                </details>
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
                label: "业务动作",
                hint: "受控变更入口",
                tone: "ok",
              },
            ]}
          />
          <p className="muted" style={{ fontSize: "0.75rem" }}>
            使用统计由进程累计请求与当前分支实例数构成，不代表近 30 天统计。
          </p>
          <BpMetricGrid
            items={[
              { label: "工作台应用", value: modules.length, tone: modules.length ? "ok" : "muted" },
              { label: "关系类型", value: links.length, tone: links.length ? "ok" : "muted" },
            ]}
          />
        </>
      )}
    </div>
  );
}
