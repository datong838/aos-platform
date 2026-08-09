import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getOntologyClient } from "../../api/ontologyClient";
import {
  buildExplorerSearchParams,
  ObjectExplorerWorkspace,
  resolveExplorerColumns,
  toggleObjectSelection,
} from "../../components/ontology/ObjectExplorerWorkspace";
import { apiGet, apiPost, S2Chrome, useJsonGet } from "./shared";
import {
  BpBanner,
  BpLinkRow,
  BpPropGrid,
  BpTable,
  BpToolbar,
} from "./blueprintUi";

type Neighbor = { id?: string; type?: string; rel?: string; title?: string };
type ObjectTypeSummary = {
  id: string;
  name: string;
  properties?: unknown;
};

type ExplorerGraphNode = {
  key: string;
  id: string;
  type: string;
  label: string;
  rel?: string;
  kind: "center" | "neighbor";
};

export function buildGraphNodes(
  detail: Record<string, unknown> | null,
  neighbors: Neighbor[],
  centerType: string,
): { center: ExplorerGraphNode | null; outer: ExplorerGraphNode[] } {
  const center = detail
    ? {
        key: `${centerType}:${String(detail.id)}`,
        id: String(detail.id),
        type: centerType,
        label: String(detail.title || detail.id),
        kind: "center" as const,
      }
    : null;
  const outer = neighbors.slice(0, 6).map((neighbor, index) => {
    const id = String(neighbor.id ?? index);
    const type = String(neighbor.type || centerType);
    const rel = neighbor.rel ? String(neighbor.rel) : undefined;
    return {
      key: `${type}:${id}:${rel || index}`,
      id,
      type,
      label: String(neighbor.title || neighbor.id || neighbor.type || id),
      rel,
      kind: "neighbor" as const,
    };
  });
  return { center, outer };
}

export function resolveObjectSelectionId(
  items: Record<string, unknown>[],
  requestedId: string | null | undefined,
): string | null {
  if (!requestedId) return items.length > 0 ? String(items[0].id) : null;
  const exact = items.find((item) => String(item.id) === requestedId);
  if (exact) return String(exact.id);
  const byAuthority = items.find((item) => {
    const identity = item._sourceIdentity;
    if (!identity || typeof identity !== "object") return false;
    const source = identity as Record<string, unknown>;
    return String(source.externalId || source.external_id || "") === requestedId;
  });
  if (byAuthority) return String(byAuthority.id);
  const canonicalParts = requestedId.split(":");
  if (requestedId.startsWith("niushop:") && canonicalParts.length >= 3) {
    const sourcePk = canonicalParts.slice(2).join(":");
    const bySourcePk = items.find((item) => String(item.id) === sourcePk);
    if (bySourcePk) return String(bySourcePk.id);
  }
  return items.length > 0 ? String(items[0].id) : null;
}

