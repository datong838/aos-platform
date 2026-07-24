import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
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
  instanceCount: number;
  funnelStage?: string;
  published?: boolean;
};

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
  const [createOpen, setCreateOpen] = useState(true);
  const [recent, setRecent] = useState<RecentEntry[]>(() => loadRecent());
  const [favoriteIds, setFavoriteIds] = useState<string[] | null>(() => loadFavorites());
  const [linkTypes, setLinkTypes] = useState<{ id: string; name: string; rel?: string; srcType?: string; dstType?: string }[]>([]);
  const [actionTypes, setActionTypes] = useState<{ id: string; name: string; objectType?: string }[]>([]);

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
      let instanceCount = 0;
      let funnelStage: string | undefined;
      try {
        const list = await getOntologyClient().listObjects(t.id);
        instanceCount = list.items?.length ?? 0;
      } catch {
        instanceCount = 0;
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
      apiGet<{ items: ObjectTypeRow[] }>("/v1/ontology/object-types"),
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
    return typeStats.slice(0, 3);
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
      setErr("请填写 Object Type id");
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
          (res.lint && res.lint.ok === false ? " · lint 有告警" : publish ? " · 已发布" : " · 草稿"),
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
    if (/index|live|done/i.test(stage)) return { label: stage, tone: "ok" };
    if (/error|fail/i.test(stage)) return { label: stage, tone: "bad" };
    return { label: stage, tone: "warn" };
  }


  const selectedMeta = types.find((t) => t.id === selected);
  const selectedStats = typeStats.find((s) => s.id === selected);

  return (
    <PageChrome title="本体管理（数字孪生）" lede="发现 · 收藏 / 最近 / 重要 Object。">
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
          placeholder="搜索 Object / Link / Action…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button
          type="button"
          className="btn ont-toolbar-refresh"
          title="重新拉取 Object Type、分支与图谱健康"
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
            aria-label="branch"
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
          OKF 映射
        </Link>
        <Link
          to="/ontology/branches"
          className="btn-nav"
          onClick={() => recordRecentLink("branches", "分支管理", "/ontology/branches")}
        >
          分支管理
        </Link>
        <Link
          to="/ontology/funnel"
          className="btn-nav"
          onClick={() =>
            recordRecentLink("funnel-wo", "Funnel · WorkOrder Live Pipeline", "/ontology/funnel")
          }
        >
          漏斗管道
        </Link>
        <Link
          to="/ontology/wiki"
          className="btn-nav"
          onClick={() =>
            recordRecentLink("wiki-wo-1001", "Wiki · WorkOrder/wo-1001", "/ontology/wiki")
          }
        >
          活知识 Wiki
        </Link>
        <Link to="/ontology/link-types/new" className="btn-nav">
          新建 Link Type
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
          {!favoriteIds && (
            <p className="muted" style={{ margin: "0 0 0.5rem", fontSize: "0.8rem" }}>
              尚未配置收藏 · 下方为预览；在「重要」表点 ⭐ 收藏后会持久化到本机
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
                  meta={`${t.instanceCount} 实例 · ${t.id}${t.published ? " · 已发布" : ""}`}
                  cta="打开 Overview →"
                  onClick={() => openDeep(t.id)}
                />
              </div>
            ))}
            {favorites.length === 0 && (
              <div className="ont-block ont-block-empty">
                <p className="muted" style={{ margin: 0 }}>
                  暂无 Object Type
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
                <span className="muted">打开 Object Type 或漏斗/Wiki 后会出现在这里</span>
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
              columns={["Object Type", "实例", "Funnel", "发布", ""]}
              rows={filteredTypes.map((t) => {
                const st = typeStats.find((s) => s.id === t.id);
                return [
                  t.name,
                  String(st?.instanceCount ?? "—"),
                  st?.funnelStage ? (
                    <span className={/error/i.test(st.funnelStage) ? "bp-prop-warn" : "bp-prop-ok"}>
                      {st.funnelStage}
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
                    Link Type 命中
                  </h4>
                  <BpTable
                    columns={["id", "name", "rel", ""]}
                    rows={filteredLinks.slice(0, 8).map((l) => [
                      l.id,
                      l.name,
                      l.rel || "—",
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
                    Action Type 命中
                  </h4>
                  <BpTable
                    columns={["id", "name", "objectType", ""]}
                    rows={filteredActions.slice(0, 8).map((a) => [
                      a.id,
                      a.name,
                      a.objectType || "—",
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
            <span>OKF 映射 → Overview 确认 → Funnel 四阶段 → Workshop</span>
          </p>
          <div className="ont-hydrate-actions">
            <Link to="/ontology/okf-funnel" className="btn-nav">
              ① OKF
            </Link>
            <Link to="/ontology/funnel" className="btn-nav">
              ② Funnel
            </Link>
            <Link to="/workshop/inbox" className="btn-nav">
              ③ Workshop
            </Link>
          </div>
        </div>
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
            {createOpen ? "收起 · 新建 Object Type" : "新建 Object Type"}
          </h2>
          <span className="mp-section-hint">{createOpen ? "▲" : "▼"}</span>
        </button>
        {createOpen && (
          <div className="ont-create-panel ont-block">
            <div className="ont-form-grid">
              <label className="ont-form-field">
                <span>id</span>
                <input
                  className="aos-input"
                  value={newId}
                  onChange={(e) => setNewId(e.target.value)}
                  placeholder="SiteAsset"
                />
              </label>
              <label className="ont-form-field">
                <span>name</span>
                <input className="aos-input" value={newName} onChange={(e) => setNewName(e.target.value)} />
              </label>
              <label className="ont-form-field ont-form-span">
                <span>description</span>
                <input className="aos-input" value={newDesc} onChange={(e) => setNewDesc(e.target.value)} />
              </label>
              <label className="ont-form-field">
                <span>property</span>
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
              {busy ? "创建中…" : "创建 Object Type"}
            </button>
          </div>
        )}
      </section>
      </div>
    </PageChrome>
  );
}
