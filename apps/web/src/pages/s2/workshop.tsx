import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, S2Chrome, useJsonGet } from "./shared";
import {
  BpBanner,
  BpLinkRow,
  BpPropGrid,
  BpSplit,
  BpTable,
  BpToolbar,
} from "./blueprintUi";

type Neighbor = { id?: string; type?: string; rel?: string; title?: string };

/** 83 · 对齐 workshop-object-view · Graph + Object View + Wiki */
export function GraphExplorerPage() {
  const { data: types, err: tErr } = useJsonGet<{ items: { id: string; name: string }[] }>(
    "/v1/ontology/object-types",
  );
  const [typeId, setTypeId] = useState("WorkOrder");
  const [objects, setObjects] = useState<Record<string, unknown>[]>([]);
  const [objectId, setObjectId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [neighbors, setNeighbors] = useState<Neighbor[]>([]);
  const [wiki, setWiki] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [toast, setToast] = useState("");

  useEffect(() => {
    if (types?.items?.length && !types.items.some((t) => t.id === typeId)) {
      setTypeId(types.items[0].id);
    }
  }, [types, typeId]);

  useEffect(() => {
    void loadObjects(typeId);
  }, [typeId]);

  async function loadObjects(t: string) {
    setErr(null);
    setObjectId(null);
    setDetail(null);
    setNeighbors([]);
    setWiki(null);
    try {
      const r = await apiGet<{ items: Record<string, unknown>[] }>(`/v1/objects/${t}`);
      setObjects(r.items);
      if (r.items.length > 0) {
        await openObject(t, String(r.items[0].id));
      }
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function openObject(t: string, id: string) {
    setErr(null);
    setObjectId(id);
    setWiki(null);
    try {
      const d = await apiGet<Record<string, unknown>>(`/v1/objects/${t}/${id}`);
      const n = await apiGet<{ items: Neighbor[] }>(`/v1/objects/${t}/${id}/neighbors`);
      setDetail(d);
      setNeighbors(n.items || []);
      try {
        const w = await apiGet<{ body?: string }>(`/v1/wiki/${encodeURIComponent(t)}/${encodeURIComponent(id)}`);
        setWiki(w.body || null);
      } catch {
        setWiki(null);
      }
    } catch (e) {
      setErr(String((e as Error).message || e));
      setDetail(null);
      setNeighbors([]);
    }
  }

  const graphNodes = useMemo(() => {
    const center = detail
      ? { id: String(detail.id), label: String(detail.title || detail.id), kind: "center" as const }
      : null;
    const outer = neighbors.slice(0, 6).map((n, i) => ({
      id: String(n.id ?? i),
      label: String(n.title || n.id || n.type),
      rel: n.rel,
      kind: "neighbor" as const,
    }));
    return { center, outer };
  }, [detail, neighbors]);

  const detailProps =
    detail &&
    Object.entries(detail)
      .filter(([k]) => !k.startsWith("_"))
      .slice(0, 6)
      .map(([k, v]) => ({ label: k, value: String(v ?? "—") }));

  return (
    <S2Chrome title="知识图谱" lede="Object+Link 页面展示 · 邻接 1-hop · Selection 绑定 Object View">
      <BpToolbar>
        <span className="muted" style={{ fontSize: "0.75rem" }}>
          Selection ·{" "}
          <span className="aos-text">{detail ? String(detail.title || objectId) : "—"}</span> · 维数{" "}
          <span style={{ color: "#fcd34d" }}>{neighbors.length + (objectId ? 1 : 0)} / 10</span>
        </span>
        <label className="muted">
          类型{" "}
          <select value={typeId} onChange={(e) => setTypeId(e.target.value)}>
            {(types?.items || []).map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
        <Link to="/workshop/inbox" className="muted">
          Inbox →
        </Link>
      </BpToolbar>

      {(tErr || err) && <p className="error">{tErr || err}</p>}
      {toast && <p className="aos-text">{toast}</p>}

      <BpSplit
        left={
          <div className="bp-graph-canvas">
            <p className="muted" style={{ fontSize: "0.75rem", marginBottom: "0.75rem" }}>
              知识图谱 · 边=Link · 节点=Object · 高亮 1-hop 传导
            </p>
            <div className="bp-graph-stage">
              {graphNodes.center && (
                <button
                  type="button"
                  className="bp-graph-node bp-graph-node-center"
                  onClick={() => setToast(`中心节点 ${graphNodes.center!.label}`)}
                >
                  {graphNodes.center.label}
                </button>
              )}
              {graphNodes.outer.map((n, i) => {
                const positions = [
                  "bp-graph-pos-n",
                  "bp-graph-pos-e",
                  "bp-graph-pos-s",
                  "bp-graph-pos-w",
                  "bp-graph-pos-ne",
                  "bp-graph-pos-nw",
                ];
                return (
                  <button
                    key={n.id}
                    type="button"
                    className={`bp-graph-node ${positions[i % positions.length]}`}
                    onClick={() =>
                      void openObject(String(n.type || typeId), n.id).catch((e) =>
                        setErr(String(e.message || e)),
                      )
                    }
                    title={n.rel}
                  >
                    {n.label}
                    {n.rel && (
                      <span className="muted" style={{ display: "block", fontSize: "0.6rem" }}>
                        {n.rel}
                      </span>
                    )}
                  </button>
                );
              })}
              {!graphNodes.center && (
                <p className="muted" style={{ textAlign: "center" }}>暂无实例 · 请到数据连接接入源</p>
              )}
            </div>
            <ul className="card-list" style={{ marginTop: "1rem" }}>
              {objects.map((o) => (
                <li key={String(o.id)} className="card">
                  <button
                    type="button"
                    className={objectId === String(o.id) ? "nav-link active" : "nav-link"}
                    onClick={() => void openObject(typeId, String(o.id))}
                  >
                    {String(o.id)} · {String(o.title || "")}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        }
        right={
          <div className="bp-cop-sidebar">
            <div className="bp-ws-section-title">Object View + Wiki</div>
            {detail ? (
              <>
                <div className="bp-object-title">{String(detail.title || detail.id)}</div>
                <p className="muted" style={{ fontSize: "0.75rem" }}>
                  {typeId}/{objectId} · Selection 绑定
                </p>
                {wiki ? (
                  <div className="bp-domain bp-domain-wiki" style={{ padding: "0.75rem", margin: "0.75rem 0" }}>
                    <div style={{ color: "#fb923c", fontSize: "0.7rem", marginBottom: 4 }}>🟣 Wiki</div>
                    <p className="muted" style={{ fontSize: "0.8rem", margin: 0 }}>{wiki.slice(0, 200)}</p>
                  </div>
                ) : (
                  <p className="muted" style={{ fontSize: "0.75rem" }}>
                    暂无 Wiki 页 · <Link to="/ontology/wiki">去 Wiki</Link>
                  </p>
                )}
                {detailProps && <BpPropGrid items={detailProps} />}
                {neighbors.length > 0 && (
                  <BpTable
                    columns={["邻居", "type", "rel"]}
                    rows={neighbors.map((n) => [
                      String(n.id ?? "—"),
                      String(n.type ?? "—"),
                      String(n.rel ?? "—"),
                    ])}
                  />
                )}
                <div className="bp-object-actions">
                  <Link to="/aip/drafts" className="btn">
                    立案 Action 🟡
                  </Link>
                  <Link to="/ontology/wiki" className="btn">
                    Wiki 全页
                  </Link>
                  <Link
                    to={
                      objectId
                        ? `/workshop/buddy?order=${encodeURIComponent(objectId)}&assist=1`
                        : "/workshop/buddy"
                    }
                    className="btn"
                  >
                    @Buddy
                  </Link>
                </div>
              </>
            ) : (
              <p className="muted">选择左侧实例查看 Object View</p>
            )}
            <p className="muted" style={{ fontSize: "0.65rem", marginTop: "1rem" }}>
              硬约束：顶层须 Action；不可「仅调 Logic」写回 Ontology。
            </p>
          </div>
        }
      />

      <BpLinkRow
        links={[
          { to: "/ontology", label: "本体管理" },
          { to: "/ontology/graph-health", label: "图谱健康" },
          { to: "/workshop/inbox", label: "运营 Inbox" },
        ]}
      />
    </S2Chrome>
  );
}

type WebhookRow = { id?: string; url?: string; event?: string; status?: string };

/** 83 · 对齐 workshop-events · 触发器表 + 幂等护栏 */
export function EventsPage() {
  const { data, err, reload } = useJsonGet<{ items: WebhookRow[] }>("/v1/actions/webhooks");
  const [msg, setMsg] = useState("");

  async function register() {
    await apiPost("/v1/actions/webhooks", {
      url: "http://127.0.0.1:9999/hook",
      event: "action.approved",
    });
    setMsg("已注册 Demo webhook");
    reload();
  }

  const blueprintRows = [
    ["表格行选中 onSelect", "写入变量", "selectedWorkOrderId", "● 已启用"],
    ["按钮「派单」onClick", "调用 Action", "assignWorkOrder", "● idempotencyKey"],
    ["筛选器 onChange", "刷新数据集", "inboxFilter", "—"],
  ];

  const apiRows = (data?.items || []).map((w) => [
    w.event || "webhook",
    "HTTP 回调",
    w.url || "—",
    w.status === "registered" ? "● 已注册" : String(w.status || "—"),
  ]);

  return (
    <S2Chrome title="Events 配置面板" lede="Widget 事件绑定、变量写入与幂等键配置。">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => void register().catch((e) => setMsg(String(e)))}>
          + 注册 Demo Webhook
        </button>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <Link to="/workshop/canvas" className="muted">
          画布配置 →
        </Link>
      </BpToolbar>
      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}

      <div className="bp-object-panel">
        <div className="bp-ws-section-title">已注册事件</div>
        <BpTable columns={["触发器", "动作", "目标变量", "幂等"]} rows={[...blueprintRows, ...apiRows]} />
      </div>

      <BpBanner tone="warn">
        <strong>幂等护栏</strong> · 写操作事件须配置 idempotencyKey，防止双击重复提交（对齐 ACT-07）。
      </BpBanner>
    </S2Chrome>
  );
}
