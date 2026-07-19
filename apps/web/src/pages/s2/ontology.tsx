import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiGet, apiPost } from "../../api/client";
import { getOntologyClient } from "../../api/ontologyClient";
import { useOntologyObject } from "../../api/ontologyHooks";
import { fieldDiff } from "../../lib/ontologyRecent";
import {
  BpBanner,
  BpLinkRow,
  BpMetricGrid,
  BpSplit,
  BpStagePipeline,
  BpTable,
  BpTabs,
  BpToolbar,
} from "./blueprintUi";
import { S2Chrome, useJsonGet } from "./shared";

type Branch = { id: string; name: string; baseRef: string; readonly: boolean; changeCount?: number };
type GhIssue = {
  code: string;
  severity?: string;
  object?: string;
  message?: string;
  href?: string;
};

/** 89/94 · 对齐 ontology-graph-health · issues 服务端真源 */
export function GraphHealthPage() {
  const { data, err, reload } = useJsonGet<{
    score: number;
    metrics: {
      objectTypes: number;
      instances: number;
      edges: number;
      orphanInstances: number;
      danglingEdges?: number;
      propConflicts?: number;
      archiveCandidates?: number;
      insightTtlDays?: number;
      engine: string;
    };
    issues?: GhIssue[];
    archivePreview?: { id: string; createdAt?: string; objectId?: string }[];
  }>("/v1/ontology/graph-health");
  const [ttlMsg, setTtlMsg] = useState("");
  const [ttlBusy, setTtlBusy] = useState(false);

  const m = data?.metrics;
  const issues = data?.issues || [];
  const gh01 = issues.filter((i) => i.code === "GH-01").length;
  const gh02 = m?.propConflicts ?? issues.filter((i) => i.code === "GH-02").length;
  const gh04 = issues.filter((i) => i.code === "GH-04").length;

  async function runTtl() {
    setTtlBusy(true);
    setTtlMsg("");
    try {
      const out = await apiPost<{ archivedCount: number; candidateCount: number }>(
        "/v1/ops/ttl/run",
        { dryRun: false },
      );
      setTtlMsg(
        `TTL 归档完成：候选 ${out.candidateCount} · 已归档 ${out.archivedCount}`,
      );
      reload();
    } catch (e) {
      setTtlMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setTtlBusy(false);
    }
  }

  return (
    <S2Chrome
      title="图谱健康度"
      lede="悬空链接 · 属性冲突 · 孤立对象 · Insight TTL 归档候选"
    >
      <div className="ont-page">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => reload()}>
          重新扫描
        </button>
        <button
          type="button"
          className="btn"
          disabled={ttlBusy}
          onClick={() => void runTtl()}
        >
          {ttlBusy ? "归档中…" : "运行 TTL 归档"}
        </button>
        <Link to="/data/health" className="btn-nav">
          L1 数据健康 →
        </Link>
        <Link to="/ontology" className="btn-nav">
          ← 本体管理
        </Link>
      </BpToolbar>
      {err && <p className="error">{err}</p>}
      {ttlMsg ? <p className="muted">{ttlMsg}</p> : null}
      <p className="muted" style={{ fontSize: "0.8rem" }}>
        当前 score={data?.score ?? "—"} · engine={m?.engine ?? "—"} · instances={m?.instances ?? "—"} ·
        dangling={m?.danglingEdges ?? "—"} · Insight TTL={m?.insightTtlDays ?? "—"} 天
      </p>

      <BpMetricGrid
        items={[
          {
            code: "GH-01",
            label: "悬空",
            value: m?.danglingEdges ?? gh01,
            tone: (m?.danglingEdges ?? gh01) > 0 ? "bad" : "ok",
          },
          {
            code: "GH-02",
            label: "冲突",
            value: gh02,
            tone: gh02 > 0 ? "warn" : "ok",
          },
          {
            code: "GH-03",
            label: "僵尸/孤立",
            value: m?.orphanInstances ?? 0,
            tone: (m?.orphanInstances ?? 0) > 10 ? "warn" : "muted",
          },
          {
            code: "GH-04",
            label: "规则",
            value: gh04,
            tone: gh04 > 0 ? "warn" : "ok",
          },
          {
            code: "P2",
            label: "归档候选",
            value: m?.archiveCandidates ?? 0,
            tone: "muted",
          },
        ]}
      />

      {(data?.archivePreview?.length ?? 0) > 0 ? (
        <>
          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: "1.25rem" }}>
            Insight 归档候选预览
          </h2>
          <ul className="muted" style={{ fontSize: "0.8rem" }}>
            {(data?.archivePreview || []).map((p) => (
              <li key={p.id}>
                {p.id} · {p.objectId || "—"} · {p.createdAt || "—"}
              </li>
            ))}
          </ul>
        </>
      ) : null}

      <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: "1.25rem" }}>
        问题列表
      </h2>
      {issues.length === 0 ? (
        <p className="bp-prop-ok">暂无问题 · 扫描通过</p>
      ) : (
        <BpTable
          columns={["类型", "对象", "说明", "操作"]}
          rows={issues.map((i) => [
            <span
              key={`t-${i.code}`}
              className={
                i.severity === "bad"
                  ? "bp-tag bp-tag-bad"
                  : i.severity === "warn"
                    ? "bp-tag bp-tag-warn"
                    : "bp-tag"
              }
            >
              {i.code}
            </span>,
            <span key={`o-${i.code}`}>{i.object || "—"}</span>,
            <span key={`m-${i.code}`} className="muted">
              {i.message || "—"}
            </span>,
            i.href ? (
              <Link key={`h-${i.code}`} to={i.href} className="bp-action-link">
                处理 →
              </Link>
            ) : (
              <span key={`h-${i.code}`} className="muted">
                —
              </span>
            ),
          ])}
        />
      )}
      <BpLinkRow
        links={[
          { to: "/ontology/funnel", label: "看 Funnel Merge" },
          { to: "/aip/drafts", label: "Draft 审批台" },
          { to: "/ontology/link-types/new", label: "新建 Link Type" },
        ]}
      />
      </div>
    </S2Chrome>
  );
}

