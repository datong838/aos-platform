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

  const props = draftProps;
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
            <BpPropGrid
              items={[
                { label: "RID", value: `ri.ontology.main.object-type.${typeId.toLowerCase()}` },
                { label: "API 名", value: typeId },
                { label: "分支", value: branchId },
                { label: "Properties", value: String(props.length) },
                {
                  label: "管道",
                  value: funnelStage || "未配置",
                  tone: funnelTone === "ok" ? "ok" : "warn",
                },
              ]}
            />
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
              <pre className="ont-ov-pre">{linkGraph}</pre>
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
          <pre
            className="card"
            style={{ fontSize: "0.75rem", textAlign: "center", whiteSpace: "pre-wrap", lineHeight: 1.8 }}
          >
            {linkGraph}
          </pre>
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
