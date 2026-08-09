import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiGet, apiPost } from "../../api/client";
import { getOntologyClient } from "../../api/ontologyClient";
import { useOntologyObject } from "../../api/ontologyHooks";
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

type GhIssue = {
  code: string;
  severity?: string;
  object?: string;
  message?: string;
  href?: string;
};

type TtlCandidate = {
  id: string;
  objectType?: string;
  objectId?: string;
  createdAt?: string;
  status?: string;
};

type TtlRunResult = {
  dryRun: boolean;
  ttlDays: number;
  candidateCount: number;
  archivedCount: number;
  archivedIds: string[];
  candidates: TtlCandidate[];
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
  const [ttlPreview, setTtlPreview] = useState<TtlRunResult | null>(null);

  const m = data?.metrics;
  const issues = data?.issues || [];
  const gh01 = issues.filter((i) => i.code === "GH-01").length;
  const gh02 = m?.propConflicts ?? issues.filter((i) => i.code === "GH-02").length;
  const gh04 = issues.filter((i) => i.code === "GH-04").length;

  async function previewTtl() {
    setTtlBusy(true);
    setTtlMsg("");
    setTtlPreview(null);
    try {
      const out = await apiPost<TtlRunResult>("/v1/ops/ttl/run", { dryRun: true });
      if (!out.dryRun) throw new Error("TTL 预览回包未标记 dryRun，已停止");
      if (out.candidateCount !== out.candidates.length) {
        throw new Error("TTL 候选预览不完整，无法冻结影响范围");
      }
      setTtlPreview(out);
      setTtlMsg(
        out.candidateCount === 0
          ? `TTL ${out.ttlDays} 天规则：无归档候选`
          : `TTL ${out.ttlDays} 天规则：已冻结 ${out.candidateCount} 个软归档候选，等待确认`,
      );
    } catch (e) {
      setTtlMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setTtlBusy(false);
    }
  }

  async function confirmTtl() {
    if (!ttlPreview || ttlPreview.candidateCount === 0) return;
    const snapshot = ttlPreview;
    const snapshotIds = snapshot.candidates.map((candidate) => candidate.id);
    setTtlBusy(true);
    setTtlMsg("");
    try {
      const out = await apiPost<TtlRunResult>("/v1/ops/ttl/run", { dryRun: false });
      const returnedIds = out.candidates.map((candidate) => candidate.id);
      const archivedIds = [...out.archivedIds].sort();
      if (
        out.dryRun ||
        out.candidateCount !== snapshot.candidateCount ||
        JSON.stringify(returnedIds) !== JSON.stringify(snapshotIds) ||
        out.archivedCount !== snapshot.candidateCount ||
        JSON.stringify(archivedIds) !== JSON.stringify([...snapshotIds].sort())
      ) {
        throw new Error("TTL 执行回包与冻结快照不一致，未确认归档成功");
      }
      setTtlPreview(null);
      setTtlMsg(`TTL 归档完成：已软归档 ${out.archivedCount} · 未物理删除核心对象`);
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
          onClick={() => void previewTtl()}
        >
          {ttlBusy ? "处理中…" : "运行 TTL 归档"}
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
      {ttlPreview ? (
        <section
          role="dialog"
          aria-label="TTL 归档确认"
          data-testid="ttl-confirmation"
          className="bp-banner"
        >
          <strong>确认 Insight TTL 软归档</strong>
          <p className="muted" style={{ margin: "0.5rem 0" }}>
            TTL {ttlPreview.ttlDays} 天 · 候选 {ttlPreview.candidateCount} 项。该操作只做可回放的软归档，
            不会物理删除核心业务 Object。
          </p>
          {ttlPreview.candidates.length > 0 ? (
            <ul className="muted" style={{ fontSize: "0.8rem" }}>
              {ttlPreview.candidates.map((candidate) => (
                <li key={candidate.id}>
                  {candidate.id} · {candidate.objectId || "—"} · {candidate.createdAt || "—"}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">无候选，不能执行归档。</p>
          )}
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              type="button"
              className="btn-primary"
              disabled={ttlBusy || ttlPreview.candidateCount === 0}
              onClick={() => void confirmTtl()}
            >
              {ttlBusy ? "执行中…" : `确认归档 ${ttlPreview.candidateCount} 项`}
            </button>
            <button
              type="button"
              className="btn"
              disabled={ttlBusy}
              onClick={() => {
                setTtlPreview(null);
                setTtlMsg("已取消 TTL 归档，未执行写操作");
              }}
            >
              取消
            </button>
          </div>
        </section>
      ) : null}
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
  const objectType = sp.get("type")?.trim() || "";
  const status = useJsonGet<{ objectType: string; stage: string; detail?: unknown }>(
    objectType ? `/v1/funnel/${encodeURIComponent(objectType)}/status` : null,
  );
  const worker = useJsonGet<{
    stages: { name: string; progress: number }[];
  }>(objectType ? `/v1/funnel/${encodeURIComponent(objectType)}/worker` : null);
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
    if (!objectType) return;
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
        <button type="button" className="btn-primary" disabled={busy || !objectType} onClick={() => void rerun()}>
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
      {!objectType && (
        <BpBanner tone="info">
          尚未选择 Object Type。请先到 <Link to="/workshop/graph">对象探索</Link> 选择真实对象类型，
          再进入 Funnel；本页不再默认绑定测试 WorkOrder。
        </BpBanner>
      )}

      <div className="card" style={{ marginBottom: "1rem" }}>
        <p>
          <strong>Funnel Batch · {objectType}</strong> · stage={status.data?.stage || "—"}
        </p>
        <p className="muted" style={{ fontSize: "0.8rem" }}>
          Backing: <Link to="/data/datasets">查看真实数据集</Link> · PK: object_id · query type={objectType || "未选择"}
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
  const objectType = sp.get("type")?.trim() || "";
  const objectId = sp.get("id")?.trim() || "";
  const [tab, setTab] = useState("card");
  const wiki = useJsonGet<{ objectType: string; objectId: string; body: Record<string, unknown> }>(
    objectType && objectId
      ? `/v1/wiki/${encodeURIComponent(objectType)}/${encodeURIComponent(objectId)}`
      : null,
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
          Agent 工具面板 →
        </Link>
        <Link to="/ontology" className="btn-nav">
          ← 本体管理
        </Link>
      </BpToolbar>
      {(wiki.err || obj.err || err) && <p className="error">{wiki.err || obj.err || err}</p>}
      {msg && <p className="bp-prop-ok">{msg}</p>}

      {!objectType || !objectId ? (
        <BpBanner tone="info">
          尚未选择对象。请先到 <Link to="/workshop/graph">对象探索</Link> 选择真实 Object，
          再从右侧进入 Wiki；本页不再默认绑定不存在的 WorkOrder/wo-1001。
        </BpBanner>
      ) : null}

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

      {objectType && objectId && tab === "card" && (
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
            Agent 工具面板
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
  // Phase E-14: 版本对比
  const [compareIds, setCompareIds] = useState<number[]>([]);
  const [diffResult, setDiffResult] = useState<{ left: Record<string, unknown>; right: Record<string, unknown> } | null>(null);

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

  // Phase E-14: 版本对比
  function toggleCompare(id: number) {
    setCompareIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 2) return [prev[1], id];
      return [...prev, id];
    });
    setDiffResult(null);
  }

  async function runCompare() {
    if (compareIds.length !== 2) return;
    setBusy(true);
    setErr("");
    try {
      const [a, b] = await Promise.all([
        apiGet<{ body: Record<string, unknown> }>(
          `/v1/wiki/${encodeURIComponent(objectType)}/${encodeURIComponent(objectId)}/versions/${compareIds[0]}`,
        ),
        apiGet<{ body: Record<string, unknown> }>(
          `/v1/wiki/${encodeURIComponent(objectType)}/${encodeURIComponent(objectId)}/versions/${compareIds[1]}`,
        ),
      ]);
      setDiffResult({ left: a.body, right: b.body });
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  // 计算字段差异
  const diffFields = diffResult
    ? Object.keys({ ...diffResult.left, ...diffResult.right }).map((key) => {
        const leftVal = JSON.stringify(diffResult.left[key] ?? null);
        const rightVal = JSON.stringify(diffResult.right[key] ?? null);
        return { key, left: leftVal, right: rightVal, changed: leftVal !== rightVal };
      })
    : [];

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
        <>
          <BpTable
            columns={["版本", "时间", "摘要", "查看", "对比"]}
            rows={items.map((v) => [
              `#${v.id}`,
              v.createdAt,
              v.summary || "—",
              <button
                key={`view-${v.id}`}
                type="button"
                className="bp-action-link"
                disabled={busy}
                onClick={() => void openVersion(v.id)}
              >
                查看
              </button>,
              <input
                key={`cmp-${v.id}`}
                type="checkbox"
                checked={compareIds.includes(v.id)}
                onChange={() => toggleCompare(v.id)}
                disabled={busy}
                aria-label={`对比版本 ${v.id}`}
              />,
            ])}
          />
          {/* Phase E-14: 版本对比操作栏 */}
          {compareIds.length > 0 && (
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
              <span className="muted" style={{ fontSize: "0.75rem" }}>
                已选 {compareIds.length}/2 版本：{compareIds.map((id) => `#${id}`).join(" vs ")}
              </span>
              <button
                type="button"
                className="btn"
                disabled={busy || compareIds.length !== 2}
                onClick={() => void runCompare()}
              >
                对比
              </button>
              <button type="button" className="btn-nav" onClick={() => { setCompareIds([]); setDiffResult(null); }}>
                清除
              </button>
            </div>
          )}
          {/* Phase E-14: Diff 视图 */}
          {diffResult && (
            <div style={{ marginTop: 12 }}>
              <h4 className="aos-text" style={{ fontSize: "0.8rem" }}>字段差异（#{compareIds[0]} → #{compareIds[1]}）</h4>
              <table className="bp-pipe-schema-table" style={{ width: "100%" }}>
                <thead>
                  <tr>
                    <th>字段</th>
                    <th>#{compareIds[0]}</th>
                    <th>#{compareIds[1]}</th>
                  </tr>
                </thead>
                <tbody>
                  {diffFields.map((f) => (
                    <tr key={f.key} style={{ background: f.changed ? "rgba(91, 141, 239, 0.1)" : undefined }}>
                      <td className="mono" style={{ fontWeight: f.changed ? 600 : 400 }}>{f.key}</td>
                      <td className={f.changed ? "aos-text" : "muted"} style={{ fontSize: "0.75rem" }}>{f.left}</td>
                      <td className={f.changed ? "aos-text" : "muted"} style={{ fontSize: "0.75rem" }}>{f.right}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
      {selected && (
        <pre className="aos-pre" style={{ marginTop: "0.75rem", maxHeight: 240, overflow: "auto" }}>
          {JSON.stringify(selected, null, 2)}
        </pre>
      )}
    </div>
  );
}

type OverlayComposition = {
  installation_pk: string;
  installation_revision: number;
  composed_schema_etag: string;
};

type OverlayHistoryItem = {
  target_kind: "ObjectType" | "LinkType";
  target_id: string;
  ontology_revision: number;
  mode: "override" | "inherit";
  display_name?: string | null;
  is_active: boolean;
  actor?: string;
  created_at?: string;
};

/** O1-R4 · 安装绑定的组织 Overlay 不可变历史。 */
export function BranchesPage() {
  const [composition, setComposition] = useState<OverlayComposition | null>(null);
  const [history, setHistory] = useState<OverlayHistoryItem[]>([]);
  const [target, setTarget] = useState("all");
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState("");

  async function reload() {
    setBusy(true);
    setErr("");
    try {
      const types = await apiGet<{ composition?: OverlayComposition | null }>(
        "/v1/ontology/object-types",
      );
      const nextComposition = types.composition || null;
      setComposition(nextComposition);
      if (!nextComposition) {
        setHistory([]);
        return;
      }
      const response = await apiGet<{ items: OverlayHistoryItem[] }>(
        `/v1/ontology/installations/${encodeURIComponent(nextComposition.installation_pk)}/overlays/history`,
      );
      setHistory(response.items || []);
    } catch (e) {
      setComposition(null);
      setHistory([]);
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  const targets = Array.from(new Set(history.map((item) => `${item.target_kind}:${item.target_id}`)));
  const visible = target === "all"
    ? history
    : history.filter((item) => `${item.target_kind}:${item.target_id}` === target);

  return (
    <S2Chrome title="分支与 Overlay" lede="Installation 绑定 · 组织定制 · 不可变修订历史">
      <div className="ont-page">
      <BpToolbar>
        <button type="button" className="btn" disabled={busy} onClick={() => void reload()}>
          {busy ? "刷新中…" : "刷新"}
        </button>
        <Link to="/ontology" className="btn-nav">
          管理组织定制 →
        </Link>
      </BpToolbar>
      {err && <p className="error">{err}</p>}
      {composition ? (
        <>
          <BpMetricGrid items={[
            { label: "Installation", value: composition.installation_pk.slice(0, 8) },
            { label: "安装修订", value: composition.installation_revision },
            { label: "Overlay 修订", value: history.length },
            { label: "当前生效", value: history.filter((item) => item.is_active).length },
          ]} />
          <BpBanner tone="info">
            平台模板保持只读。组织定制通过强 ETag/CAS 与 Idempotency-Key 生成不可变修订；
            “恢复安装模板”会追加 inherit 修订，不删除历史。
          </BpBanner>
          <label className="mp-field" style={{ maxWidth: 360, margin: "1rem 0" }}>
            <span className="mp-field-label">筛选目标</span>
            <select className="aos-input" value={target} onChange={(event) => setTarget(event.target.value)}>
              <option value="all">全部目标</option>
              {targets.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <BpTable
            columns={["目标", "修订", "模式", "显示名", "状态", "操作者 / 时间"]}
            rows={visible.map((item) => [
              <strong key={`${item.target_kind}-${item.target_id}`}>{item.target_kind}:{item.target_id}</strong>,
              item.ontology_revision,
              item.mode,
              item.display_name || "继承安装模板",
              item.is_active ? <span className="aos-text">当前生效</span> : <span className="muted">历史</span>,
              `${item.actor || "—"} · ${item.created_at ? new Date(item.created_at).toLocaleString() : "—"}`,
            ])}
          />
          {!busy && history.length === 0 && (
            <p className="muted">当前组织尚未创建本体定制；所有类型均继承当前安装模板。</p>
          )}
        </>
      ) : !busy && !err ? (
        <BpBanner tone="warn">当前工作区没有可用的电商领域包 Installation，无法创建组织 Overlay。</BpBanner>
      ) : null}
      <BpLinkRow links={[{ to: "/ontology", label: "本体管理与组织定制" }]} />
      </div>
    </S2Chrome>
  );
}
