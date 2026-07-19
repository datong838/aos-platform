import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { getOntologyClient } from "../api/ontologyClient";
import { BpBanner } from "./s2/blueprintUi";

export type WidgetCanvasNode = {
  kind: string;
  pluginId?: string;
  title?: string;
  config?: {
    site?: string;
    objectType?: string;
    objectId?: string;
    actionTypeId?: string;
    groupBy?: string;
  };
};

/** 106/108 · 旧 stub Layout 按 pluginId 升真渲染 */
export function resolveRenderKind(node: Pick<WidgetCanvasNode, "kind" | "pluginId">): string {
  if (node.pluginId === "action-form") return "action";
  if (node.pluginId === "graph-view") return "graph";
  if (node.pluginId === "metric-card") return "metric";
  return node.kind;
}

/** 108 · ObjectSet 行分桶 */
export function summarizeMetricRows(
  rows: Record<string, unknown>[],
  groupBy = "status",
): { total: number; buckets: { label: string; count: number }[] } {
  const counts = new Map<string, number>();
  for (const row of rows) {
    const props = (row.props as Record<string, unknown> | undefined) || row;
    const raw = props[groupBy] ?? row[groupBy] ?? "(空)";
    const label = String(raw);
    counts.set(label, (counts.get(label) || 0) + 1);
  }
  const buckets = [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
  return { total: rows.length, buckets };
}

/** 107 · 画布 Idempotency-Key */
export function newCanvasIdempotencyKey(prefix = "canvas-af"): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

/** 107 · execute 请求体；画布默认 HITL */
export function buildActionExecuteBody(opts: {
  actionTypeId: string;
  objectType?: string;
  objectId?: string;
  payload: Record<string, unknown>;
  autoApprove?: boolean;
}): {
  actionTypeId: string;
  objectType: string;
  objectId?: string;
  payload: Record<string, unknown>;
  proposed: Record<string, unknown>;
  autoApprove: boolean;
} {
  const objectType = (opts.objectType || "WorkOrder").trim() || "WorkOrder";
  const objectId = (opts.objectId || "").trim() || undefined;
  return {
    actionTypeId: opts.actionTypeId,
    objectType,
    objectId,
    payload: opts.payload,
    proposed: opts.payload,
    autoApprove: opts.autoApprove === true,
  };
}

type ActionParam = { name: string; type?: string; required?: boolean };

export function ActionFormWidget({
  node,
  onConfig,
}: {
  node: WidgetCanvasNode;
  onConfig?: (patch: { actionTypeId?: string; objectType?: string; objectId?: string }) => void;
}) {
  const actionTypeId = node.config?.actionTypeId || "CloseWorkOrder";
  const objectType = node.config?.objectType || "WorkOrder";
  const objectId = node.config?.objectId || "";
  const [params, setParams] = useState<ActionParam[]>([]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [draftId, setDraftId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setErr(null);
    apiGet<{ id?: string; parameters?: ActionParam[] }>(
      `/v1/actions/types/${encodeURIComponent(actionTypeId)}`,
    )
      .then((row) => {
        if (cancelled) return;
        const ps = Array.isArray(row.parameters) ? row.parameters : [];
        setParams(ps);
        setValues((prev) => {
          const next: Record<string, string> = {};
          for (const p of ps) {
            next[p.name] = prev[p.name] ?? "";
          }
          return next;
        });
      })
      .catch((e) => {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [actionTypeId]);

  function payloadFromValues(): Record<string, unknown> {
    const payload: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(values)) {
      payload[k] = v;
    }
    return payload;
  }

  async function runValidate() {
    setBusy(true);
    setMsg(null);
    setDraftId(null);
    setErr(null);
    try {
      const res = await apiPost<{ ok?: boolean; actionTypeId?: string }>("/v1/actions/validate", {
        actionTypeId,
        payload: payloadFromValues(),
      });
      setMsg(res.ok ? `校验通过 · ${res.actionTypeId || actionTypeId}` : "校验返回非 ok");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function runSubmitDraft() {
    setBusy(true);
    setMsg(null);
    setDraftId(null);
    setErr(null);
    try {
      const body = buildActionExecuteBody({
        actionTypeId,
        objectType,
        objectId,
        payload: payloadFromValues(),
        autoApprove: false,
      });
      const key = newCanvasIdempotencyKey();
      const res = await apiPost<{
        id?: string;
        status?: string;
        productionWritten?: boolean;
        via?: string;
      }>("/v1/actions/execute", body, { "Idempotency-Key": key });
      const id = res.id || null;
      setDraftId(id);
      setMsg(
        `已创建 Draft · ${id || "—"} · status=${res.status || "proposed"} · productionWritten=${String(res.productionWritten)} · via=${res.via || "hitl-draft"}`,
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bp-canvas-widget">
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span className="bp-tag bp-tag-ok">Action Form</span>
        <span className="muted" style={{ fontSize: "0.75rem" }}>
          {actionTypeId} · validate + HITL Draft（禁 autoApprove）
        </span>
      </div>
      {onConfig && (
        <>
          <label className="muted" style={{ display: "block", marginTop: 6, fontSize: "0.75rem" }}>
            actionTypeId{" "}
            <input
              value={actionTypeId}
              onChange={(e) => onConfig({ actionTypeId: e.target.value, objectType, objectId })}
              style={{ width: "12rem" }}
            />
          </label>
          <label className="muted" style={{ display: "block", marginTop: 4, fontSize: "0.75rem" }}>
            objectType{" "}
            <input
              value={objectType}
              onChange={(e) => onConfig({ actionTypeId, objectType: e.target.value, objectId })}
              style={{ width: "8rem" }}
            />
          </label>
          <label className="muted" style={{ display: "block", marginTop: 4, fontSize: "0.75rem" }}>
            objectId{" "}
            <input
              value={objectId}
              onChange={(e) => onConfig({ actionTypeId, objectType, objectId: e.target.value })}
              placeholder="可选"
              style={{ width: "8rem" }}
            />
          </label>
        </>
      )}
      {params.length === 0 && !err && (
        <p className="muted" style={{ fontSize: "0.75rem", marginTop: 6 }}>
          无参数定义 · 仍可试跑校验 / 提交 Draft
        </p>
      )}
      {params.map((p) => (
        <label
          key={p.name}
          className="muted"
          style={{ display: "block", marginTop: 4, fontSize: "0.75rem" }}
        >
          {p.name}
          {p.required ? " *" : ""}{" "}
          <input
            value={values[p.name] ?? ""}
            onChange={(e) => setValues((prev) => ({ ...prev, [p.name]: e.target.value }))}
          />
        </label>
      ))}
      <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="btn" disabled={busy} onClick={() => void runValidate()}>
          {busy ? "处理中…" : "试跑校验"}
        </button>
        <button type="button" className="btn-nav" disabled={busy} onClick={() => void runSubmitDraft()}>
          提交 Draft（HITL）
        </button>
      </div>
      {msg && (
        <p className="bp-prop-ok" style={{ fontSize: "0.75rem" }}>
          {msg}
        </p>
      )}
      {draftId && (
        <p style={{ fontSize: "0.75rem", marginTop: 4 }}>
          <Link to="/aip/drafts" className="nav-link">
            打开 Draft 审批台 → {draftId}
          </Link>
        </p>
      )}
      {err && (
        <p className="error" style={{ fontSize: "0.75rem" }}>
          {err}
        </p>
      )}
    </div>
  );
}

type Neighbor = { rel?: string; type?: string; id?: string };

export function GraphViewWidget({
  node,
  fallbackObjectId,
  onConfig,
}: {
  node: WidgetCanvasNode;
  fallbackObjectId?: string;
  onConfig?: (patch: { objectType?: string; objectId?: string }) => void;
}) {
  const objectType = node.config?.objectType || "WorkOrder";
  const objectId = node.config?.objectId || fallbackObjectId || "wo-1001";
  const [items, setItems] = useState<Neighbor[]>([]);
  const [engine, setEngine] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    setErr(null);
    try {
      const res = (await getOntologyClient().neighbors(objectType, objectId)) as {
        items?: Neighbor[];
        engine?: string;
      };
      setItems(Array.isArray(res.items) ? res.items : []);
      setEngine(res.engine || "adjacency_table");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setItems([]);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [objectType, objectId]);

  return (
    <div className="bp-canvas-widget">
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span className="bp-tag">Graph View</span>
        <span className="muted" style={{ fontSize: "0.75rem" }}>
          {objectType}/{objectId} · {engine || "adjacency_table"}（非 G6）
        </span>
      </div>
      {onConfig && (
        <div style={{ marginTop: 6, display: "flex", gap: 8, flexWrap: "wrap" }}>
          <label className="muted" style={{ fontSize: "0.75rem" }}>
            type{" "}
            <input
              value={objectType}
              onChange={(e) => onConfig({ objectType: e.target.value, objectId })}
              style={{ width: "7rem" }}
            />
          </label>
          <label className="muted" style={{ fontSize: "0.75rem" }}>
            id{" "}
            <input
              value={objectId}
              onChange={(e) => onConfig({ objectType, objectId: e.target.value })}
              style={{ width: "7rem" }}
            />
          </label>
        </div>
      )}
      <button type="button" className="btn" style={{ marginTop: 8 }} disabled={busy} onClick={() => void load()}>
        {busy ? "加载中…" : "刷新邻接"}
      </button>
      {err && (
        <p className="error" style={{ fontSize: "0.75rem" }}>
          {err}
        </p>
      )}
      {!err && items.length === 0 && (
        <BpBanner tone="info">
          <span className="muted" style={{ fontSize: "0.75rem" }}>
            无 1-hop 边 · 可到本体 Graph 页核对 seed
          </span>
        </BpBanner>
      )}
      <ul className="card-list" style={{ marginTop: 8 }}>
        {items.map((n, i) => (
          <li key={`${n.rel}-${n.type}-${n.id}-${i}`} className="muted" style={{ fontSize: "0.75rem" }}>
            —[{n.rel || "rel"}]→ {n.type}/{n.id}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** 108 · Metric Card · ObjectSet 计数 + 分桶 */
export function MetricCardWidget({
  node,
  onConfig,
}: {
  node: WidgetCanvasNode;
  onConfig?: (patch: { objectType?: string; groupBy?: string; site?: string }) => void;
}) {
  const objectType = node.config?.objectType || "WorkOrder";
  const groupBy = node.config?.groupBy || "status";
  const site = node.config?.site || "";
  const [total, setTotal] = useState(0);
  const [buckets, setBuckets] = useState<{ label: string; count: number }[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    setErr(null);
    try {
      const filters: { field: string; value: string }[] = [];
      if (site.trim()) filters.push({ field: "site", value: site.trim() });
      const res = await apiPost<{ items?: Record<string, unknown>[]; total?: number }>(
        "/v1/object-sets/query",
        {
          objectType,
          filters,
          page: 1,
          pageSize: 200,
          source: "pg",
        },
      );
      const items = Array.isArray(res.items) ? res.items : [];
      const summary = summarizeMetricRows(items, groupBy);
      setTotal(typeof res.total === "number" ? res.total : summary.total);
      setBuckets(summary.buckets);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setTotal(0);
      setBuckets([]);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [objectType, groupBy, site]);

  return (
    <div className="bp-canvas-widget">
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span className="bp-tag bp-tag-ok">Metric</span>
        <span className="muted" style={{ fontSize: "0.75rem" }}>
          {objectType} · groupBy={groupBy} · source=object-sets
        </span>
      </div>
      {onConfig && (
        <div style={{ marginTop: 6, display: "flex", gap: 8, flexWrap: "wrap" }}>
          <label className="muted" style={{ fontSize: "0.75rem" }}>
            type{" "}
            <input
              value={objectType}
              onChange={(e) => onConfig({ objectType: e.target.value, groupBy, site })}
              style={{ width: "7rem" }}
            />
          </label>
          <label className="muted" style={{ fontSize: "0.75rem" }}>
            groupBy{" "}
            <input
              value={groupBy}
              onChange={(e) => onConfig({ objectType, groupBy: e.target.value, site })}
              style={{ width: "6rem" }}
            />
          </label>
          <label className="muted" style={{ fontSize: "0.75rem" }}>
            site{" "}
            <input
              value={site}
              onChange={(e) => onConfig({ objectType, groupBy, site: e.target.value })}
              placeholder="可选"
              style={{ width: "6rem" }}
            />
          </label>
        </div>
      )}
      <p style={{ margin: "0.5rem 0 0", fontSize: "1.5rem", fontWeight: 600 }}>{busy ? "…" : total}</p>
      <p className="muted" style={{ fontSize: "0.7rem", margin: 0 }}>
        总数（本页抽样分桶 ≤200）
      </p>
      <button type="button" className="btn" style={{ marginTop: 8 }} disabled={busy} onClick={() => void load()}>
        {busy ? "刷新中…" : "刷新指标"}
      </button>
      {err && (
        <p className="error" style={{ fontSize: "0.75rem" }}>
          {err}
        </p>
      )}
      <ul className="card-list" style={{ marginTop: 8 }}>
        {buckets.slice(0, 8).map((b) => (
          <li key={b.label} className="muted" style={{ fontSize: "0.75rem" }}>
            {b.label}: <strong>{b.count}</strong>
          </li>
        ))}
      </ul>
      {!err && !busy && buckets.length === 0 && (
        <BpBanner tone="info">
          <span className="muted" style={{ fontSize: "0.75rem" }}>
            无行 · 检查 ObjectType / Filter
          </span>
        </BpBanner>
      )}
    </div>
  );
}
