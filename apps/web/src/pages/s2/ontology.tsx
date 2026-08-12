import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiGet, apiPost, apiPut } from "../../api/client";
import { getOntologyClient } from "../../api/ontologyClient";
import { queryAuthoritativeGraph } from "../../api/ontologyGraph";
import type { GraphDomain, GraphSnapshot } from "../../api/ontologyExplorerContracts";
import { useOntologyObject } from "../../api/ontologyHooks";
import { OntologyGraphCanvas } from "../../components/ontology/OntologyGraphCanvas";
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
  samples?: { objectType: string; objectId: string }[];
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
    score: number | null;
    scoreStatus?: "known" | "unknown";
    scoreVersion?: string;
    breakdown?: { code: string; affectedObjects: number; denominator: number; rate: number; threshold: number; maxDeduction: number; deduction: number }[];
    metrics: {
      objectTypes: number;
      instances: number;
      edges: number;
      orphanInstances: number;
      danglingEdges?: number;
      propConflicts?: number;
      unlinkedInstances?: number;
      requiredLinkEligible?: number;
      propertyClassification?: { canonical: number; system: number; compatibilityAlias: number; actualConflict: number };
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
  const [graphDomain, setGraphDomain] = useState<GraphDomain>("domain");
  const [graphSeedType, setGraphSeedType] = useState("Payment");
  const [graphSeedId, setGraphSeedId] = useState("");
  const [graphSnapshot, setGraphSnapshot] = useState<GraphSnapshot | null>(null);
  const [graphBusy, setGraphBusy] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [healthView, setHealthView] = useState("list");
  const [issueCodeFilter, setIssueCodeFilter] = useState("all");

  const m = data?.metrics;
  const issues = data?.issues || [];
  const gh01 = issues.filter((i) => i.code === "GH-01").length;
  const gh02 = m?.propConflicts ?? issues.filter((i) => i.code === "GH-02").length;
  const gh04 = issues.filter((i) => i.code === "GH-04").length;
  const visibleIssues = issueCodeFilter === "all" ? issues : issues.filter((issue) => issue.code === issueCodeFilter);

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

  async function inspectGraph(nextType = graphSeedType, nextId = graphSeedId, nextDomain = graphDomain) {
    setGraphBusy(true);
    setGraphError(null);
    try {
      let resolvedId = nextId.trim();
      if (!resolvedId && nextDomain === "domain") {
        const items = await getOntologyClient().listObjects(nextType);
        resolvedId = items.items[0] ? String(items.items[0].id) : "";
      }
      if (!resolvedId) {
        throw new Error(nextDomain === "operational_lineage"
          ? "运行血缘层需要填写 Task/Plan/Action/Evidence 等稳定对象 ID"
          : "当前 Object Type 没有可用于检查的真实对象");
      }
      const snapshot = await queryAuthoritativeGraph({
        seeds: [{ objectType: nextType, objectId: resolvedId }],
        hops: 2,
        maxNodes: 300,
        direction: "both",
        objectTypes: [],
        relationTypes: [],
        graphDomains: [nextDomain],
      });
      setGraphSeedType(nextType);
      setGraphSeedId(resolvedId);
      setGraphSnapshot(snapshot);
    } catch (graphInspectError) {
      setGraphSnapshot(null);
      setGraphError(String((graphInspectError as Error).message || graphInspectError));
    } finally {
      setGraphBusy(false);
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
        当前 score={data?.scoreStatus === "unknown" ? "不可判定" : (data?.score ?? "—")} · 公式={data?.scoreVersion ?? "—"} ·
        engine={m?.engine ?? "—"} · instances={m?.instances ?? "—"} · dangling={m?.danglingEdges ?? "—"} · Insight TTL={m?.insightTtlDays ?? "—"} 天
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
            label: "真实属性冲突",
            value: gh02,
            tone: gh02 > 0 ? "warn" : "ok",
          },
          {
            code: "GH-03",
            label: "必需关系缺失",
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

      <BpBanner tone={data?.scoreStatus === "unknown" ? "warn" : "info"}>
        属性分类：Canonical {m?.propertyClassification?.canonical ?? "—"} · 系统字段 {m?.propertyClassification?.system ?? "—"} ·
        兼容别名 {m?.propertyClassification?.compatibilityAlias ?? "—"} · 真实冲突 {m?.propertyClassification?.actualConflict ?? "—"}。
        普通无边对象 {m?.unlinkedInstances ?? "—"} 不直接扣分；仅 {m?.requiredLinkEligible ?? "—"} 个声明必需关系的对象进入 GH-03 分母。
      </BpBanner>
      {(data?.breakdown?.length ?? 0) > 0 && (
        <BpTable
          columns={["指标", "受影响 / 分母", "比率 / 阈值", "扣分"]}
          rows={(data?.breakdown || []).map((item) => [
            item.code,
            `${item.affectedObjects} / ${item.denominator}`,
            `${(item.rate * 100).toFixed(2)}% / ${(item.threshold * 100).toFixed(0)}%`,
            `${item.deduction} / ${item.maxDeduction}`,
          ])}
        />
      )}

      <BpTabs
        tabs={[{ id: "list", label: "问题列表" }, { id: "graph", label: "问题图谱" }]}
        active={healthView}
        onChange={setHealthView}
      />

      {healthView === "graph" && <section className="ont-section" aria-labelledby="graph-inspector-title">
        <h2 id="graph-inspector-title" className="aos-text" style={{ fontSize: "0.875rem" }}>
          权威图检查器
        </h2>
        <p className="muted" style={{ fontSize: "0.8rem" }}>
          Domain Graph 与 Operational Lineage 分层读取；每个快照只包含一个图域，不在前端混写事实。
        </p>
        <BpToolbar>
          <label>
            图域
            <select
              aria-label="图检查器图域"
              value={graphDomain}
              onChange={(event) => {
                setGraphDomain(event.target.value as GraphDomain);
                setGraphSnapshot(null);
                setGraphError(null);
              }}
            >
              <option value="domain">领域知识图谱</option>
              <option value="operational_lineage">运行血缘图</option>
            </select>
          </label>
          <label>
            对象类型
            <input aria-label="图检查器对象类型" value={graphSeedType} onChange={(event) => setGraphSeedType(event.target.value)} />
          </label>
          <label>
            稳定对象 ID
            <input
              aria-label="图检查器对象 ID"
              value={graphSeedId}
              placeholder={graphDomain === "domain" ? "留空自动选择首个真实对象" : "必须填写"}
              onChange={(event) => setGraphSeedId(event.target.value)}
            />
          </label>
          <button type="button" className="btn" disabled={graphBusy || !graphSeedType.trim()} onClick={() => void inspectGraph()}>
            {graphBusy ? "读取中…" : "读取权威快照"}
          </button>
        </BpToolbar>
        {graphError && <p className="error" role="alert">{graphError}</p>}
        {(graphSnapshot || graphBusy) && (
          <OntologyGraphCanvas
            snapshot={graphSnapshot}
            loading={graphBusy}
            error={graphError}
            onExpandNode={(node) => void inspectGraph(node.objectType, node.objectId)}
          />
        )}
      </section>}

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

      {healthView === "list" && <>
      <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: "1.25rem" }}>问题列表</h2>
      <label className="muted">
        问题类型
        <select aria-label="图谱健康问题类型" value={issueCodeFilter} onChange={(event) => setIssueCodeFilter(event.target.value)}>
          <option value="all">全部</option>
          <option value="GH-01">GH-01 悬空端点</option>
          <option value="GH-02">GH-02 真实属性冲突</option>
          <option value="GH-03">GH-03 必需关系缺失</option>
          <option value="GH-04">GH-04 治理规则</option>
        </select>
      </label>
      {visibleIssues.length === 0 ? (
        <p className="bp-prop-ok">暂无问题 · 扫描通过</p>
      ) : (
        <BpTable
          columns={["类型", "对象", "说明", "操作"]}
          rows={visibleIssues.map((i) => [
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
            i.samples?.[0] ? (
              <button key={`h-${i.code}`} type="button" className="bp-action-link" onClick={() => {
                setHealthView("graph");
                setGraphDomain("domain");
                void inspectGraph(i.samples![0].objectType, i.samples![0].objectId, "domain");
              }}>
                图中定位 →
              </button>
            ) : i.href ? (
              <Link key={`h-${i.code}`} to={i.href} className="bp-action-link">处理 →</Link>
            ) : (
              <span key={`h-${i.code}`} className="muted">
                —
              </span>
            ),
          ])}
        />
      )}
      </>}
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
  const [sp, setSp] = useSearchParams();
  const objectType = sp.get("type")?.trim() || "";
  const objectTypes = useJsonGet<{ items: { id: string; name: string }[] }>(
    "/v1/ontology/object-types",
  );
  const status = useJsonGet<{ objectType: string; stage: string; detail?: { mode?: string; receiptId?: string; rerunAt?: string; failures?: unknown[] } }>(
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
      const r = await apiPost<{ stage?: string; mode?: string; receiptId?: string; rerunAt?: string }>(
        `/v1/funnel/${encodeURIComponent(objectType)}/rerun`,
        { mode: pipeMode },
      );
      const verified = await apiGet<{ objectType: string; stage: string; detail?: { mode?: string; receiptId?: string; rerunAt?: string } }>(
        `/v1/funnel/${encodeURIComponent(objectType)}/status`,
      );
      if (!r.receiptId || verified.detail?.receiptId !== r.receiptId || verified.stage !== r.stage) {
        throw new Error("Funnel 重跑回读与 Receipt 不一致");
      }
      setMsg(`已重跑并回读 · ${r.mode} · ${r.stage} · Receipt ${r.receiptId.slice(0, 8)}`);
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
      lede={`${objectType || "请选择对象类型"} · Changelog → Merge → Index → Hydration`}
    >
      <div className="ont-page">
      <BpToolbar>
        <label className="muted">
          对象类型
          <select
            aria-label="选择 Funnel 对象类型"
            value={objectType}
            onChange={(event) => {
              const next = new URLSearchParams(sp);
              if (event.target.value) next.set("type", event.target.value);
              else next.delete("type");
              setSp(next, { replace: true });
            }}
          >
            <option value="">请选择对象类型</option>
            {(objectTypes.data?.items || []).map((item) => (
              <option key={item.id} value={item.id}>{item.name || item.id}</option>
            ))}
          </select>
        </label>
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
        <p className="muted" style={{ fontSize: "0.75rem", marginTop: 8 }}>
          最近 Receipt: {status.data?.detail?.receiptId || "—"} · 重跑时间: {status.data?.detail?.rerunAt || "—"}
        </p>
      </div>

      {!objectType ? (
        <p className="muted">请选择对象类型后查看权威 Funnel 四阶段状态。</p>
      ) : status.loading || worker.loading ? (
        <p className="muted">加载流水线…</p>
      ) : status.err || worker.err ? (
        <p className="error">流水线状态读取失败，请检查上方错误后重试。</p>
      ) : stages.length > 0 ? (
        <BpStagePipeline stages={stages} />
      ) : (
        <p className="muted">当前对象类型暂无阶段状态。</p>
      )}

      <BpBanner tone={(status.data?.detail?.failures?.length || 0) > 0 ? "warn" : "info"}>
        失败证据 · {(status.data?.detail?.failures?.length || 0) > 0
          ? `${status.data?.detail?.failures?.length} 条，前往数据健康查看`
          : "当前权威状态未报告失败"} · {" "}
        <Link to="/data/health" className="bp-action-link">数据健康</Link>
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
  const [sp, setSp] = useSearchParams();
  const objectType = sp.get("type")?.trim() || "";
  const objectId = sp.get("id")?.trim() || "";
  const [tab, setTab] = useState("card");
  const objectTypes = useJsonGet<{ items: { id: string; name: string }[] }>("/v1/ontology/object-types");
  const subjects = useJsonGet<{ items: { objectId: string; displayLabel?: string; sourceRecordLabel?: string; covered: boolean }[] }>(
    objectType ? `/v1/wiki/${encodeURIComponent(objectType)}/coverage-index?limit=200` : null,
  );
  const wiki = useJsonGet<{ objectType: string; objectId: string; body: Record<string, unknown>; exists?: boolean }>(
    objectType && objectId
      ? `/v1/wiki/${encodeURIComponent(objectType)}/${encodeURIComponent(objectId)}?allowMissing=true`
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
        <label className="muted">
          对象类型
          <select aria-label="Wiki 对象类型" value={objectType} onChange={(event) => {
            const next = new URLSearchParams(sp);
            if (event.target.value) next.set("type", event.target.value); else next.delete("type");
            next.delete("id");
            setSp(next, { replace: true });
          }}>
            <option value="">请选择对象类型</option>
            {(objectTypes.data?.items || []).map((item) => <option key={item.id} value={item.id}>{item.name || item.id}</option>)}
          </select>
        </label>
        <label className="muted">
          业务对象
          <select aria-label="Wiki 业务对象" value={objectId} disabled={!objectType || subjects.loading} onChange={(event) => {
            const next = new URLSearchParams(sp);
            if (event.target.value) next.set("id", event.target.value); else next.delete("id");
            setSp(next, { replace: true });
          }}>
            <option value="">{subjects.loading ? "加载对象中…" : "请选择业务对象"}</option>
            {(subjects.data?.items || []).map((item) => <option key={item.objectId} value={item.objectId}>{item.displayLabel || item.sourceRecordLabel || item.objectId}{item.covered ? " · 已有知识" : " · 知识缺口"}</option>)}
          </select>
        </label>
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
        <Link to="/aip/memory-governance" className="btn-nav">
          记忆与知识治理 →
        </Link>
        <Link to="/ontology" className="btn-nav">
          ← 本体管理
        </Link>
      </BpToolbar>
      {(objectTypes.err || subjects.err || wiki.err || obj.err || err) && <p className="error">{objectTypes.err || subjects.err || wiki.err || obj.err || err}</p>}
      {msg && <p className="bp-prop-ok">{msg}</p>}

      {!objectType || !objectId ? (
        <BpBanner tone="info">
          请在上方选择真实对象类型和业务对象，或从 <Link to="/workshop/graph">对象探索</Link> 深链进入。
          本页不再默认绑定测试 WorkOrder。
        </BpBanner>
      ) : null}
      {objectType && objectId && wiki.data?.exists === false ? (
        <BpBanner tone="info">当前业务对象尚无知识卡，这是可补充的知识缺口，不是请求错误。填写后保存将创建 Draft，审批通过才写入生产 Wiki。</BpBanner>
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
                {String(obj.data?._displayLabel || `${objectType} · ${objectId}`)}
              </h2>
              <p className="muted" style={{ fontSize: "0.75rem" }}>
                实例 PK: {objectId}
              </p>
              <h3 className="aos-text" style={{ fontSize: "0.8rem", marginTop: 12 }}>
                Object 属性（只读同步源）
              </h3>
              <ul className="card-list">
                {Object.keys(obj.data || {}).filter((key) => !key.startsWith("_") && key !== "id" && key !== "type").slice(0, 8).map((k) => (
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
                  placeholder={`${String(obj.data?._displayLabel || objectType)} · 运营知识摘要`}
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
          Agent 经工具读 Wiki 字段（wiki.read / tools.invoke）；进入运行上下文前还须经过 Memory authority 的 scope、freshness、applicability、marking 与 Citation 校验。配置入口：{" "}
          <Link to="/aip/tools" className="bp-action-link">
            Agent 工具面板
          </Link>
          {" · "}<Link to="/aip/memory-governance" className="bp-action-link">查看治理与 Citation</Link>
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
  ontology_overlay_set_hash?: string;
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
  base_schema_sha256?: string;
  visible_properties?: string[] | null;
  extended_properties?: Record<string, unknown>;
  policies?: Record<string, unknown> | null;
};

export function overlayIfMatch(item: Pick<OverlayHistoryItem, "ontology_revision" | "base_schema_sha256">): string {
  if (!item.base_schema_sha256) throw new Error("Overlay 缺少 base schema hash，不能执行 CAS 写入");
  return `\"ontology-overlay-v1:${item.ontology_revision}:${item.base_schema_sha256}\"`;
}

function overlayFieldSummary(value: unknown): string {
  if (value == null) return "—";
  if (Array.isArray(value)) return value.length ? value.join("、") : "空";
  if (typeof value === "object") {
    const keys = Object.keys(value as Record<string, unknown>);
    return keys.length ? keys.join("、") : "空";
  }
  return String(value);
}

export function overlayDiffRows(current: OverlayHistoryItem, previous: OverlayHistoryItem | null) {
  return [
    ["模式", current.mode, previous?.mode || "无历史"],
    ["显示名", current.display_name || "继承安装模板", previous?.display_name || (previous ? "继承安装模板" : "无历史")],
    ["可见属性", overlayFieldSummary(current.visible_properties), overlayFieldSummary(previous?.visible_properties)],
    ["扩展属性", overlayFieldSummary(current.extended_properties), overlayFieldSummary(previous?.extended_properties)],
    ["组织策略", overlayFieldSummary(current.policies), overlayFieldSummary(previous?.policies)],
  ];
}

/** O1-R4 · 安装绑定的组织 Overlay 不可变历史。 */
export function BranchesPage() {
  const [composition, setComposition] = useState<OverlayComposition | null>(null);
  const [history, setHistory] = useState<OverlayHistoryItem[]>([]);
  const [active, setActive] = useState<OverlayHistoryItem[]>([]);
  const [target, setTarget] = useState("all");
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

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
      const [response, activeResponse] = await Promise.all([
        apiGet<{ items: OverlayHistoryItem[] }>(`/v1/ontology/installations/${encodeURIComponent(nextComposition.installation_pk)}/overlays/history`),
        apiGet<{ items: OverlayHistoryItem[] }>(`/v1/ontology/installations/${encodeURIComponent(nextComposition.installation_pk)}/overlays`),
      ]);
      setHistory(response.items || []);
      setActive(activeResponse.items || []);
    } catch (e) {
      setComposition(null);
      setHistory([]);
      setActive([]);
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
  const selectedHistory = target === "all" ? [] : visible;
  const current = selectedHistory.find((item) => item.is_active) || null;
  const previous = selectedHistory.find((item) => !item.is_active) || null;

  async function resetToInherit(item: OverlayHistoryItem) {
    if (!composition || item.mode !== "override" || !item.base_schema_sha256) return;
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      const expected = overlayIfMatch(item);
      await apiPut(
        `/v1/ontology/installations/${encodeURIComponent(composition.installation_pk)}/overlays/${item.target_kind}/${encodeURIComponent(item.target_id)}`,
        { mode: "inherit" },
        { "If-Match": expected, "Idempotency-Key": `ontology-reset-${crypto.randomUUID()}` },
      );
      const verified = await apiGet<{ items: OverlayHistoryItem[] }>(
        `/v1/ontology/installations/${encodeURIComponent(composition.installation_pk)}/overlays`,
      );
      const next = verified.items.find((candidate) => candidate.target_kind === item.target_kind && candidate.target_id === item.target_id);
      if (!next || next.mode !== "inherit" || next.ontology_revision !== item.ontology_revision + 1) {
        throw new Error("恢复安装模板后回读不一致");
      }
      setMsg(`已恢复 ${item.target_kind}:${item.target_id} 为安装模板继承 · r${next.ontology_revision}`);
      await reload();
    } catch (error) {
      setErr(String((error as Error).message || error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <S2Chrome title="组织定制 Overlay" lede="Installation 绑定 · 组织定制 · 不可变修订历史（不是代码分支）">
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
      {msg && <p className="bp-prop-ok">{msg}</p>}
      {composition ? (
        <>
          <BpMetricGrid items={[
            { label: "Installation", value: composition.installation_pk.slice(0, 8) },
            { label: "安装修订", value: composition.installation_revision },
            { label: "Overlay 修订", value: history.length },
            { label: "当前生效", value: active.length },
          ]} />
          <BpBanner tone="info">
            平台模板保持只读。组织定制通过强 ETag/CAS 与 Idempotency-Key 生成不可变修订；
            “恢复安装模板”会追加 inherit 修订，不删除历史。当前合成 ETag：
            <code>{composition.composed_schema_etag}</code>；Overlay 集合：
            <code>{composition.ontology_overlay_set_hash || "sha256:未返回"}</code>。
          </BpBanner>
          <label className="mp-field" style={{ maxWidth: 360, margin: "1rem 0" }}>
            <span className="mp-field-label">筛选目标</span>
            <select className="aos-input" value={target} onChange={(event) => setTarget(event.target.value)}>
              <option value="all">全部目标</option>
              {targets.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          {current && (
            <div className="card" style={{ marginBottom: "1rem" }}>
              <h2 className="aos-text" style={{ fontSize: "0.9rem", marginTop: 0 }}>当前与上一修订差异</h2>
              <BpTable
                columns={["字段", "当前修订", "上一修订"]}
                rows={overlayDiffRows(current, previous)}
              />
              {current.mode === "override" && (
                <button type="button" className="btn-outline-cyan" disabled={busy} onClick={() => void resetToInherit(current)}>
                  恢复安装模板（保留历史）
                </button>
              )}
            </div>
          )}
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