/** 89/94 · Funnel + 真重跑 · ?type= */
export function FunnelPage() {
  const [sp] = useSearchParams();
  const objectType = sp.get("type")?.trim() || "WorkOrder";
  const status = useJsonGet<{ objectType: string; stage: string; detail?: unknown }>(
    `/v1/funnel/${encodeURIComponent(objectType)}/status`,
  );
  const worker = useJsonGet<{
    stages: { name: string; progress: number }[];
  }>(`/v1/funnel/${encodeURIComponent(objectType)}/worker`);
  const [pipeMode, setPipeMode] = useState<"live" | "replacement">("live");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const stages = (worker.data?.stages || []).map((s, i) => {
    const labels = ["① CHANGELOG JOB", "② MERGE CHANGES JOB", "③ INDEXING JOB", "④ HYDRATION JOB"];
    const titles = ["算数据差 old→new", "Changelog + Action 用户编辑", "按 Object DB 分片 → index", "index → search nodes"];
    const p = s.progress;
    const tone = p >= 1 ? "done" : p > 0 ? "active" : "wait";
    const statusText =
      p >= 1 ? `✅ 完成 · ${Math.round(p * 100)}%` : p > 0 ? `🔄 ${Math.round(p * 100)}%` : "⏳ 等待";
    return {
      step: labels[i] || s.name,
      title: titles[i] || s.name,
      subtitle: `Funnel 托管 · ${s.name}`,
      status: statusText,
      progress: p,
      tone: tone as "done" | "active" | "wait",
    };
  });

  async function rerun() {
    setBusy(true);
    setMsg("");
    try {
      const r = await apiPost<{ stage?: string; mode?: string }>(
        `/v1/funnel/${encodeURIComponent(objectType)}/rerun`,
        { mode: pipeMode },
      );
      setMsg(`已重跑 · mode=${r.mode} · stage=${r.stage}`);
      status.reload();
      worker.reload();
    } catch (e) {
      setMsg(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <S2Chrome
      title="漏斗管道"
      lede={`${objectType} 四阶段 · Changelog → Merge → Index → Hydration`}
    >
      <div className="ont-page">
      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            status.reload();
            worker.reload();
          }}
        >
          刷新
        </button>
        <button type="button" className="btn-primary" disabled={busy} onClick={() => void rerun()}>
          {busy ? "重跑中…" : pipeMode === "replacement" ? "重跑 Replacement" : "重跑 Live"}
        </button>
        <Link to="/ontology/okf-funnel" className="btn-nav">
          OKF 映射 →
        </Link>
        <Link to="/data/builds" className="btn-nav">
          Builds 日志 →
        </Link>
        <Link to="/ontology" className="btn-nav">
          ← 本体管理
        </Link>
      </BpToolbar>
      {(status.err || worker.err) && <p className="error">{status.err || worker.err}</p>}
      {msg && <p className={msg.startsWith("已") ? "bp-prop-ok" : "error"}>{msg}</p>}

      <div className="card" style={{ marginBottom: "1rem" }}>
        <p>
          <strong>Funnel Batch · {objectType}</strong> · stage={status.data?.stage || "—"}
        </p>
        <p className="muted" style={{ fontSize: "0.8rem" }}>
          Backing: <Link to="/data/datasets">{objectType}-demo</Link> · PK: object_id · query type={objectType}
        </p>
        <div style={{ marginTop: 8 }}>
          <label className="muted" style={{ marginRight: 12 }}>
            <input type="radio" checked={pipeMode === "live"} onChange={() => setPipeMode("live")} /> Live
            pipeline
          </label>
          <label className="muted">
            <input
              type="radio"
              checked={pipeMode === "replacement"}
              onChange={() => setPipeMode("replacement")}
            />{" "}
            Replacement
          </label>
        </div>
        <p className="muted" style={{ fontSize: "0.75rem", marginTop: 8 }}>
          切换模式后点「重跑」写入 funnel_status，worker 进度从服务端读取。
        </p>
      </div>

      {stages.length > 0 ? (
        <BpStagePipeline stages={stages} />
      ) : (
        <p className="muted">加载流水线…</p>
      )}

      <BpBanner tone="warn">
        最近错误 · Type Coherence · DLQ 见{" "}
        <Link to="/data/health" className="bp-action-link">
          数据健康
        </Link>
      </BpBanner>
      <BpBanner tone="info">
        Funnel 不是 ETL，而是事务监听器——湖仓每一次 COMMIT，都驱动业务 Object 刷新。
      </BpBanner>
      </div>
    </S2Chrome>
  );
}

