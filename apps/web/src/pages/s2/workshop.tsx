import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getOntologyClient } from "../../api/ontologyClient";
import {
  createAnnotation,
  createExploration,
  createObjectSet,
  listExplorations,
  type ExplorationAsset,
} from "../../api/ontologyExplorationAssets";
import { queryAuthoritativeGraph } from "../../api/ontologyGraph";
import type { GraphSnapshot } from "../../api/ontologyExplorerContracts";
import {
  buildExplorerSearchParams,
  ObjectExplorerWorkspace,
  resolveExplorerColumns,
  toggleObjectSelection,
} from "../../components/ontology/ObjectExplorerWorkspace";
import { OntologyGraphCanvas } from "../../components/ontology/OntologyGraphCanvas";
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
  const [graphSnapshot, setGraphSnapshot] = useState<GraphSnapshot | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [graphHops, setGraphHops] = useState(2);
  const [graphRelationType, setGraphRelationType] = useState("");
  const [graphObjectType, setGraphObjectType] = useState("");
  const [wiki, setWiki] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [toast, setToast] = useState("");
  const [query, setQuery] = useState("");
  const [viewMode, setViewMode] = useState<"table" | "graph" | "annotation">("table");
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [detailOpen, setDetailOpen] = useState(false);
  const [focusMode, setFocusMode] = useState(false);
  const [detailTab, setDetailTab] = useState<
    "overview" | "properties" | "relations" | "wiki" | "action" | "timeline"
  >("overview");
  const [assetName, setAssetName] = useState("栖月汇对象探索");
  const [assetVisibility, setAssetVisibility] = useState<"private" | "workspace">("private");
  const [savedExplorations, setSavedExplorations] = useState<ExplorationAsset[]>([]);
  const [assetBusy, setAssetBusy] = useState(false);
  const [annotationTitle, setAnnotationTitle] = useState("");
  const [annotationBody, setAnnotationBody] = useState("");

  useEffect(() => {
    if (types?.items?.length && !types.items.some((t) => t.id === typeId)) {
      setTypeId(types.items[0].id);
    }
  }, [types, typeId]);

  useEffect(() => {
    void loadObjects(typeId);
  }, [typeId]);

  useEffect(() => {
    void refreshExplorations();
  }, []);

  async function refreshExplorations() {
    try {
      const items = await listExplorations();
      setSavedExplorations(items);
      const viewRef = searchParams.get("viewRef")?.trim();
      const referenced = viewRef ? items.find((item) => item.id === viewRef) : undefined;
      if (referenced) applySavedExploration(referenced, false);
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function loadObjects(t: string) {
    setErr(null);
    setObjectId(null);
    setDetail(null);
    setNeighbors([]);
    setGraphSnapshot(null);
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
      setDetail(d as Record<string, unknown>);
      setSearchParams(buildExplorerSearchParams(t, id, searchParams), { replace: true });
      await loadGraph(t, id, graphHops, graphRelationType, graphObjectType);
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
      setGraphSnapshot(null);
    }
  }

  async function loadGraph(t: string, id: string, hops: number, relationType: string, objectType: string) {
    setGraphLoading(true);
    setGraphError(null);
    try {
      const snapshot = await queryAuthoritativeGraph({
        seeds: [{ objectType: t, objectId: id }],
        hops,
        maxNodes: 500,
        direction: "both",
        objectTypes: objectType ? [...new Set([t, objectType])] : [],
        relationTypes: relationType ? [relationType] : [],
        graphDomains: ["domain"],
      });
      setGraphSnapshot(snapshot);
      const nodeByKey = new Map(snapshot.nodes.map((node) => [node.key, node]));
      const seedKey = `${t}:${id}`;
      setNeighbors(snapshot.edges.flatMap((edge) => {
        const otherKey = edge.source === seedKey
          ? edge.target
          : edge.target === seedKey
            ? edge.source
            : null;
        const other = otherKey ? nodeByKey.get(otherKey) : undefined;
        return other ? [{ id: other.objectId, type: other.objectType, rel: edge.relationType }] : [];
      }));
    } catch (graphLoadError) {
      setGraphSnapshot(null);
      setNeighbors([]);
      setGraphError(`权威图查询失败：${String((graphLoadError as Error).message || graphLoadError)}`);
    } finally {
      setGraphLoading(false);
    }
  }

  const graphRelationTypes = useMemo(
    () => [...new Set(graphSnapshot?.edges.map((edge) => edge.relationType) || [])].sort(),
    [graphSnapshot],
  );
  const graphObjectTypes = useMemo(
    () => [...new Set([
      ...(graphSnapshot?.nodes.map((node) => node.objectType) || []),
      ...(graphObjectType ? [graphObjectType] : []),
    ])].sort(),
    [graphSnapshot, graphObjectType],
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

  async function saveCurrentExploration(visibility = assetVisibility) {
    if (!assetName.trim()) {
      setErr("请先填写探索名称");
      return;
    }
    setAssetBusy(true);
    setErr(null);
    try {
      const saved = await createExploration({
        name: assetName.trim(),
        objectType: typeId,
        viewMode,
        visibility,
        query: { search: query },
        columns: objectColumns.map((column) => ({ ...column })),
        graph: { focusObjectId: objectId },
      });
      setAssetVisibility(visibility);
      setToast(`已保存并重读 · ${saved.payload.name} · revision ${saved.revision}`);
      await refreshExplorations();
      const next = new URLSearchParams(searchParams);
      next.set("viewRef", saved.id);
      setSearchParams(next, { replace: true });
    } catch (e) {
      setErr(`保存探索失败：${String((e as Error).message || e)}`);
    } finally {
      setAssetBusy(false);
    }
  }

  async function saveSelectedObjectSet() {
    if (selectedKeys.length === 0) return;
    setAssetBusy(true);
    setErr(null);
    try {
      const saved = await createObjectSet({
        name: `${assetName.trim() || currentTypeName} · 对象集`,
        objectType: typeId,
        visibility: assetVisibility,
        items: selectedKeys.map((key) => ({
          objectType: typeId,
          objectId: key.slice(`${typeId}:`.length),
        })),
      });
      setToast(`对象集已写入服务端 · ${saved.id} · ${selectedKeys.length} 项`);
    } catch (e) {
      setErr(`创建对象集失败：${String((e as Error).message || e)}`);
    } finally {
      setAssetBusy(false);
    }
  }

  async function saveCurrentAnnotation() {
    if (!annotationTitle.trim() || !annotationBody.trim()) {
      setErr("注释标题和正文不能为空");
      return;
    }
    setAssetBusy(true);
    setErr(null);
    try {
      const selectedObjectId = objectId ? String(objectId) : null;
      const saved = await createAnnotation({
        title: annotationTitle.trim(),
        body: annotationBody.trim(),
        subject: selectedObjectId
          ? {
              subjectType: "object_instance",
              subjectId: `${typeId}/${selectedObjectId}`,
              objectRef: { objectType: typeId, objectId: selectedObjectId },
            }
          : { subjectType: "object_type", subjectId: typeId },
        visibility: assetVisibility,
        state: "draft",
      });
      setToast(`注释草稿已写入服务端 · ${saved.id}`);
      setAnnotationBody("");
    } catch (e) {
      setErr(`保存注释失败：${String((e as Error).message || e)}`);
    } finally {
      setAssetBusy(false);
    }
  }

  function applySavedExploration(asset: ExplorationAsset, updateUrl = true) {
    setAssetName(asset.payload.name);
    setAssetVisibility(asset.payload.visibility);
    setViewMode(asset.payload.viewMode);
    setQuery(String(asset.payload.query.search || ""));
    setTypeId(asset.payload.objectType);
    if (updateUrl) {
      const next = new URLSearchParams(searchParams);
      next.set("viewRef", asset.id);
      setSearchParams(next, { replace: true });
    }
    setToast(`已从服务端恢复 ${asset.payload.name} · revision ${asset.revision}`);
  }

  function openSavedExploration(id: string) {
    const asset = savedExplorations.find((item) => item.id === id);
    if (asset) applySavedExploration(asset);
  }

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
          <div className="p-objx-tab-actions">
            <select
              aria-label="打开已保存探索"
              value={searchParams.get("viewRef") || ""}
              onChange={(event) => openSavedExploration(event.target.value)}
            >
              <option value="">已保存探索</option>
              {savedExplorations.map((item) => (
                <option key={item.id} value={item.id}>{item.payload.name}</option>
              ))}
            </select>
            <input
              aria-label="探索名称"
              value={assetName}
              onChange={(event) => setAssetName(event.target.value)}
              maxLength={240}
            />
            <select
              aria-label="资产可见范围"
              value={assetVisibility}
              onChange={(event) => setAssetVisibility(event.target.value as "private" | "workspace")}
            >
              <option value="private">仅自己</option>
              <option value="workspace">当前工作区</option>
            </select>
            <button type="button" className="p-objx-action" disabled={assetBusy} onClick={() => void saveCurrentExploration()}>
              {assetBusy ? "写入中…" : "保存探索"}
            </button>
            <button type="button" className="p-objx-action" disabled={assetBusy} onClick={() => void saveCurrentExploration("workspace")}>
              分享至工作区
            </button>
            <button
              type="button"
              className="p-objx-action"
              disabled={assetBusy || selectedKeys.length === 0}
              title={selectedKeys.length === 0 ? "请先选择至少一个对象" : "将选中对象保存为对象集"}
              onClick={() => void saveSelectedObjectSet()}
            >
              新建对象集
            </button>
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
            <button
              type="button"
              className={`p-objx-view-btn ${viewMode === "annotation" ? "is-active" : ""}`}
              onClick={() => setViewMode("annotation")}
            >
              注释
            </button>
          </div>
          <div className="p-objx-view-center">
            <span className="p-objx-results-count">{filteredObjects.length} 条结果</span>
            {selectedKeys.length > 0 && (
              <span className="p-objx-selection-count">已选择 {selectedKeys.length} 条</span>
            )}
          </div>
          {viewMode === "graph" && objectId && (
            <div className="p-objx-graph-query-controls" aria-label="权威图查询条件">
              <label>
                跳数
                <select
                  aria-label="图查询跳数"
                  value={graphHops}
                  onChange={(event) => {
                    const hops = Number(event.target.value);
                    setGraphHops(hops);
                    void loadGraph(typeId, objectId, hops, graphRelationType, graphObjectType);
                  }}
                >
                  {[1, 2, 3, 4, 5].map((hops) => <option key={hops} value={hops}>{hops}</option>)}
                </select>
              </label>
              <label>
                关系
                <select
                  aria-label="关系类型过滤"
                  value={graphRelationType}
                  onChange={(event) => {
                    const relationType = event.target.value;
                    setGraphRelationType(relationType);
                    void loadGraph(typeId, objectId, graphHops, relationType, graphObjectType);
                  }}
                >
                  <option value="">全部关系</option>
                  {graphRelationTypes.map((relationType) => <option key={relationType}>{relationType}</option>)}
                </select>
              </label>
              <label>
                类型过滤
                <select
                  aria-label="对象类型过滤"
                  value={graphObjectType}
                  onChange={(event) => {
                    const objectType = event.target.value;
                    setGraphObjectType(objectType);
                    void loadGraph(typeId, objectId, graphHops, graphRelationType, objectType);
                  }}
                >
                  <option value="">全部类型</option>
                  {graphObjectTypes.map((objectType) => <option key={objectType}>{objectType}</option>)}
                </select>
              </label>
            </div>
          )}
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
            ) : viewMode === "graph" ? (
              <OntologyGraphCanvas
                snapshot={graphSnapshot}
                loading={graphLoading}
                error={graphError}
                onSelectNode={(node) => {
                  setToast(`已选择 ${node.objectType}/${node.objectId}`);
                  if (node.objectType === typeId && node.objectId === objectId) setDetailOpen(true);
                }}
                onExpandNode={(node) => selectObject(node.objectType, node.objectId)}
              />
            ) : (
              <div className="p-objx-annotation-editor">
                <h3>新建注释草稿</h3>
                <p className="muted">
                  {objectId ? `绑定对象 ${typeId}/${objectId}` : `绑定 Object Type ${typeId}`}
                  {" · "}保存后形成不可变 revision，可在后续 Wiki 审批流中引用。
                </p>
                <label>
                  标题
                  <input
                    aria-label="注释标题"
                    value={annotationTitle}
                    onChange={(event) => setAnnotationTitle(event.target.value)}
                    maxLength={240}
                  />
                </label>
                <label>
                  正文
                  <textarea
                    aria-label="注释正文"
                    value={annotationBody}
                    onChange={(event) => setAnnotationBody(event.target.value)}
                    rows={10}
                  />
                </label>
                <button type="button" className="p-objx-save" disabled={assetBusy} onClick={() => void saveCurrentAnnotation()}>
                  {assetBusy ? "写入中…" : "保存注释草稿"}
                </button>
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
