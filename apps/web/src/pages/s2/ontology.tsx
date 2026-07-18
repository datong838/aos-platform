import { useState } from "react";
import { Link } from "react-router-dom";
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

type Branch = { id: string; name: string; baseRef: string; readonly: boolean };

/** 77 · 对齐 ontology-graph-health.html */
export function GraphHealthPage() {
  const { data, err, reload } = useJsonGet<{
    score: number;
    metrics: {
      objectTypes: number;
      instances: number;
      edges: number;
      orphanInstances: number;
      engine: string;
    };
  }>("/v1/ontology/graph-health");

  const m = data?.metrics;
  const orphans = m?.orphanInstances ?? 0;
  const edges = m?.edges ?? 0;

  return (
    <S2Chrome
      title="图谱健康度"
      lede="对齐 ontology-graph-health · L2 运维（≠ L1 数据健康）"
    >
      <BpToolbar>
        <button type="button" className="btn" onClick={() => reload()}>
          重新扫描
        </button>
        <Link to="/data/health" className="muted">
          L1 数据健康 →
        </Link>
      </BpToolbar>
      {err && <p className="error">{err}</p>}
      <p className="muted">
        悬空链接 · 属性冲突 · 孤立对象 · 规则冲突 · score={data?.score ?? "—"}
      </p>

      <BpMetricGrid
        items={[
          { code: "GH-01", label: "悬空", value: edges > 0 ? 0 : 1, tone: edges > 0 ? "ok" : "bad" },
          { code: "GH-02", label: "冲突", value: 0, tone: "ok" },
          { code: "GH-03", label: "僵尸/孤立", value: orphans, tone: orphans > 10 ? "warn" : "muted" },
          { code: "GH-04", label: "规则", value: (data?.score ?? 100) < 80 ? 1 : 0, tone: "ok" },
          { code: "P2", label: "归档候选", value: orphans > 0 ? Math.min(orphans, 8) : 0, tone: "muted" },
        ]}
      />

      <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: "1.25rem" }}>
        问题列表
      </h2>
      <BpTable
        columns={["类型", "对象", "说明", "操作"]}
        rows={[
          ...(orphans > 0
            ? [
                [
                  <span className="bp-tag bp-tag-warn">GH-03</span>,
                  <span>孤立实例 ×{orphans}</span>,
                  <span className="muted">无 graph_edge 关联</span>,
                  <Link to="/ontology">浏览本体</Link>,
                ],
              ]
            : []),
          ...(edges === 0
            ? [
                [
                  <span className="bp-tag bp-tag-bad">GH-01</span>,
                  <span>图谱边</span>,
                  <span className="muted">edges=0 · engine={m?.engine}</span>,
                  <Link to="/workshop/graph">知识图谱</Link>,
                ],
              ]
            : []),
          [
            <span className="bp-tag">GH-04</span>,
            <span>WorkOrder 演示</span>,
            <span className="muted">seed 工单 wo-1001↔wo-1003</span>,
            <Link to="/aip/drafts">开 Draft 修复</Link>,
          ],
        ]}
      />
      <BpLinkRow
        links={[
          { to: "/ontology/funnel", label: "看 Funnel Merge" },
          { to: "/aip/drafts", label: "Draft 审批台" },
        ]}
      />
    </S2Chrome>
  );
}

/** 77 · 对齐 ontology-funnel.html */
export function FunnelPage() {
  const status = useJsonGet<{ objectType: string; stage: string; detail?: unknown }>(
    "/v1/funnel/WorkOrder/status",
  );
  const worker = useJsonGet<{
    stages: { name: string; progress: number }[];
  }>("/v1/funnel/WorkOrder/worker");
  const [pipeMode, setPipeMode] = useState<"live" | "replacement">("live");

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

  return (
    <S2Chrome title="漏斗管道" lede="对齐 ontology-funnel · WorkOrder 四阶段 · Changelog→Hydration">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => { status.reload(); worker.reload(); }}>
          刷新
        </button>
        <Link to="/ontology/okf-funnel" className="muted">
          OKF 映射 →
        </Link>
        <Link to="/data/builds" className="muted">
          Builds 日志 →
        </Link>
      </BpToolbar>
      {(status.err || worker.err) && <p className="error">{status.err || worker.err}</p>}

      <div className="card" style={{ marginBottom: "1rem" }}>
        <p>
          <strong>Funnel Batch · WorkOrder</strong> · stage={status.data?.stage || "—"}
        </p>
        <p className="muted" style={{ fontSize: "0.8rem" }}>
          Backing: <Link to="/data/datasets">WorkOrder-demo</Link> · PK: object_id
        </p>
        <label className="muted" style={{ marginRight: 12 }}>
          <input type="radio" checked={pipeMode === "live"} onChange={() => setPipeMode("live")} /> Live pipeline
        </label>
        <label className="muted">
          <input type="radio" checked={pipeMode === "replacement"} onChange={() => setPipeMode("replacement")} />{" "}
          Replacement · 后台 67%
        </label>
      </div>

      {stages.length > 0 ? (
        <BpStagePipeline stages={stages} />
      ) : (
        <p className="muted">加载流水线…</p>
      )}

      <BpBanner tone="warn">
        最近错误 · Type Coherence · demo DLQ 样例见{" "}
        <Link to="/data/health">Data Health</Link>
      </BpBanner>
      <BpBanner tone="info">
        Funnel 不是 ETL，而是事务监听器——湖仓每一次 COMMIT，都驱动业务 Object 刷新。
      </BpBanner>
    </S2Chrome>
  );
}

