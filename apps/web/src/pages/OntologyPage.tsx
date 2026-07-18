import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import {
  BpBanner,
  BpDiscoverCard,
  BpLinkRow,
  BpSplit,
  BpTable,
  BpToolbar,
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

/** 80 · 对齐 ontology.html Discover + 浏览实例 + 创建 OT */
export function OntologyPage() {
  const [types, setTypes] = useState<ObjectTypeRow[]>([]);
  const [typeStats, setTypeStats] = useState<TypeStats[]>([]);
  const [objects, setObjects] = useState<Record<string, unknown>[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [neighbors, setNeighbors] = useState<{ id?: string; type?: string; rel?: string }[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [branchId, setBranchId] = useState("main");
  const [search, setSearch] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const [newId, setNewId] = useState("");
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [propName, setPropName] = useState("code");
  const [publish, setPublish] = useState(false);
  const [busy, setBusy] = useState(false);

  const loadStats = useCallback(async (items: ObjectTypeRow[]) => {
    const stats: TypeStats[] = [];
    for (const t of items) {
      let instanceCount = 0;
      let funnelStage: string | undefined;
      try {
        const list = await apiGet<{ items: unknown[] }>(`/v1/objects/${encodeURIComponent(t.id)}`);
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
    const [t, b, h] = await Promise.all([
      apiGet<{ items: ObjectTypeRow[] }>("/v1/ontology/object-types"),
      apiGet<{ items: Branch[] }>("/v1/ontology/branches"),
      apiGet<Health>("/v1/ontology/graph-health"),
    ]);
    setTypes(t.items);
    setBranches(b.items);
    setHealth(h);
    if (b.items.length && !b.items.some((x) => x.id === branchId)) {
      setBranchId(b.items[0].id);
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

  const favorites = useMemo(() => {
    const wo = typeStats.find((s) => s.id === "WorkOrder");
    const rest = typeStats.filter((s) => s.id !== "WorkOrder").slice(0, 2);
    return wo ? [wo, ...rest] : typeStats.slice(0, 3);
  }, [typeStats]);

  async function openType(id: string, branch = branchId) {
    setSelected(id);
    setDetail(null);
    setNeighbors([]);
    setErr(null);
    const q = branch ? `?branch=${encodeURIComponent(branch)}` : "";
    const list = await apiGet<{ items: Record<string, unknown>[] }>(
      `/v1/objects/${encodeURIComponent(id)}${q}`,
    );
    setObjects(list.items);
  }

  async function onBranchChange(next: string) {
    setBranchId(next);
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
    const d = await apiGet<Record<string, unknown>>(`/v1/objects/${type}/${id}`);
    setDetail(d);
    const n = await apiGet<{ items: { id?: string; type?: string; rel?: string }[] }>(
      `/v1/objects/${type}/${id}/neighbors`,
    );
    setNeighbors(n.items);
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
      await reloadTypes();
      await openType(res.id);
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
    <PageChrome
      title="Ontology Manager"
      lede="Discover · 收藏 / 最近 / 重要 Object · 分支浏览 · 创建 Object Type"
    >
      <BpToolbar>
        <input
          type="search"
          placeholder="搜索 Object / Link / Action…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ minWidth: "14rem" }}
        />
        <label className="muted">
          分支{" "}
          <select aria-label="branch" value={branchId} onChange={(e) => void onBranchChange(e.target.value)}>
            {branches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
                {b.readonly ? " (只读)" : ""}
              </option>
            ))}
          </select>
        </label>
        {health && (
          <span className="muted">
            图谱健康 {health.score} · instances={String(health.metrics.instances ?? "—")}
          </span>
        )}
      </BpToolbar>

      <BpLinkRow
        links={[
          { to: "/ontology/branches", label: "分支管理" },
          { to: "/ontology/okf-funnel", label: "OKF 映射" },
          { to: "/ontology/funnel", label: "Funnel" },
          { to: "/ontology/wiki", label: "Wiki" },
          { to: "/ontology/graph-health", label: "图谱健康" },
        ]}
      />

      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}

      <section style={{ marginTop: "1.25rem" }}>
        <h2 className="bp-section-label">⭐ 收藏</h2>
        <div className="bp-discover-grid">
          {favorites.map((t, i) => (
            <BpDiscoverCard
              key={t.id}
              accent={i === 0 ? "violet" : "muted"}
              title={t.name}
              badge={funnelBadge(t.funnelStage)}
              meta={`${t.instanceCount} 实例 · ${t.id}${t.published ? " · 已发布" : ""}`}
              cta="浏览实例 →"
              onClick={() => void openType(t.id).catch((e) => setErr(String(e.message || e)))}
            />
          ))}
          {favorites.length === 0 && <p className="muted">暂无 Object Type</p>}
        </div>
      </section>

      <section>
        <h2 className="bp-section-label">🕐 最近查看</h2>
        <ul className="bp-recent-list">
          <li>
            <Link to="/ontology/funnel">Funnel · WorkOrder Live Pipeline</Link>
            <span className="muted" style={{ fontSize: "0.75rem" }}>
              可点
            </span>
          </li>
          <li>
            <Link to="/ontology/wiki">Wiki · WorkOrder/wo-1001</Link>
            <span className="muted" style={{ fontSize: "0.75rem" }}>
              活知识
            </span>
          </li>
          <li>
            <Link to="/workshop/inbox">Workshop · 运营 Inbox</Link>
            <span className="muted" style={{ fontSize: "0.75rem" }}>
              写回链
            </span>
          </li>
        </ul>
      </section>

      <section>
        <h2 className="bp-section-label">📌 重要 / 最近修改</h2>
        <BpTable
          columns={["Object Type", "实例", "Funnel", "发布", ""]}
          rows={typeStats.map((t) => [
            t.name,
            String(t.instanceCount),
            t.funnelStage ? (
              <span className={/error/i.test(t.funnelStage) ? "bp-prop-warn" : ""}>{t.funnelStage}</span>
            ) : (
              "—"
            ),
            t.published ? "✅" : "草稿",
            <button
              key={`open-${t.id}`}
              type="button"
              className="nav-link"
              onClick={() => void openType(t.id).catch((e) => setErr(String(e.message || e)))}
            >
              浏览
            </button>,
          ])}
        />
      </section>

      <div className="bp-hydration-banner">
        <div>
          <div style={{ fontSize: "0.7rem", color: "#34d399", marginBottom: 4 }}>标准水合</div>
          <p className="muted" style={{ margin: 0, fontSize: "0.875rem" }}>
            OKF 映射 → Overview 确认 → Funnel 四阶段 → Workshop
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Link to="/ontology/okf-funnel" className="btn">
            ① OKF
          </Link>
          <Link to="/ontology/funnel" className="btn">
            ② Funnel
          </Link>
          <Link to="/workshop/inbox" className="btn">
            ③ Workshop
          </Link>
        </div>
      </div>

      <h2 className="bp-ws-section-title" style={{ marginTop: "1.5rem" }}>
        Object Type 详情
      </h2>
      {selected && selectedMeta ? (
        <ObjectTypeDetailPanel
          typeId={selected}
          typeName={selectedMeta.name}
          description={selectedMeta.description}
          published={selectedMeta.published}
          properties={selectedMeta.properties}
          branchId={branchId}
          instanceCount={selectedStats?.instanceCount ?? objects.length}
          funnelStage={selectedStats?.funnelStage}
          objects={objects}
          onOpenInstance={(id) =>
            void openObject(selected, id).catch((e) => setErr(String(e.message || e)))
          }
          detail={detail}
          neighbors={neighbors}
        />
      ) : (
        <p className="muted">从上方收藏/表格或下方列表选择 Object Type 查看 7 Tab 详情</p>
      )}

      <h2 className="bp-ws-section-title" style={{ marginTop: "1.5rem" }}>
        快速切换
      </h2>
      <BpSplit
        left={
          <>
            <div className="bp-ws-section-title">Object Types</div>
            <ul className="card-list">
              {filteredTypes.map((t) => (
                <li key={t.id} className="card">
                  <button
                    type="button"
                    className={selected === t.id ? "nav-link active" : "nav-link"}
                    onClick={() => void openType(t.id).catch((e) => setErr(String(e.message || e)))}
                  >
                    {t.name} <span className="muted">({t.id})</span>
                  </button>
                </li>
              ))}
            </ul>
          </>
        }
        right={
          selected ? (
            <p className="muted">实例与邻居见上方 Data Tab</p>
          ) : (
            <p className="muted">选择类型查看 7 Tab 详情</p>
          )
        }
      />

      <BpBanner tone="info">
        <strong>新建 Object Type</strong>
        <div style={{ marginTop: 8 }}>
          <label className="muted" style={{ display: "block" }}>
            id{" "}
            <input value={newId} onChange={(e) => setNewId(e.target.value)} placeholder="SiteAsset" />
          </label>
          <label className="muted" style={{ display: "block", marginTop: 6 }}>
            name <input value={newName} onChange={(e) => setNewName(e.target.value)} />
          </label>
          <label className="muted" style={{ display: "block", marginTop: 6 }}>
            description <input value={newDesc} onChange={(e) => setNewDesc(e.target.value)} />
          </label>
          <label className="muted" style={{ display: "block", marginTop: 6 }}>
            property{" "}
            <input value={propName} onChange={(e) => setPropName(e.target.value)} placeholder="code" />
          </label>
          <label className="muted" style={{ display: "block", marginTop: 6 }}>
            <input type="checkbox" checked={publish} onChange={(e) => setPublish(e.target.checked)} /> 立即发布
          </label>
          <button type="button" className="btn" style={{ marginTop: 8 }} disabled={busy} onClick={() => void createType()}>
            {busy ? "创建中…" : "创建"}
          </button>
        </div>
      </BpBanner>
    </PageChrome>
  );
}
