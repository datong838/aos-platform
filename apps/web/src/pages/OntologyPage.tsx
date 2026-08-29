import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiGet, apiPost, apiPut } from "../api/client";
import { getOntologyClient } from "../api/ontologyClient";
import { PageChrome } from "../components/PageChrome";
import {
  formatRelativeZh,
  isFavorite,
  loadBranchPref,
  loadFavorites,
  loadRecent,
  pushRecent,
  saveBranchPref,
  toggleFavorite,
  type RecentEntry,
} from "../lib/ontologyRecent";
import {
  BpDiscoverCard,
  BpTable,
} from "./s2/blueprintUi";
import { ObjectTypeDetailPanel } from "./s2/objectTypeDetail";

type Branch = { id: string; name: string; baseRef: string; readonly: boolean };
type Health = { score: number; metrics: Record<string, unknown> };
type ObjectTypeRow = {
  id: string;
  name: string;
  description?: string;
  published?: boolean;
  properties?: { name: string; type?: string }[];
};

type TypeStats = {
  id: string;
  name: string;
  instanceCount: number | null;
  funnelStage?: string;
  published?: boolean;
};

type OntologyComposition = {
  installation_pk: string;
  installation_revision: number;
  composed_schema_etag: string;
};

type ActiveOverlay = {
  target_kind: string;
  target_id: string;
  mode: "override" | "inherit";
  display_name?: string | null;
  ontology_revision: number;
  base_schema_sha256: string;
};

const ECOM_OBJECT_TYPES = new Set([
  "Shop", "Product", "ProductSku", "Category", "Order", "OrderLine", "Shipment",
  "CustomerLite", "Weapp", "SystemConfig", "ProductReview", "Payment",
]);

