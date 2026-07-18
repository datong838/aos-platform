import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet } from "../../api/client";
import {
  BpBanner,
  BpLinkRow,
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

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "properties", label: "Properties" },
  { id: "actions", label: "Action types" },
  { id: "links", label: "Link type graph" },
  { id: "dependents", label: "Dependents" },
  { id: "data", label: "Data" },
  { id: "usage", label: "Usage" },
];

export function ObjectTypeDetailPanel({
  typeId,
  typeName,
  description,
  published,
  properties,
  branchId,
  instanceCount,
  funnelStage,
  objects,
  onOpenInstance,
  detail,
  neighbors,
}: {
  typeId: string;
  typeName: string;
  description?: string;
  published?: boolean;
  properties?: PropDef[];
  branchId: string;
  instanceCount: number;
  funnelStage?: string;
  objects: Record<string, unknown>[];
  onOpenInstance: (id: string) => void;
  detail: Record<string, unknown> | null;
  neighbors: { id?: string; type?: string; rel?: string }[];
}) {
  const [tab, setTab] = useState("overview");
  const [links, setLinks] = useState<LinkRow[]>([]);
  const [actions, setActions] = useState<ActionRow[]>([]);
  const [modules, setModules] = useState<ModuleRow[]>([]);
  const [metricsTotal, setMetricsTotal] = useState<number | null>(null);

  useEffect(() => {
    setTab("overview");
  }, [typeId]);

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

  const props = properties || [];
  const detailProps =
    detail &&
    Object.entries(detail)
      .filter(([k]) => !k.startsWith("_"))
      .slice(0, 8)
      .map(([k, v]) => ({ label: k, value: String(v ?? "—") }));

  const linkGraph = useMemo(() => {
    if (links.length === 0) return `[${typeId}] · 暂无 Link Type`;
    return links
      .map((l) => {
        if (l.srcType === typeId) {
          return `[${typeId}] ── ${l.rel || "link"} ──► [${l.dstType}]`;
        }
        return `[${l.srcType}] ── ${l.rel || "link"} ──► [${typeId}]`;
      })
      .join("\n");
  }, [links, typeId]);

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
        <div className="bp-domain bp-domain-ontology" style={{ padding: "1rem" }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginBottom: "0.75rem" }}>
            <span className={`bp-tag bp-tag-${published ? "ok" : "warn"}`}>
              {published ? "已发布" : "草稿"}
            </span>
            <span className={`bp-tag bp-tag-${funnelTone}`}>
              Funnel: {funnelStage || "未配置"}
            </span>
            <span className="bp-tag">{instanceCount} 实例</span>
          </div>
          {description && (
            <p className="muted" style={{ fontSize: "0.875rem" }}>
              {description}
            </p>
          )}
          <BpPropGrid
            items={[
              { label: "API 名", value: typeId },
              { label: "RID", value: `ri.ontology.main.object-type.${typeId.toLowerCase()}` },
              { label: "分支", value: branchId },
              { label: "Properties", value: String(props.length) },
            ]}
          />
          <div className="canvas-grid" style={{ marginTop: "1rem" }}>
            <div className="card">
              <h3 className="bp-ws-section-title">Properties</h3>
              <ul className="muted" style={{ fontSize: "0.8rem", paddingLeft: "1rem" }}>
                {props.slice(0, 3).map((p) => (
                  <li key={p.name}>
                    {p.name} · {p.type || "string"}
                  </li>
                ))}
                {props.length === 0 && <li>—</li>}
              </ul>
              <button type="button" className="nav-link" onClick={() => setTab("properties")}>
                查看全部 →
              </button>
            </div>
            <div className="card">
              <h3 className="bp-ws-section-title">Action types</h3>
              <ul className="muted" style={{ fontSize: "0.8rem", paddingLeft: "1rem" }}>
                {actions.slice(0, 3).map((a) => (
                  <li key={a.id}>{a.name}</li>
                ))}
                {actions.length === 0 && <li>暂无</li>}
              </ul>
            </div>
            <div className="card">
              <h3 className="bp-ws-section-title">Link graph</h3>
              <pre className="muted" style={{ fontSize: "0.65rem", whiteSpace: "pre-wrap" }}>
                {linkGraph}
              </pre>
            </div>
            <div className="card">
              <h3 className="bp-ws-section-title">Data · Funnel</h3>
              <p className="muted" style={{ fontSize: "0.8rem" }}>
                {funnelStage ? `Stage: ${funnelStage}` : "未配置 Funnel"}
              </p>
              <Link to="/ontology/funnel" className="nav-link">
                Pipeline →
              </Link>
            </div>
          </div>
          <BpLinkRow
            links={[
              { to: "/ontology/wiki", label: "LLM Wiki" },
              { to: "/ontology/funnel", label: "Funnel" },
            ]}
          />
        </div>
      )}

      {tab === "properties" && (
        <BpTable
          columns={["Property", "类型", "Backing", "标志"]}
          rows={
            props.length
              ? props.map((p, i) => [
                  p.name,
                  p.type || "string",
                  p.name,
                  i === 0 ? "PK" : "—",
                ])
              : [["—", "—", "—", "—"]]
          }
        />
      )}

      {tab === "actions" && (
        <>
          {actions.length === 0 && <p className="muted">该 Object Type 暂无 Action Type</p>}
          <ul className="card-list">
            {actions.map((a) => (
              <li key={a.id} className="card">
                <strong>{a.name}</strong>
                <span className="muted" style={{ marginLeft: 8 }}>
                  {a.id}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      {tab === "links" && (
        <>
          <pre
            className="card"
            style={{ fontSize: "0.75rem", textAlign: "center", whiteSpace: "pre-wrap", lineHeight: 1.8 }}
          >
            {linkGraph}
          </pre>
          {links.length > 0 && (
            <BpTable
              columns={["id", "rel", "src", "dst"]}
              rows={links.map((l) => [
                l.id,
                l.rel || "—",
                l.srcType || "—",
                l.dstType || "—",
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
              ["Funnel Pipeline", "Data", <Link key="f" to="/ontology/funnel">Pipeline →</Link>],
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
            <Link to="/ontology/funnel" className="btn" style={{ marginTop: 8, display: "inline-block" }}>
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
                hint: "非 OT 专属 · 近 30 天读",
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
            Usage 30 天读/写/活跃用户以当前 metrics totals + 实例数汇总。
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