/** 89/94 · Wiki 可编辑 → Draft · ?type=&id= */
export function WikiPage() {
  const [sp] = useSearchParams();
  const objectType = sp.get("type")?.trim() || "WorkOrder";
  const objectId = sp.get("id")?.trim() || "wo-1001";
  const [tab, setTab] = useState("card");
  const wiki = useJsonGet<{ objectType: string; objectId: string; body: Record<string, unknown> }>(
    `/v1/wiki/${encodeURIComponent(objectType)}/${encodeURIComponent(objectId)}`,
  );
  const obj = useOntologyObject(objectType, objectId);
  const [summary, setSummary] = useState("");
  const [fieldsText, setFieldsText] = useState("{}");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    const body = wiki.data?.body || {};
    setSummary(String(body.summary || ""));
    setFieldsText(JSON.stringify((body.fields as Record<string, unknown>) || {}, null, 2));
    setDirty(false);
  }, [wiki.data]);

  async function submitDraft() {
    setBusy(true);
    setMsg("");
    setErr("");
    try {
      let fields: Record<string, unknown> = {};
      try {
        fields = JSON.parse(fieldsText || "{}") as Record<string, unknown>;
      } catch {
        throw new Error("specification 须为合法 JSON");
      }
      const d = await getOntologyClient().createDraft({
        actionTypeId: "UpdateWikiCard",
        objectType,
        objectId,
        proposed: { wikiBody: { summary, fields } },
        title: `更新 Wiki 知识卡 · ${objectId}`,
      });
      setMsg(`已创建 Draft ${d.id}（未写生产）。请到审批台通过后生效。`);
      setDirty(false);
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <S2Chrome
      title="活知识 Wiki"
      lede="可编辑知识卡 · 保存即建 Draft · 审批通过后写 wiki_page（禁止直写 PUT）"
    >
      <div className="ont-page">
      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            wiki.reload();
            obj.reload();
          }}
        >
          刷新
        </button>
        <button
          type="button"
          className="btn-primary"
          disabled={busy || !dirty}
          onClick={() => void submitDraft()}
        >
          {busy ? "提交中…" : "保存并建 Draft"}
        </button>
        <Link to="/aip/drafts" className="btn-nav-accent">
          Draft 审批台 →
        </Link>
        <Link to="/aip/tools" className="btn-nav">
          智能体管理工作台 →
        </Link>
        <Link to="/ontology" className="btn-nav">
          ← 本体管理
        </Link>
      </BpToolbar>
      {(wiki.err || obj.err || err) && <p className="error">{wiki.err || obj.err || err}</p>}
      {msg && <p className="bp-prop-ok">{msg}</p>}

      <BpTabs
        active={tab}
        onChange={setTab}
        tabs={[
          { id: "card", label: "知识卡片" },
          { id: "sync", label: "双向绑定" },
          { id: "agent", label: "Agent 读字段" },
          { id: "versions", label: "版本" },
        ]}
      />

      {tab === "card" && (
        <BpSplit
          left={
            <>
              <div className="bp-section-label">Object 挂载</div>
              <h2 className="aos-text" style={{ fontSize: "1rem" }}>
                {objectType} · {objectId}
              </h2>
              <p className="muted" style={{ fontSize: "0.75rem" }}>
                实例 PK: {objectId}
              </p>
              <h3 className="aos-text" style={{ fontSize: "0.8rem", marginTop: 12 }}>
                Object 属性（只读同步源）
              </h3>
              <ul className="card-list">
                {["title", "status", "site", "priority"].map((k) => (
                  <li key={k} className="card">
                    <span className="muted">{k}</span>
                    <div>{String(obj.data?.[k] ?? "—")}</div>
                  </li>
                ))}
              </ul>
            </>
          }
          right={
            <>
              <h2 className="aos-text" style={{ fontSize: "1rem" }}>
                LLM Wiki 知识卡片
              </h2>
              <div className="card">
                <label className="muted">标题</label>
                <input
                  className="aos-input"
                  value={summary}
                  onChange={(e) => {
                    setSummary(e.target.value);
                    setDirty(true);
                  }}
                  placeholder="工单备注标题"
                />
                <label className="muted" style={{ display: "block", marginTop: 8 }}>
                  specification（JSON）
                </label>
                <textarea
                  className="aos-input"
                  rows={6}
                  value={fieldsText}
                  onChange={(e) => {
                    setFieldsText(e.target.value);
                    setDirty(true);
                  }}
                  style={{ width: "100%", fontFamily: "monospace", fontSize: "0.75rem", resize: "vertical" }}
                />
                <p className="muted" style={{ fontSize: "0.75rem", marginTop: 8 }}>
                  {dirty ? "有未提交更改 · 保存将创建 UpdateWikiCard Draft" : "与服务端一致"}
                </p>
              </div>
            </>
          }
        />
      )}

      {tab === "sync" && (
        <BpBanner tone="info">
          双向绑定：Object 变更 → Wiki specification 刷新；Wiki 编辑 → Draft → 审批 → wiki_page。
        </BpBanner>
      )}
      {tab === "agent" && (
        <BpBanner tone="info">
          Agent 经工具读 Wiki 字段（wiki.read / tools.invoke）。配置入口：{" "}
          <Link to="/aip/tools" className="bp-action-link">
            智能体管理工作台
          </Link>
        </BpBanner>
      )}
      {tab === "versions" && (
        <WikiVersionsPanel objectType={objectType} objectId={objectId} />
      )}
      </div>
    </S2Chrome>
  );
}