/** 77 · 对齐 ontology-wiki.html */
export function WikiPage() {
  const [tab, setTab] = useState("card");
  const wiki = useJsonGet<{ objectType: string; objectId: string; body: Record<string, unknown> }>(
    "/v1/wiki/WorkOrder/wo-1001",
  );
  const obj = useJsonGet<Record<string, unknown>>("/v1/objects/WorkOrder/wo-1001");

  const body = wiki.data?.body || {};
  const summary = String(body.summary || "");
  const fields = (body.fields as Record<string, unknown>) || {};

  return (
    <S2Chrome title="活知识 Wiki" lede="对齐 ontology-wiki · WIKI-001 · wo-1001 只读（写经 Draft）">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => { wiki.reload(); obj.reload(); }}>
          刷新
        </button>
        <span className="muted">Palantir Document ≠ 活 Wiki</span>
        <Link to="/ontology" className="muted">
          ← WorkOrder 列表
        </Link>
      </BpToolbar>
      {(wiki.err || obj.err) && <p className="error">{wiki.err || obj.err}</p>}

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
              <div className="bp-section-label">WIKI-001 · Object 挂载</div>
              <h2 className="aos-text" style={{ fontSize: "1rem" }}>
                WorkOrder · wo-1001
              </h2>
              <p className="muted" style={{ fontSize: "0.75rem" }}>实例 PK: wo-1001</p>
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
                <input readOnly value={summary || "工单 wo-1001 · 运营备注卡"} />
                <label className="muted" style={{ display: "block", marginTop: 8 }}>
                  specification
                </label>
                <textarea
                  readOnly
                  rows={3}
                  value={JSON.stringify(fields, null, 2)}
                  style={{ width: "100%", fontFamily: "monospace", fontSize: "0.75rem" }}
                />
                <p className="muted" style={{ fontSize: "0.7rem", marginTop: 8 }}>
                  保存 Wiki → Object 须经 Draft（PUT /v1/wiki 已禁）
                </p>
              </div>
            </>
          }
        />
      )}

      {tab === "sync" && (
        <BpBanner tone="info">
          WIKI-002 双向绑定：Object 变更 → Wiki specification 刷新；Wiki remark → Draft → Object（演示只读）。
        </BpBanner>
      )}
      {tab === "agent" && (
        <p className="muted">
          Agent 读字段：tools.invoke / wiki.read 已接 seed summary · 见{" "}
          <Link to="/aip/tools">Agent 工具面板</Link>
        </p>
      )}
      {tab === "versions" && (
        <p className="muted">版本历史 MVP 后置 · 当前仅展示最新 wiki_page 行。</p>
      )}
    </S2Chrome>
  );
}

/** 77 · 对齐 ontology-branches.html */
export function BranchesPage() {
  const { data, err, reload } = useJsonGet<{ items: Branch[] }>("/v1/ontology/branches");

  return (
    <S2Chrome title="分支管理" lede="对齐 ontology-branches · meta_branch 表格">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <span className="muted">+ 新建分支（MVP 后置）</span>
      </BpToolbar>
      {err && <p className="error">{err}</p>}

      <BpTable
        columns={["分支名", "基于", "Object 变更", "状态", "操作"]}
        rows={(data?.items || []).map((b) => [
          <strong>{b.id}</strong>,
          b.baseRef || "—",
          b.readonly ? "—" : "开发中",
          b.readonly ? <span className="aos-text">生产/只读</span> : <span className="muted">开发中</span>,
          b.readonly ? (
            <span className="muted">—</span>
          ) : (
            <>
              <button type="button" className="btn" disabled>
                合并
              </button>{" "}
              <button type="button" className="btn" disabled>
                对比
              </button>
            </>
          ),
        ])}
      />

      {(data?.items || []).some((b) => b.id === "sandbox") && (
        <BpBanner tone="warn">
          ⚠ sandbox 的 backing dataset 建议与 Dataset 分支同步合并（演示提示 · 对齐蓝图）。
        </BpBanner>
      )}
      <BpLinkRow links={[{ to: "/ontology", label: "本体管理" }]} />
    </S2Chrome>
  );
}