/** 91/92 · 发现页 · 最近真源 · 分支偏好 */
export function OntologyPage() {
  const navigate = useNavigate();
  const [types, setTypes] = useState<ObjectTypeRow[]>([]);
  const [typeStats, setTypeStats] = useState<TypeStats[]>([]);
  const [objects, setObjects] = useState<Record<string, unknown>[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [neighbors, setNeighbors] = useState<{ id?: string; type?: string; rel?: string }[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [branchId, setBranchId] = useState(() => loadBranchPref("main"));
  const [search, setSearch] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const [newId, setNewId] = useState("");
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [propName, setPropName] = useState("code");
  const [publish, setPublish] = useState(false);
  const [busy, setBusy] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [recent, setRecent] = useState<RecentEntry[]>(() => loadRecent());
  const [favoriteIds, setFavoriteIds] = useState<string[] | null>(() => loadFavorites());
  const [linkTypes, setLinkTypes] = useState<{ id: string; name: string; rel?: string; srcType?: string; dstType?: string }[]>([]);
  const [actionTypes, setActionTypes] = useState<{ id: string; name: string; objectType?: string }[]>([]);
  const [composition, setComposition] = useState<OntologyComposition | null>(null);
  const [activeOverlay, setActiveOverlay] = useState<ActiveOverlay | null>(null);
  const [overlayName, setOverlayName] = useState("");
  const [overlayBusy, setOverlayBusy] = useState(false);

  const recordRecentOt = useCallback((id: string, name?: string) => {
    setRecent(pushRecent({ kind: "objectType", id, label: name || id }));
  }, []);

  const recordRecentLink = useCallback((id: string, label: string, href: string) => {
    setRecent(pushRecent({ kind: "link", id, label, href }));
  }, []);

  const onToggleFavorite = useCallback((id: string) => {
    setFavoriteIds(toggleFavorite(id));
  }, []);

  const loadStats = useCallback(async (items: ObjectTypeRow[]) => {
    const stats: TypeStats[] = [];
    for (const t of items) {
      let instanceCount: number | null = null;
      let funnelStage: string | undefined;
      try {
        const list = await getOntologyClient().listObjects(t.id);
        instanceCount = list.items?.length ?? 0;
      } catch {
        instanceCount = null;
      }
      try {
        const f = await apiGet<{ stage?: string }>(`/v1/funnel/${encodeURIComponent(t.id)}/status`);
        funnelStage = f.stage;
      } catch {
        funnelStage = undefined;
      }
      stats.push({
        id: t.id,
        name: t.name,
        instanceCount,
        funnelStage,
        published: t.published,
      });
    }
    setTypeStats(stats);
  }, []);

  const reloadTypes = useCallback(async () => {
    const [t, b, h, lt, at] = await Promise.all([
      apiGet<{ items: ObjectTypeRow[]; composition?: OntologyComposition | null }>("/v1/ontology/object-types"),
      apiGet<{ items: Branch[] }>("/v1/ontology/branches"),
      apiGet<Health>("/v1/ontology/graph-health"),
      apiGet<{ items: { id: string; name: string; rel?: string; srcType?: string; dstType?: string }[] }>(
        "/v1/ontology/link-types",
      ).catch(() => ({ items: [] })),
      apiGet<{ items: { id: string; name: string; objectType?: string }[] }>("/v1/actions/types").catch(() => ({
        items: [],
      })),
    ]);
    setTypes(t.items);
    setComposition(t.composition || null);
    setBranches(b.items);
    setHealth(h);
    setLinkTypes(lt.items || []);
    setActionTypes(at.items || []);
    if (b.items.length && !b.items.some((x) => x.id === branchId)) {
      const next = b.items[0].id;
      setBranchId(next);
      saveBranchPref(next);
    }
    await loadStats(t.items);
  }, [branchId, loadStats]);

  useEffect(() => {
    if (!selected || !composition?.installation_pk) {
      setActiveOverlay(null);
      return;
    }
    let current = true;
    void apiGet<{ items: ActiveOverlay[] }>(
      `/v1/ontology/installations/${encodeURIComponent(composition.installation_pk)}/overlays`,
    ).then((result) => {
      if (!current) return;
      const hit = result.items.find((item) => item.target_kind === "ObjectType" && item.target_id === selected) || null;
      setActiveOverlay(hit);
      setOverlayName(hit?.display_name || types.find((type) => type.id === selected)?.name || selected);
    }).catch((error) => current && setErr(String((error as Error).message || error)));
    return () => { current = false; };
  }, [composition?.installation_pk, selected, types]);

  async function saveOrganizationOverlay(mode: "override" | "inherit") {
    if (!selected || !composition?.installation_pk) return;
    setOverlayBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const ifMatch = activeOverlay
        ? `"ontology-overlay-v1:${activeOverlay.ontology_revision}:${activeOverlay.base_schema_sha256}"`
        : '"0"';
      const result = await apiPut<{
        ontologyRevision: number; baseSchemaSha256: string; mode: "override" | "inherit";
        displayName?: string | null;
      }>(
        `/v1/ontology/installations/${encodeURIComponent(composition.installation_pk)}/overlays/ObjectType/${encodeURIComponent(selected)}`,
        mode === "inherit"
          ? { mode: "inherit", displayName: null, visibleProperties: null, extendedProperties: {}, policies: null }
          : { mode: "override", displayName: overlayName.trim(), visibleProperties: null, extendedProperties: {}, policies: null },
        { "If-Match": ifMatch, "Idempotency-Key": crypto.randomUUID() },
      );
      setActiveOverlay({
        target_kind: "ObjectType", target_id: selected, mode: result.mode,
        display_name: result.displayName, ontology_revision: result.ontologyRevision,
        base_schema_sha256: result.baseSchemaSha256,
      });
      setMsg(mode === "inherit" ? "已创建继承修订，恢复当前安装模板显示名" : "组织定制已保存；未修改平台模板");
      await reloadTypes();
    } catch (error) {
      setErr(String((error as Error).message || error));
    } finally {
      setOverlayBusy(false);
    }
  }

  useEffect(() => {
    reloadTypes().catch((e) => setErr(String(e.message || e)));
  }, [reloadTypes]);

  const filteredTypes = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return types;
    return types.filter(
      (t) =>
        t.id.toLowerCase().includes(q) ||
        t.name.toLowerCase().includes(q) ||
        (t.description || "").toLowerCase().includes(q),
    );
  }, [types, search]);

  const filteredLinks = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return [];
    return linkTypes.filter(
      (l) =>
        l.id.toLowerCase().includes(q) ||
        l.name.toLowerCase().includes(q) ||
        (l.rel || "").toLowerCase().includes(q) ||
        (l.srcType || "").toLowerCase().includes(q) ||
        (l.dstType || "").toLowerCase().includes(q),
    );
  }, [linkTypes, search]);

  const filteredActions = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return [];
    return actionTypes.filter(
      (a) =>
        a.id.toLowerCase().includes(q) ||
        a.name.toLowerCase().includes(q) ||
        (a.objectType || "").toLowerCase().includes(q),
    );
  }, [actionTypes, search]);

  const favorites = useMemo(() => {
    if (favoriteIds && favoriteIds.length > 0) {
      const rows: TypeStats[] = [];
      for (const id of favoriteIds) {
        const st = typeStats.find((s) => s.id === id);
        if (st) {
          rows.push(st);
          continue;
        }
        const t = types.find((x) => x.id === id);
        if (t) {
          rows.push({
            id: t.id,
            name: t.name,
            instanceCount: 0,
            published: t.published,
          });
        }
      }
      return rows.slice(0, 6);
    }
    return [];
  }, [favoriteIds, typeStats, types]);

  const branchReadonly = useMemo(() => {
    const hit = branches.find((b) => b.id === branchId);
    if (hit) return !!hit.readonly;
    return branchId === "main" || branchId === "master";
  }, [branches, branchId]);

  async function openType(id: string, branch = branchId) {
    const meta = types.find((t) => t.id === id);
    setSelected(id);
    recordRecentOt(id, meta?.name);
    setDetail(null);
    setNeighbors([]);
    setErr(null);
    const q = branch ? { branch } : undefined;
    const list = await getOntologyClient().listObjects(id, q);
    setObjects(list.items as Record<string, unknown>[]);
  }

  function openDeep(id: string) {
    const meta = types.find((t) => t.id === id) || typeStats.find((t) => t.id === id);
    recordRecentOt(id, meta?.name);
    navigate(`/ontology/object-types/${encodeURIComponent(id)}`);
  }

  async function onBranchChange(next: string) {
    setBranchId(next);
    saveBranchPref(next);
    if (selected) {
      try {
        await openType(selected, next);
      } catch (e) {
        setErr(String((e as Error).message || e));
      }
    }
  }

  async function openObject(type: string, id: string) {
    setErr(null);
    const q = branchId ? { branch: branchId } : undefined;
    const ont = getOntologyClient();
    const d = await ont.getObject(type, id, q);
    setDetail(d as Record<string, unknown>);
    const n = (await ont.neighbors(type, id)) as {
      items?: { id?: string; type?: string; rel?: string }[];
    };
    setNeighbors(n.items || []);
  }

  async function createType() {
    const id = newId.trim();
    const name = newName.trim() || id;
    if (!id) {
      setErr("请填写对象类型标识");
      return;
    }
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const props = propName.trim() ? [{ name: propName.trim(), type: "string" }] : [];
      const res = await apiPost<{ id: string; lint?: { ok?: boolean } }>("/v1/ontology/object-types", {
        id,
        name,
        description: newDesc,
        publish,
        properties: props,
      });
      setMsg(
        `已创建 ${res.id}` +
          (res.lint && res.lint.ok === false ? " · 规则检查有告警" : publish ? " · 已发布" : " · 草稿"),
      );
      setNewId("");
      setNewName("");
      setCreateOpen(false);
      await reloadTypes();
      openDeep(res.id);
    } catch (e) {
      const errObj = e as Error & { body?: { details?: unknown; message?: string } };
      setErr(String(errObj.message || e));
    } finally {
      setBusy(false);
    }
  }

  function funnelBadge(stage?: string): { label: string; tone: "ok" | "warn" | "bad" } | undefined {
    if (!stage) return { label: "未配置", tone: "warn" };
    if (/error|fail/i.test(stage)) return { label: "异常", tone: "bad" };
    if (/index/i.test(stage)) return { label: "索引中", tone: "ok" };
    if (/live/i.test(stage)) return { label: "已生效", tone: "ok" };
    if (/done/i.test(stage)) return { label: "已完成", tone: "ok" };
    return { label: "状态待确认", tone: "warn" };
  }


  const selectedMeta = types.find((t) => t.id === selected);
  const selectedStats = typeStats.find((s) => s.id === selected);

  return (
    <PageChrome title="本体管理（数字孪生）" lede="发现、收藏和查看当前工作区的业务对象类型。">
      <div className="ont-page">
      {/* 91 v1.6 · 本页控件边框统一加深 */}
      <h2 className="ont-discover-title ont-discover-title-top">
        <span className="ont-discover-icon" aria-hidden>
          ✦
        </span>
        发现
      </h2>

      <div className="ont-toolbar-row ont-toolbar-search">
        <input
          type="search"
          className="aos-input ont-search-input"
          placeholder="搜索对象类型、关系类型或业务动作…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button
          type="button"
          className="btn ont-toolbar-refresh"
          title="重新读取对象类型、分支与图谱健康状态"
          onClick={() => void reloadTypes().catch((e) => setErr(String((e as Error).message || e)))}
        >
          ↻ 刷新列表
        </button>
      </div>

      <div className="ont-toolbar-row ont-toolbar-actions">
        <label className="mp-field ont-toolbar-field">
          <span className="mp-field-label">分支</span>
          <select
            className="aos-input"
            aria-label="选择分支"
            value={branchId}
            onChange={(e) => void onBranchChange(e.target.value)}
          >
            {branches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
                {b.readonly ? " (只读)" : ""}
              </option>
            ))}
          </select>
        </label>
        {health && (
          <Link to="/ontology/graph-health" className="btn-nav">
            图谱健康 {health.score}
          </Link>
        )}
        <Link to="/ontology/okf-funnel" className="btn-nav">
          行业映射
        </Link>
        <Link
          to="/ontology/branches"
          className="btn-nav"
          onClick={() => recordRecentLink("branches", "分支与组织定制", "/ontology/branches")}
        >
          分支与组织定制
        </Link>
        <Link
          to="/workshop/graph"
          className="btn-nav"
          title="先选择真实对象，再进入业务漏斗"
        >
          从对象进入业务漏斗
        </Link>
        <Link
          to="/workshop/graph"
          className="btn-nav"
          title="先选择真实对象，再进入知识库"
        >
          从对象进入知识库
        </Link>
        <Link to="/ontology/link-types/new" className="btn-nav">
          新建关系类型
        </Link>
        <Link to="/ontology/graph-health" className="btn-nav">
          图谱健康度
        </Link>
      </div>

      {msg && <p className="bp-prop-ok">{msg}</p>}
      {err && <p className="error">{err}</p>}

      <div className="ont-discover">
        {/* ① 收藏 */}
        <section className="ont-layer">
          <h3 className="ont-section-title">⭐ 收藏</h3>
          {favorites.length === 0 && (
            <p className="muted" style={{ margin: "0 0 0.5rem", fontSize: "0.8rem" }}>
              尚未收藏对象类型；可在下方列表点击星标加入收藏
            </p>
          )}
          <div className="bp-discover-grid">
            {favorites.map((t) => (
              <div key={t.id} className="ont-fav-wrap">
                <button
                  type="button"
                  className="ont-fav-star"
                  title={isFavorite(t.id, favoriteIds) ? "取消收藏" : "加入收藏"}
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleFavorite(t.id);
                  }}
                >
                  {isFavorite(t.id, favoriteIds) ? "★" : "☆"}
                </button>
                <BpDiscoverCard
                  accent="muted"
                  title={t.name}
                  badge={funnelBadge(t.funnelStage)}
                  meta={`${t.instanceCount === null ? "实例数未读取" : `${t.instanceCount} 个实例`}${t.published ? " · 已发布" : ""}`}
                  cta="打开详情 →"
                  onClick={() => openDeep(t.id)}
                />
              </div>
            ))}
            {favorites.length === 0 && (
              <div className="ont-block ont-block-empty">
                <p className="muted" style={{ margin: 0 }}>
                  暂无收藏
                </p>
              </div>
            )}
          </div>
        </section>

        {/* ② 最近查看 · 92 真持久化 + 真相对时间 */}
        <section className="ont-layer">
          <h3 className="ont-section-title">🕐 最近查看</h3>
          <ul className="bp-recent-list ont-block">
            {recent.length === 0 && (
              <li>
                <span className="muted">打开对象类型、业务漏斗或知识页后会出现在这里</span>
              </li>
            )}
            {recent.map((r) => (
              <li key={`${r.kind}-${r.id}`}>
                {r.kind === "objectType" ? (
                  <button type="button" className="bp-recent-link" onClick={() => openDeep(r.id)}>
                    {r.label}
                  </button>
                ) : (
                  <Link
                    to={r.href || r.id}
                    className="bp-recent-link"
                    onClick={() => recordRecentLink(r.id, r.label, r.href || r.id)}
                  >
                    {r.label}
                  </Link>
                )}
                <span className="bp-recent-time">{formatRelativeZh(r.at)}</span>
              </li>
            ))}
          </ul>
        </section>

        {/* ③ 重要表 */}
        <section className="ont-layer">
          <h3 className="ont-section-title">📌 重要 / 最近修改</h3>
          <div className="ont-block ont-block-table">
            <BpTable
              columns={["对象类型", "实例", "业务漏斗", "发布状态", ""]}
              rows={filteredTypes.map((t) => {
                const st = typeStats.find((s) => s.id === t.id);
                return [
                  t.name,
                  st?.instanceCount === null || st?.instanceCount === undefined ? "未读取" : String(st.instanceCount),
                  st?.funnelStage ? (
                    <span className={/error/i.test(st.funnelStage) ? "bp-prop-warn" : "bp-prop-ok"}>
                      {funnelBadge(st.funnelStage)?.label}
                    </span>
                  ) : (
                    "—"
                  ),
                  t.published ? "已发布" : "草稿",
                  <span key={t.id} style={{ display: "inline-flex", gap: 10, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="bp-action-link"
                      onClick={() => onToggleFavorite(t.id)}
                      title={isFavorite(t.id, favoriteIds) ? "取消收藏" : "加入收藏"}
                    >
                      {isFavorite(t.id, favoriteIds) ? "★" : "☆"}
                    </button>
                    <button type="button" className="bp-action-link" onClick={() => openDeep(t.id)}>
                      打开
                    </button>
                    <button
                      type="button"
                      className="bp-action-link"
                      onClick={() => void openType(t.id).catch((e) => setErr(String(e.message || e)))}
                    >
                      内嵌
                    </button>
                  </span>,
                ];
              })}
            />
          </div>
          {search.trim() && (filteredLinks.length > 0 || filteredActions.length > 0) && (
            <div style={{ marginTop: "0.85rem" }}>
              {filteredLinks.length > 0 && (
                <>
                  <h4 className="muted" style={{ margin: "0 0 0.35rem", fontSize: "0.8rem" }}>
                    关系类型命中
                  </h4>
                  <BpTable
                    columns={["关系名称", "来源对象", "目标对象", ""]}
                    rows={filteredLinks.slice(0, 8).map((l) => [
                      l.name,
                      types.find((type) => type.id === l.srcType)?.name || "未读取",
                      types.find((type) => type.id === l.dstType)?.name || "未读取",
                      <Link
                        key={l.id}
                        to={`/ontology/link-types/${encodeURIComponent(l.id)}`}
                        className="bp-action-link"
                      >
                        打开 →
                      </Link>,
                    ])}
                  />
                </>
              )}
              {filteredActions.length > 0 && (
                <>
                  <h4 className="muted" style={{ margin: "0.65rem 0 0.35rem", fontSize: "0.8rem" }}>
                    业务动作命中
                  </h4>
                  <BpTable
                    columns={["业务动作", "所属对象类型", ""]}
                    rows={filteredActions.slice(0, 8).map((a) => [
                      a.name,
                      types.find((type) => type.id === a.objectType)?.name || "未读取",
                      <Link
                        key={a.id}
                        to={`/ontology/action-types/${encodeURIComponent(a.id)}`}
                        className="bp-action-link"
                      >
                        编辑 →
                      </Link>,
                    ])}
                  />
                </>
              )}
            </div>
          )}
        </section>

        {/* ④ 水合 · 文案可换行 · 三钮同风格 */}
        <div className="bp-hydration-banner ont-block ont-block-hydrate">
          <p className="ont-hydrate-copy">
            <span className="ont-hydrate-label">标准水合</span>
            <span className="ont-hydrate-sep">·</span>
            <span>行业映射 → 对象确认 → 业务漏斗四阶段 → 工作台</span>
          </p>
          <div className="ont-hydrate-actions">
            <Link to="/ontology/okf-funnel" className="btn-nav">
              ① 行业映射
            </Link>
            <Link to="/workshop/graph" className="btn-nav" title="选择对象类型后进入业务漏斗">
              ② 业务漏斗
            </Link>
            <Link to="/workshop/inbox" className="btn-nav">
              ③ 工作台
            </Link>
          </div>
        </div>

        {/* ⑥ 本体治理入口 */}
        <section className="ont-layer">
          <h3 className="ont-section-title">🔐 本体治理入口</h3>
          <div className="bp-discover-grid">
            <Link to="/ontology/branches" className="bp-discover-card ont-block" style={{ padding: "16px 18px", textDecoration: "none" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span style={{ fontWeight: 600, fontSize: "14px", color: "var(--aos-text)" }}>分支与组织定制</span>
                <span className="bp-badge bp-badge-blue" style={{ fontSize: 12 }}>组织定制</span>
              </div>
              <p style={{ margin: 0, fontSize: "12px", color: "var(--aos-muted)", lineHeight: 1.5 }}>
                查看当前安装版本绑定的组织定制、不可变修订和生效版本。
              </p>
            </Link>
            <Link to="/ontology/graph-health" className="bp-discover-card ont-block" style={{ padding: "16px 18px", textDecoration: "none" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span style={{ fontWeight: 600, fontSize: "14px", color: "var(--aos-text)" }}>图谱健康度</span>
                <span className="bp-badge bp-badge-green" style={{ fontSize: 12 }}>健康</span>
              </div>
              <p style={{ margin: 0, fontSize: "12px", color: "var(--aos-muted)", lineHeight: 1.5 }}>
                监控本体图谱的一致性、连通性与告警。
              </p>
            </Link>
            <Link to="/workshop/graph" className="bp-discover-card ont-block" style={{ padding: "16px 18px", textDecoration: "none" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span style={{ fontWeight: 600, fontSize: "14px", color: "var(--aos-text)" }}>活知识库</span>
                <span className="bp-badge bp-badge-gray" style={{ fontSize: 12 }}>知识</span>
              </div>
              <p style={{ margin: 0, fontSize: "12px", color: "var(--aos-muted)", lineHeight: 1.5 }}>
                从真实对象进入，沉淀业务定义、示例与协作笔记。
              </p>
            </Link>
            <Link to="/workshop/graph" className="bp-discover-card ont-block" style={{ padding: "16px 18px", textDecoration: "none" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span style={{ fontWeight: 600, fontSize: "14px", color: "var(--aos-text)" }}>对象探索</span>
                <span className="bp-badge bp-badge-amber" style={{ fontSize: 12 }}>探索</span>
              </div>
              <p style={{ margin: 0, fontSize: "12px", color: "var(--aos-muted)", lineHeight: 1.5 }}>
                以对象为中心浏览实例、关系与时间线。
              </p>
            </Link>
          </div>
        </section>
      </div>

      {/* 内嵌七 Tab · 次要，仅「内嵌」时展开 */}
      {selected && selectedMeta && (
        <section className="ont-layer ont-layer-detail is-focus">
          <div className="mp-section-head">
            <h2 className="bp-ws-section-title" style={{ margin: 0 }}>
              内嵌详情 · {selectedMeta.name}
            </h2>
            <div className="ont-type-switch">
              <Link to={`/ontology/object-types/${encodeURIComponent(selected)}`} className="btn-nav-accent">
                完整深页 →
              </Link>
              <button type="button" className="btn" onClick={() => setSelected(null)}>
                收起
              </button>
            </div>
          </div>
          <ObjectTypeDetailPanel
            typeId={selected}
            typeName={selectedMeta.name}
            description={selectedMeta.description}
            published={selectedMeta.published}
            properties={selectedMeta.properties}
            branchId={branchId}
            branchReadonly={branchReadonly}
            instanceCount={selectedStats?.instanceCount ?? objects.length}
            funnelStage={selectedStats?.funnelStage}
            objects={objects}
            onOpenInstance={(id) =>
              void openObject(selected, id).catch((e) => setErr(String(e.message || e)))
            }
            detail={detail}
            neighbors={neighbors}
            onBranchSaved={() =>
              selected
                ? void openType(selected).catch((e) => setErr(String((e as Error).message || e)))
                : undefined
            }
            onMetaSaved={() =>
              void reloadTypes().catch((e) => setErr(String((e as Error).message || e)))
            }
          />
        </section>
      )}

      {selected && selectedMeta && composition && ECOM_OBJECT_TYPES.has(selected) && (
        <section className="ont-layer ont-block">
          <div className="mp-section-head">
            <div>
              <h2 className="bp-ws-section-title" style={{ margin: 0 }}>组织定制</h2>
              <p className="muted" style={{ margin: "0.35rem 0" }}>
                当前组织与工作区专属 · 安装版本 {composition.installation_revision} ·
                定制修订 {activeOverlay?.ontology_revision || 0} · 不反写平台模板
              </p>
            </div>
          </div>
          <label className="ont-form-field">
            <span>显示名</span>
            <input
              className="aos-input"
              value={overlayName}
              disabled={overlayBusy}
              onChange={(event) => setOverlayName(event.target.value)}
            />
          </label>
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <button
              type="button"
              className="btn-primary"
              disabled={overlayBusy || !overlayName.trim()}
              onClick={() => void saveOrganizationOverlay("override")}
            >
              {overlayBusy ? "保存中…" : "保存组织定制"}
            </button>
            <button
              type="button"
              className="btn"
              disabled={overlayBusy || !activeOverlay}
              onClick={() => void saveOrganizationOverlay("inherit")}
            >
              恢复安装模板
            </button>
          </div>
        </section>
      )}

      {/* 新建 · 默认展开 + 图标 */}
      <section className="ont-layer ont-layer-create">
        <button
          type="button"
          className="mp-collapse-toggle ont-create-toggle"
          onClick={() => setCreateOpen((v) => !v)}
        >
          <h2 className="ont-create-title">
            <span className="ont-create-icon" aria-hidden>
              ＋
            </span>
            {createOpen ? "收起 · 新建对象类型" : "新建对象类型"}
          </h2>
          <span className="mp-section-hint">{createOpen ? "▲" : "▼"}</span>
        </button>
        {createOpen && (
          <div className="ont-create-panel ont-block">
            <div className="ont-form-grid">
              <label className="ont-form-field">
                <span>类型标识（技术字段）</span>
                <input
                  className="aos-input"
                  value={newId}
                  onChange={(e) => setNewId(e.target.value)}
                  placeholder="SiteAsset"
                />
              </label>
              <label className="ont-form-field">
                <span>显示名称</span>
                <input className="aos-input" value={newName} onChange={(e) => setNewName(e.target.value)} />
              </label>
              <label className="ont-form-field ont-form-span">
                <span>业务说明</span>
                <input className="aos-input" value={newDesc} onChange={(e) => setNewDesc(e.target.value)} />
              </label>
              <label className="ont-form-field">
                <span>首个属性标识（技术字段）</span>
                <input
                  className="aos-input"
                  value={propName}
                  onChange={(e) => setPropName(e.target.value)}
                  placeholder="code"
                />
              </label>
              <label className="ont-form-check">
                <input type="checkbox" checked={publish} onChange={(e) => setPublish(e.target.checked)} />
                立即发布
              </label>
            </div>
            <button
              type="button"
              className="btn-primary"
              style={{ marginTop: 12 }}
              disabled={busy}
              onClick={() => void createType()}
            >
              {busy ? "创建中…" : "创建对象类型"}
            </button>
          </div>
        )}
      </section>
      </div>
    </PageChrome>
  );
}