type WikiVerItem = { id: number; createdAt: string; summary?: string | null; draftId?: string | null };

function WikiVersionsPanel({ objectType, objectId }: { objectType: string; objectId: string }) {
  const [items, setItems] = useState<WikiVerItem[]>([]);
  const [err, setErr] = useState("");
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);

  async function reload() {
    setBusy(true);
    setErr("");
    try {
      const res = await apiGet<{ items: WikiVerItem[] }>(
        `/v1/wiki/${encodeURIComponent(objectType)}/${encodeURIComponent(objectId)}/versions`,
      );
      setItems(res.items || []);
    } catch (e) {
      setErr(String((e as Error).message || e));
      setItems([]);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void reload();
  }, [objectType, objectId]);

  async function openVersion(id: number) {
    setBusy(true);
    setErr("");
    try {
      const res = await apiGet<{ body: Record<string, unknown>; createdAt: string; draftId?: string }>(
        `/v1/wiki/${encodeURIComponent(objectType)}/${encodeURIComponent(objectId)}/versions/${id}`,
      );
      setSelected({ ...res.body, _meta: { id, createdAt: res.createdAt, draftId: res.draftId } });
    } catch (e) {
      setErr(String((e as Error).message || e));
      setSelected(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div className="mp-section-head">
        <strong>历史版本（审批写回前快照）</strong>
        <button type="button" className="btn" disabled={busy} onClick={() => void reload()}>
          刷新
        </button>
      </div>
      {err && <p className="error">{err}</p>}
      {!err && items.length === 0 && (
        <p className="muted">暂无历史。编辑 Wiki 并经 Draft 审批通过后，会在此保留上一版快照。</p>
      )}
      {items.length > 0 && (
        <BpTable
          columns={["版本", "时间", "摘要", ""]}
          rows={items.map((v) => [
            `#${v.id}`,
            v.createdAt,
            v.summary || "—",
            <button
              key={v.id}
              type="button"
              className="bp-action-link"
              disabled={busy}
              onClick={() => void openVersion(v.id)}
            >
              查看
            </button>,
          ])}
        />
      )}
      {selected && (
        <pre className="aos-pre" style={{ marginTop: "0.75rem", maxHeight: 240, overflow: "auto" }}>
          {JSON.stringify(selected, null, 2)}
        </pre>
      )}
    </div>
  );
}

/** 89 v2 · 分支列表 / 新建 / checkout / diff / merge */
export function BranchesPage() {
  const { data, err, reload } = useJsonGet<{ items: Branch[] }>("/v1/ontology/branches");
  const [newId, setNewId] = useState("");
  const [newName, setNewName] = useState("");
  const [baseRef, setBaseRef] = useState("main");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [formErr, setFormErr] = useState("");
  const [diffBranch, setDiffBranch] = useState<string | null>(null);
  const [diffItems, setDiffItems] = useState<
    { objectType: string; objectId: string; kind: string; base?: unknown; branch?: unknown }[]
  >([]);
  const [diffErr, setDiffErr] = useState("");

  async function createBranch() {
    setBusy(true);
    setMsg("");
    setFormErr("");
    try {
      const id = newId.trim();
      if (!id) throw new Error("请填写分支 id");
      await apiPost("/v1/ontology/branches", {
        id,
        name: newName.trim() || id,
        baseRef: baseRef.trim() || "main",
      });
      setMsg(`已创建分支 ${id}`);
      setNewId("");
      setNewName("");
      reload();
    } catch (e) {
      setFormErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  async function checkoutSample(branchId: string) {
    setBusy(true);
    setMsg("");
    setFormErr("");
    try {
      await apiPost(`/v1/ontology/branches/${encodeURIComponent(branchId)}/checkout`, {
        objectType: "WorkOrder",
        objectId: "wo-1001",
        patch: { title: `[${branchId}] 分支试改 · wo-1001` },
      });
      setMsg(`已检出并改写 WorkOrder/wo-1001 → ${branchId}`);
      reload();
    } catch (e) {
      setFormErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  async function showDiff(branchId: string) {
    setBusy(true);
    setDiffErr("");
    setDiffBranch(branchId);
    try {
      const res = await apiGet<{
        items: { objectType: string; objectId: string; kind: string; base?: unknown; branch?: unknown }[];
      }>(`/v1/ontology/branches/${encodeURIComponent(branchId)}/diff`);
      setDiffItems(res.items || []);
    } catch (e) {
      setDiffItems([]);
      setDiffErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  async function mergeBranch(branchId: string) {
    if (!window.confirm(`确认将 ${branchId} 的 overlay 合并进 base（通常 main）？此操作写生产表。`)) {
      return;
    }
    setBusy(true);
    setMsg("");
    setFormErr("");
    try {
      const res = await apiPost<{ merged: number }>(
        `/v1/ontology/branches/${encodeURIComponent(branchId)}/merge`,
        {},
      );
      setMsg(`已合并 ${res.merged ?? 0} 个对象变更 → base`);
      if (diffBranch === branchId) {
        setDiffItems([]);
      }
      reload();
    } catch (e) {
      setFormErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <S2Chrome title="分支管理" lede="本体分支 · overlay 变更 · 对比 / 合并写入 base（89 v2）">
      <div className="ont-page">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <Link to="/ontology" className="btn-nav">
          ← 本体管理
        </Link>
      </BpToolbar>
      {err && <p className="error">{err}</p>}
      {msg && <p className="bp-prop-ok">{msg}</p>}
      {formErr && <p className="error">{formErr}</p>}

      <div className="card" style={{ marginBottom: "1rem" }}>
        <strong>新建分支</strong>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8, alignItems: "flex-end" }}>
          <label className="mp-field">
            <span className="mp-field-label">id</span>
            <input className="aos-input" value={newId} onChange={(e) => setNewId(e.target.value)} placeholder="feature-x" />
          </label>
          <label className="mp-field">
            <span className="mp-field-label">name</span>
            <input className="aos-input" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="功能分支" />
          </label>
          <label className="mp-field">
            <span className="mp-field-label">baseRef</span>
            <input className="aos-input" value={baseRef} onChange={(e) => setBaseRef(e.target.value)} placeholder="main" />
          </label>
          <button type="button" className="btn-primary" disabled={busy} onClick={() => void createBranch()}>
            {busy ? "创建中…" : "+ 新建分支"}
          </button>
        </div>
      </div>

      <BpTable
        columns={["分支名", "基于", "Object 变更", "状态", "操作"]}
        rows={(data?.items || []).map((b) => [
          <strong key={`n-${b.id}`}>{b.id}</strong>,
          b.baseRef || "—",
          b.readonly ? "—" : `${b.changeCount ?? 0} 处`,
          b.readonly ? <span className="aos-text">生产/只读</span> : <span className="muted">开发中</span>,
          b.readonly ? (
            <span className="muted">—</span>
          ) : (
            <span key={`ops-${b.id}`} style={{ display: "inline-flex", flexWrap: "wrap", gap: 8 }}>
              <button
                type="button"
                className="bp-action-link"
                disabled={busy}
                onClick={() => void checkoutSample(b.id)}
                title="检出 WorkOrder/wo-1001 并写入试改标题"
              >
                检出样例
              </button>
              <button type="button" className="bp-action-link" disabled={busy} onClick={() => void showDiff(b.id)}>
                对比
              </button>
              <button
                type="button"
                className="bp-action-link"
                disabled={busy || !(b.changeCount && b.changeCount > 0)}
                onClick={() => void mergeBranch(b.id)}
              >
                合并
              </button>
            </span>
          ),
        ])}
      />

      {diffBranch && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <div className="mp-section-head">
            <strong>Diff · {diffBranch}</strong>
            <button type="button" className="btn" onClick={() => setDiffBranch(null)}>
              关闭
            </button>
          </div>
          {diffErr && <p className="error">{diffErr}</p>}
          {!diffErr && diffItems.length === 0 && <p className="muted">无 overlay 变更</p>}
          {diffItems.map((d) => {
            const baseObj =
              d.base && typeof d.base === "object" ? (d.base as Record<string, unknown>) : null;
            const branchObj =
              d.branch && typeof d.branch === "object" ? (d.branch as Record<string, unknown>) : null;
            const fields = fieldDiff(baseObj, branchObj);
            return (
              <div key={`${d.objectType}/${d.objectId}`} className="ont-diff-item">
                <div className="ont-diff-head">
                  <strong>
                    {d.objectType}/{d.objectId}
                  </strong>
                  <span className={`ont-diff-kind is-${d.kind}`}>{d.kind}</span>
                  <Link
                    to={`/ontology/object-types/${encodeURIComponent(d.objectType)}`}
                    className="bp-action-link"
                  >
                    打开类型 →
                  </Link>
                </div>
                {d.kind === "deleted" && (
                  <p className="muted" style={{ margin: "0.35rem 0" }}>
                    将从 base 删除；原 props：{JSON.stringify(baseObj || {})}
                  </p>
                )}
                {d.kind === "added" && (
                  <p className="muted" style={{ margin: "0.35rem 0" }}>
                    新增对象 props：{JSON.stringify(branchObj || {})}
                  </p>
                )}
                {d.kind === "modified" && fields.length === 0 && (
                  <p className="muted" style={{ margin: "0.35rem 0" }}>
                    overlay 已跟踪，字段与 base 当前一致
                  </p>
                )}
                {fields.length > 0 && (
                  <BpTable
                    columns={["字段", "base", "branch"]}
                    rows={fields.map((f) => [f.key, f.base, f.branch])}
                  />
                )}
              </div>
            );
          })}
        </div>
      )}

      {(data?.items || []).some((b) => b.id === "sandbox") && (
        <BpBanner tone="warn">
          sandbox 为只读种子分支；请新建开发分支后「检出样例 → 对比 → 合并」。
        </BpBanner>
      )}
      <BpLinkRow links={[{ to: "/ontology", label: "本体管理" }]} />
      </div>
    </S2Chrome>
  );
}