/** 83 · 对齐 Object Explorer · 标签+搜索+视图栏+表格+Object View 侧边栏 */
export function GraphExplorerPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { data: types, err: tErr } = useJsonGet<{ items: ObjectTypeSummary[] }>(
    "/v1/ontology/object-types",
  );
  const [typeId, setTypeId] = useState(searchParams.get("type")?.trim() || "Order");
  const [objects, setObjects] = useState<Record<string, unknown>[]>([]);
  const [objectId, setObjectId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [neighbors, setNeighbors] = useState<Neighbor[]>([]);
  const [wiki, setWiki] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [toast, setToast] = useState("");
  const [query, setQuery] = useState("");
  const [viewMode, setViewMode] = useState<"table" | "graph">("table");
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [detailOpen, setDetailOpen] = useState(false);
  const [focusMode, setFocusMode] = useState(false);
  const [detailTab, setDetailTab] = useState<
    "overview" | "properties" | "relations" | "wiki" | "action" | "timeline"
  >("overview");

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
    setDetailOpen(false);
    setSelectedKeys([]);
    try {
      const r = await getOntologyClient().listObjects(t);
      setObjects((r.items || []) as Record<string, unknown>[]);
      const requestedId = searchParams.get("id")?.trim();
      if (r.items.length > 0 && requestedId) {
        const selected = resolveObjectSelectionId(
          r.items as Record<string, unknown>[],
          requestedId,
        );
        if (selected) await openObject(t, selected);
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
      const ont = getOntologyClient();
      const d = await ont.getObject(t, id);
      const n = (await ont.neighbors(t, id)) as { items?: Neighbor[] };
      setDetail(d as Record<string, unknown>);
      setSearchParams(buildExplorerSearchParams(t, id, searchParams), { replace: true });
      setNeighbors(n.items || []);
      setDetailOpen(true);
      setDetailTab("overview");
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

  const graphNodes = useMemo(
    () => buildGraphNodes(detail, neighbors, typeId),
    [detail, neighbors, typeId],
  );

  function selectObject(nextType: string, nextId: string) {
    if (nextType === typeId) {
      void openObject(nextType, nextId);
      return;
    }
    setSearchParams({ type: nextType, id: nextId }, { replace: true });
    setTypeId(nextType);
  }

  const allDetailProps =
    detail &&
    Object.entries(detail)
      .filter(([k]) => !k.startsWith("_"))
      .map(([k, v]) => ({ label: k, value: String(v ?? "—") }));
  const detailProps = allDetailProps && allDetailProps.slice(0, 6);

  const currentType = types?.items?.find((t) => t.id === typeId);
  const currentTypeName = currentType?.name || typeId;

  const filteredObjects = useMemo(() => {
    if (!query.trim()) return objects;
    const q = query.toLowerCase();
    return objects.filter((o) =>
      String(o.title || o.id || "").toLowerCase().includes(q),
    );
  }, [objects, query]);

  const columnResolution = useMemo(
    () => resolveExplorerColumns(currentType?.properties, objects),
    [currentType?.properties, objects],
  );
  const objectColumns = columnResolution.columns;
  const allVisibleKeys = filteredObjects.map((object) => `${typeId}:${String(object.id)}`);
  const allVisibleSelected =
    allVisibleKeys.length > 0 && allVisibleKeys.every((key) => selectedKeys.includes(key));

  return (
    <S2Chrome title="对象探索" lede="Object Explorer · 按类型浏览对象 · Selection 绑定 Object View + Wiki">
      <div className="p-objx-app">
        {/* 标签栏 */}
        <div className="p-objx-tabs-bar">
          <div className="p-objx-tab is-active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.3-4.3" />
            </svg>
            {currentTypeName}
          </div>
        </div>

        {/* 搜索栏 */}
        <div className="p-objx-search-bar">
          <div className="p-objx-search-left">
            <div className="p-objx-type-pill">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
              </svg>
              {currentTypeName}
            </div>
            <div className="p-objx-search-field">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <path d="m21 21-4.3-4.3" />
              </svg>
              <input
                type="text"
                placeholder={`搜索 ${currentTypeName}...`}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <label className="muted">
              类型
              <select value={typeId} onChange={(e) => setTypeId(e.target.value)}>
                {(types?.items || []).map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {/* 视图栏 */}
        <div className="p-objx-view-bar">
          <div className="p-objx-view-left">
            <button
              type="button"
              className={`p-objx-view-btn ${viewMode === "table" ? "is-active" : ""}`}
              onClick={() => setViewMode("table")}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M3 9h18" />
                <path d="M3 15h18" />
                <path d="M9 3v18" />
                <path d="M15 3v18" />
              </svg>
              表格
            </button>
            <button
              type="button"
              className={`p-objx-view-btn ${viewMode === "graph" ? "is-active" : ""}`}
              onClick={() => setViewMode("graph")}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="5" r="3" />
                <circle cx="5" cy="19" r="3" />
                <circle cx="19" cy="19" r="3" />
                <path d="M12 8v8M9.5 16.5l-2.5 1M14.5 16.5l2.5 1" />
              </svg>
              图谱
            </button>
          </div>
          <div className="p-objx-view-center">
            <span className="p-objx-results-count">{filteredObjects.length} 条结果</span>
            {selectedKeys.length > 0 && (
              <span className="p-objx-selection-count">已选择 {selectedKeys.length} 条</span>
            )}
          </div>
        </div>

        {columnResolution.schemaIncomplete && viewMode === "table" && (
          <div className="p-objx-schema-warning" role="status">
            当前 Object Type 的属性 Schema 元数据不完整，暂按全部已加载对象的字段并集展示；不会从第一行猜列。
          </div>
        )}

        {/* 主体：默认全宽主画布，选择对象后按需打开详情抽屉 */}
        <ObjectExplorerWorkspace
          detailOpen={detailOpen && Boolean(detail)}
          focusMode={focusMode}
          onCloseDetail={() => setDetailOpen(false)}
          onToggleFocus={() => setFocusMode((value) => !value)}
          canvas={
            viewMode === "table" ? (
              <div className="p-objx-table-wrap">
                <table className="p-objx-table">
                  <thead>
                    <tr>
                      <th className="p-objx-check">
                        <input
                          type="checkbox"
                          aria-label="选择当前页全部对象"
                          checked={allVisibleSelected}
                          onChange={() =>
                            setSelectedKeys((current) =>
                              allVisibleSelected
                                ? current.filter((key) => !allVisibleKeys.includes(key))
                                : [...new Set([...current, ...allVisibleKeys])],
                            )
                          }
                        />
                      </th>
                      {objectColumns.map((col) => (
                        <th key={col.key} title={[col.type, col.unit, col.pii ? "PII" : ""].filter(Boolean).join(" · ")}>
                          {col.label}
                          {col.pii ? " · 已脱敏" : ""}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredObjects.map((o) => (
                      <tr
                        key={String(o.id)}
                        className={objectId === String(o.id) ? "is-current" : ""}
                        onClick={() => void openObject(typeId, String(o.id))}
                      >
                        <td className="p-objx-check">
                          <input
                            type="checkbox"
                            aria-label={`选择 ${typeId}/${String(o.id)}`}
                            checked={selectedKeys.includes(`${typeId}:${String(o.id)}`)}
                            onClick={(event) => event.stopPropagation()}
                            onChange={() =>
                              setSelectedKeys((current) =>
                                toggleObjectSelection(current, `${typeId}:${String(o.id)}`),
                              )
                            }
                          />
                        </td>
                        {objectColumns.map((col, idx) => (
                          <td key={col.key}>
                            {idx === 0 ? (
                              <div className="p-objx-cell-title">
                                <div className="p-objx-avatar">
                                  {String(o[col.key] || "?").charAt(0).toUpperCase()}
                                </div>
                                {String(o[col.key] ?? "—")}
                              </div>
                            ) : (
                              String(o[col.key] ?? "—")
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                    {filteredObjects.length === 0 && (
                      <tr>
                        <td colSpan={objectColumns.length + 1} style={{ textAlign: "center", padding: "2rem" }}>
                          <span className="muted">暂无对象 · 请到数据源管理接入源</span>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            ) : (
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
                        key={n.key}
                        type="button"
                        className={`bp-graph-node ${positions[i % positions.length]}`}
                        onClick={() => selectObject(n.type, n.id)}
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
                    <p className="muted" style={{ textAlign: "center" }}>暂无实例 · 请到数据源管理接入源</p>
                  )}
                </div>
              </div>
            )
          }
          detail={
            <div className="bp-cop-sidebar">
              <div className="bp-ws-section-title">Object View + Wiki</div>
              {detail ? (
                <>
                  <div className="bp-object-title">{String(detail.title || detail.id)}</div>
                  <p className="muted" style={{ fontSize: "0.75rem" }}>
                    {typeId}/{objectId} · Selection 绑定
                  </p>
                  <div className="p-objx-detail-tabs" role="tablist" aria-label="对象详情视图">
                    {(
                      [
                        ["overview", "概览"],
                        ["properties", "属性"],
                        ["relations", "关系"],
                        ["wiki", "Wiki"],
                        ["action", "Action"],
                        ["timeline", "时间线"],
                      ] as const
                    ).map(([key, label]) => (
                      <button
                        key={key}
                        type="button"
                        role="tab"
                        aria-selected={detailTab === key}
                        className={detailTab === key ? "is-active" : ""}
                        onClick={() => setDetailTab(key)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  {detailTab === "overview" && detailProps && <BpPropGrid items={detailProps} />}
                  {detailTab === "properties" && allDetailProps && <BpPropGrid items={allDetailProps} />}
                  {detailTab === "relations" &&
                    (neighbors.length > 0 ? (
                      <BpTable
                        columns={["邻居", "type", "rel"]}
                        rows={neighbors.map((n) => [
                          String(n.id ?? "—"),
                          String(n.type ?? "—"),
                          String(n.rel ?? "—"),
                        ])}
                      />
                    ) : (
                      <p className="muted">当前对象暂无可见关系。</p>
                    ))}
                  {detailTab === "wiki" &&
                    (wiki ? (
                      <div className="bp-domain bp-domain-wiki p-objx-wiki-preview">
                        <div>Wiki · 当前生效内容</div>
                        <p>{wiki.slice(0, 500)}</p>
                        <Link to={`/ontology/wiki?type=${encodeURIComponent(typeId)}&id=${encodeURIComponent(String(objectId || ""))}`}>
                          打开 Wiki 全页
                        </Link>
                      </div>
                    ) : (
                      <p className="muted">
                        当前对象暂无 Wiki。UX1 保持只读，不在此处伪造创建成功。
                      </p>
                    ))}
                  {detailTab === "action" && (
                    <p className="muted">对象级受控 Action 将在 UA2/UX5 接入；当前不展示无目标绑定的假动作。</p>
                  )}
                  {detailTab === "timeline" && (
                    <p className="muted">可审计任务、Action、版本和 Evidence 时间线将在 UA2 后接入。</p>
                  )}
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
      </div>

      {(tErr || err) && <p className="error">{tErr || err}</p>}
      {toast && <p className="aos-text">{toast}</p>}

      <BpLinkRow
        links={[
          { to: "/ontology", label: "本体管理" },
          { to: "/ontology/graph-health", label: "图谱健康" },
          { to: "/workshop/inbox", label: "风险告警 Inbox" },
        ]}
      />
    </S2Chrome>
  );
}

type WebhookRow = { id?: string; url?: string; event?: string; status?: string };
type OutboxRow = {
  id?: string;
  channel?: string;
  ok?: boolean;
  status?: string;
  pluginId?: string;
};
type ChannelPlugin = {
  id: string;
  nameZh?: string;
  name?: string;
  installed?: boolean;
  runtime?: string;
};

/** 218m · outbox 表格行文案 */
export function formatOutboxRow(row: OutboxRow): {
  id: string;
  channel: string;
  result: string;
  status: string;
} {
  const id = String(row.id || "—");
  const channel = String(row.channel || row.pluginId || "—");
  const result = row.ok === true ? "ok" : row.ok === false ? "fail" : "—";
  const status = String(row.status || "—");
  return { id, channel, result, status };
}

/** 83/101 · 对齐 workshop-events · 通道插件 + Webhook 持久化 · 218m outbox */
export function EventsPage() {
  const { data, err, reload } = useJsonGet<{ items: WebhookRow[] }>("/v1/actions/webhooks");
  const channelsApi = useJsonGet<{ items: ChannelPlugin[] }>("/v1/channel-plugins");
  const outboxApi = useJsonGet<{ items: OutboxRow[]; count?: number }>("/v1/channels/outbox");
  const [msg, setMsg] = useState("");
  const [hookUrl, setHookUrl] = useState("http://127.0.0.1:9999/hook");
  const [hookEvent, setHookEvent] = useState("action.approved");

  async function register() {
    await apiPost("/v1/actions/webhooks", {
      url: hookUrl.trim() || "http://127.0.0.1:9999/hook",
      event: hookEvent.trim() || "action.approved",
    });
    setMsg("已注册 webhook（已持久化）");
    reload();
  }

  async function sendWebhookDry() {
    const r = await apiPost<{ ok?: boolean; matched?: number }>("/v1/channels/channel-webhook/send", {
      event: hookEvent.trim() || "action.approved",
      body: { ping: true },
    });
    setMsg(`通道投递 · matched=${r.matched ?? 0} · ok=${String(r.ok)}`);
    outboxApi.reload();
  }

  async function installChannel(id: string) {
    await apiPost(`/v1/channel-plugins/${encodeURIComponent(id)}/install`, {});
    setMsg(`已安装通道 ${id}`);
    channelsApi.reload();
  }

  async function retryOutbox(id: string) {
    const r = await apiPost<{ ok?: boolean; retriedId?: string }>(
      `/v1/channels/outbox/${encodeURIComponent(id)}/retry`,
      {},
    );
    setMsg(`outbox 重投 · id=${r.retriedId || id} · ok=${String(r.ok)}`);
    outboxApi.reload();
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

  const channelRows = (channelsApi.data?.items || []).map((c) => [
    c.nameZh || c.name || c.id,
    c.id,
    c.installed ? "已安装" : "未安装",
    c.runtime || "—",
    c.installed ? (
      <span className="muted" key={c.id}>
        —
      </span>
    ) : (
      <button
        key={c.id}
        type="button"
        className="bp-action-link"
        onClick={() => void installChannel(c.id).catch((e) => setMsg(String(e)))}
      >
        安装
      </button>
    ),
  ]);

  const outboxRows = (outboxApi.data?.items || []).map((o) => {
    const f = formatOutboxRow(o);
    return [
      f.id,
      f.channel,
      f.result,
      f.status,
      o.id ? (
        <button
          key={o.id}
          type="button"
          className="bp-action-link"
          data-testid="outbox-retry"
          onClick={() => void retryOutbox(String(o.id)).catch((e) => setMsg(String(e)))}
        >
          重投
        </button>
      ) : (
        "—"
      ),
    ];
  });

  return (
    <S2Chrome title="Events 配置面板" lede="Widget 事件绑定、通道插件与幂等键配置。">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => void register().catch((e) => setMsg(String(e)))}>
          + 注册 Webhook
        </button>
        <button
          type="button"
          className="btn-nav"
          onClick={() => void sendWebhookDry().catch((e) => setMsg(String(e)))}
        >
          试投递 channel-webhook
        </button>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <button type="button" className="btn-nav" onClick={() => outboxApi.reload()}>
          刷新 outbox
        </button>
        <Link to="/workshop/canvas" className="btn-nav">
          画布配置 →
        </Link>
      </BpToolbar>
      <div className="ont-form-grid" style={{ marginBottom: 12 }}>
        <label className="ont-form-field">
          <span>webhook URL</span>
          <input className="aos-input" value={hookUrl} onChange={(e) => setHookUrl(e.target.value)} />
        </label>
        <label className="ont-form-field">
          <span>event</span>
          <input className="aos-input" value={hookEvent} onChange={(e) => setHookEvent(e.target.value)} />
        </label>
      </div>
      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}
      {channelsApi.err && <p className="error">{channelsApi.err}</p>}
      {outboxApi.err && <p className="error">{outboxApi.err}</p>}

      <div className="bp-object-panel">
        <div className="bp-ws-section-title">通知通道插件</div>
        <BpTable
          columns={["名称", "id", "安装", "runtime", ""]}
          rows={channelRows.length ? channelRows : [["—", "—", "—", "—", "—"]]}
        />
        <div className="bp-ws-section-title" style={{ marginTop: "1rem" }}>
          已注册事件
        </div>
        <BpTable columns={["触发器", "动作", "目标变量", "幂等"]} rows={[...blueprintRows, ...apiRows]} />
        <div className="bp-ws-section-title" style={{ marginTop: "1rem" }}>
          Channel outbox（212m/218m）
        </div>
        <BpTable
          columns={["id", "channel", "结果", "status", ""]}
          rows={outboxRows.length ? outboxRows : [["—", "—", "—", "—", "—"]]}
        />
      </div>

      <BpBanner tone="warn">
        <strong>幂等护栏</strong> · 写操作事件须配置 idempotencyKey，防止双击重复提交（对齐 ACT-07）。
        Webhook 默认 dry-run（AOS_WEBHOOK_DRY_RUN=1）；邮件需 AOS_SMTP_HOST。
      </BpBanner>
    </S2Chrome>
  );
}
