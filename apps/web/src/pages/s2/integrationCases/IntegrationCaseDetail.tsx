import type { IntegrationCaseError } from "../../../api/integrationCases/errors";
import type {
  IntegrationBlocker,
  IntegrationCaseDetail as IntegrationCaseDetailResponse,
  IntegrationEvidenceSummary,
  IntegrationStageGate,
} from "../../../api/integrationCases/types";
import { businessCaseName } from "./IntegrationCaseCatalog";

export type IntegrationCaseReadStatus =
  | "idle"
  | "loading"
  | "ready"
  | "empty"
  | "forbidden"
  | "not_visible_or_missing"
  | "error"
  | "stale"
  | "refreshing";

/** Structural view contract; compatible with the single read model owned by W1. */
export interface IntegrationCaseReadViewState<T> {
  data: T | null;
  status: IntegrationCaseReadStatus;
  error: IntegrationCaseError | null;
}

export interface IntegrationCaseDetailProps {
  state: IntegrationCaseReadViewState<IntegrationCaseDetailResponse>;
  onRetry?: () => void;
  onCreateSnapshot?: () => void;
  snapshotPending?: boolean;
  snapshotError?: string | null;
}

const panelStyle = {
  border: "1px solid var(--aos-border)",
  borderRadius: 3,
  padding: 12,
} as const;

const STAGE_LABELS = {
  planned: "已规划",
  connection_verified: "连接已验证",
  data_verified: "数据已验证",
  ontology_verified: "本体已验证",
  logic_verified: "逻辑已验证",
  workshop_verified: "工作台已验证",
  production_ready: "生产就绪",
  production_active: "生产活跃",
} as const;

const GATE_STATUS_LABELS = {
  satisfied: "已满足",
  blocked: "受阻",
  not_evaluated: "未评估",
} as const;

function Retry({ onRetry }: { onRetry?: () => void }) {
  if (!onRetry) return null;
  return <button type="button" className="btn" onClick={onRetry}>重试读取</button>;
}

function Failure({ state, onRetry }: IntegrationCaseDetailProps) {
  if (state.status === "forbidden") {
    return <div role="alert"><strong>无权查看接入案例详情</strong><p>请申请接入案例读取权限。</p><Retry onRetry={onRetry} /></div>;
  }
  if (state.status === "not_visible_or_missing") {
    return <div role="alert"><strong>接入案例不可见或不存在</strong><p>为避免泄漏，不区分不存在与不可见。</p><Retry onRetry={onRetry} /></div>;
  }
  if (state.status === "error") {
    return (
      <div role="alert">
        <strong>接入案例详情读取失败</strong>
        <p>{state.error?.message ?? "未知读取错误"}</p>
        {state.error?.code && <p>错误代码：<code>{state.error.code}</code></p>}
        <Retry onRetry={onRetry} />
      </div>
    );
  }
  return null;
}

function Refs({ values, emptyText = "无" }: { values: string[]; emptyText?: string }) {
  if (values.length === 0) return <span>{emptyText}</span>;
  return <ul>{values.map((value) => <li key={value}><code>{value}</code></li>)}</ul>;
}

function StageGate({ gate }: { gate: IntegrationStageGate }) {
  return (
    <li data-stage={gate.stage} data-gate-status={gate.status}>
      <strong>{STAGE_LABELS[gate.stage]}</strong>
      <dl>
        <div><dt>服务端状态</dt><dd>{GATE_STATUS_LABELS[gate.status]}（<code>{gate.status}</code>）</dd></div>
        <div><dt>Evidence 引用</dt><dd><Refs values={gate.evidenceRefs} /></dd></div>
        <div><dt>原因引用</dt><dd><Refs values={gate.reasonRefs} /></dd></div>
      </dl>
    </li>
  );
}

function Evidence({ evidence }: { evidence: IntegrationEvidenceSummary }) {
  return (
    <li data-evidence-id={evidence.evidenceId}>
      <strong>{evidence.evidenceType} · {evidence.outcome}</strong>
      <dl>
        <div><dt>Evidence ID / revision</dt><dd><code>{evidence.evidenceId}</code> / {evidence.revision}</dd></div>
        <div><dt>Subject 引用</dt><dd><code>{evidence.subjectRef}</code></dd></div>
        <div><dt>Artifact hash</dt><dd><code>{evidence.artifactHash}</code></dd></div>
        <div><dt>Evidence hash</dt><dd><code>{evidence.evidenceHash}</code></dd></div>
        <div><dt>观测时间</dt><dd><time dateTime={evidence.observedAt}>{evidence.observedAt}</time></dd></div>
        <div><dt>到期时间</dt><dd>{evidence.expiresAt ? <time dateTime={evidence.expiresAt}>{evidence.expiresAt}</time> : "无"}</dd></div>
        <div><dt>撤销时间</dt><dd>{evidence.revokedAt ? <time dateTime={evidence.revokedAt}>{evidence.revokedAt}</time> : "无"}</dd></div>
        <div><dt>记录时间</dt><dd><time dateTime={evidence.recordedAt}>{evidence.recordedAt}</time></dd></div>
      </dl>
    </li>
  );
}

function Blocker({ blocker, discloseOwner }: { blocker: IntegrationBlocker; discloseOwner: boolean }) {
  return (
    <li data-blocker-id={blocker.blockerId}>
      <strong>{blocker.code}</strong>
      <dl>
        <div><dt>严重度 / 状态</dt><dd>{blocker.severity} / {blocker.status}</dd></div>
        <div><dt>阶段门</dt><dd><code>{blocker.gate}</code></dd></div>
        <div><dt>原因引用</dt><dd><Refs values={blocker.reasonRefs} /></dd></div>
        <div><dt>Evidence 引用</dt><dd><Refs values={blocker.evidenceRefs} /></dd></div>
        {discloseOwner && <div><dt>负责人</dt><dd>{blocker.owner ?? "未分配"}</dd></div>}
        <div><dt>首次观测</dt><dd><time dateTime={blocker.firstObservedAt}>{blocker.firstObservedAt}</time></dd></div>
        <div><dt>更新时间</dt><dd><time dateTime={blocker.updatedAt}>{blocker.updatedAt}</time></dd></div>
      </dl>
    </li>
  );
}

function DetailFacts({ detail }: { detail: IntegrationCaseDetailResponse }) {
  const current = detail.scope === "current";
  return (
    <div data-case-id={detail.caseId} data-case-scope={detail.scope}>
      <dl>
        <div><dt>案例</dt><dd>{businessCaseName(detail.displayName)}</dd></div>
        <div><dt>作用域</dt><dd>{current ? "当前租户" : "脱敏参考"}</dd></div>
        <div><dt>当前阶段</dt><dd>{STAGE_LABELS[detail.computedStage]}</dd></div>
        <div><dt>证据快照</dt><dd>{detail.snapshotRevision === null ? "尚无" : `第 ${detail.snapshotRevision} 版`}</dd></div>
      </dl>

      {current ? (
        <details aria-label="审计详情">
          <summary>查看审计详情</summary>
          <dl>
            <div><dt>案例标识</dt><dd><code>{detail.caseId}</code></dd></div>
            <div><dt>负责人</dt><dd>{detail.owner}</dd></div>
            <div><dt>安装标识</dt><dd><code>{detail.installationId}</code> · 第 {detail.installationRevision} 版</dd></div>
            <div><dt>覆盖配置版本</dt><dd><code>{detail.overlayRevision}</code></dd></div>
            <div><dt>组合标识</dt><dd><code>{detail.compositionId}</code></dd></div>
            <div><dt>锁定版本</dt><dd>{detail.lockRevision}</dd></div>
            <div><dt>锁定摘要</dt><dd><code>{detail.lockHash}</code>（服务端只读）</dd></div>
            <div><dt>数据截止时间</dt><dd>{detail.cutoffAt ? <time dateTime={detail.cutoffAt}>{detail.cutoffAt}</time> : "无"}</dd></div>
            <div><dt>下次计算时间</dt><dd>{detail.nextProjectionAt ? <time dateTime={detail.nextProjectionAt}>{detail.nextProjectionAt}</time> : "无"}</dd></div>
          </dl>
        </details>
      ) : (
        <p role="note">此案例是独立脱敏参考副本；不披露当前租户 Owner、Installation、Overlay、Composition、Lock 或统计。</p>
      )}

      <section aria-label="案例核验摘要">
        <h4>核验摘要</h4>
        <p>已满足阶段 {detail.stageGates.filter((gate) => gate.status === "satisfied").length} / {detail.stageGates.length}；待处理事项 {detail.blockers.length} 项。</p>
      </section>

      <details aria-label="阶段门与证据审计详情">
        <summary>查看阶段门、待处理事项与证据审计详情</summary>
        <section aria-label="八阶段门">
          <h4>八个阶段门</h4>
          <p>按响应原样展示；页面不据此重算或推断阶段。</p>
          <ol>{detail.stageGates.map((gate) => <StageGate key={gate.stage} gate={gate} />)}</ol>
        </section>

        <section aria-label="阻塞项">
          <h4>待处理事项</h4>
          {detail.blockers.length === 0
            ? <p>服务端未返回待处理事项。</p>
            : <ul>{detail.blockers.map((blocker) => <Blocker key={blocker.blockerId} blocker={blocker} discloseOwner={current} />)}</ul>}
        </section>

        <section aria-label="Evidence 元数据">
          <h4>受限证据元数据</h4>
          <p>仅展示服务端响应中的审计元数据，不展示原文、内部执行人、密钥、个人信息或事故正文。</p>
          {detail.latestEvidence.length === 0
            ? <p>服务端未返回证据元数据。</p>
            : <ul>{detail.latestEvidence.map((evidence) => <Evidence key={`${evidence.evidenceId}:${evidence.revision}`} evidence={evidence} />)}</ul>}
        </section>
      </details>
    </div>
  );
}

export function IntegrationCaseDetail({ state, onRetry, onCreateSnapshot, snapshotPending, snapshotError }: IntegrationCaseDetailProps) {
  const showData = state.data !== null && ["ready", "stale", "refreshing"].includes(state.status);
  const canSnapshot = onCreateSnapshot && state.data?.scope === "current" && showData;
  return (
    <section aria-label="接入案例详情" style={panelStyle}>
      <header>
        <h3 style={{ margin: 0 }}>接入案例详情</h3>
        <p>只读展示服务端事实；页面不自行计算阶段。</p>
      </header>

      {state.status === "idle" && <p role="status">请选择一个接入案例。</p>}
      {state.status === "loading" && <p role="status">正在读取接入案例详情…</p>}
      {state.status === "empty" && <div role="status"><p>服务端未返回接入案例详情。</p><Retry onRetry={onRetry} /></div>}
      <Failure state={state} onRetry={onRetry} />
      {state.status === "stale" && <div role="status">当前详情是最后一次成功读取的服务端事实，刷新失败。<Retry onRetry={onRetry} /></div>}
      {state.status === "refreshing" && <p role="status">正在刷新接入案例详情；以下为最后一次服务端事实。</p>}
      {showData && state.data && <DetailFacts detail={state.data} />}
      {canSnapshot && (
        <section aria-label="证据快照操作" style={{ marginTop: 12, borderTop: "1px solid var(--aos-border)", paddingTop: 12 }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={snapshotPending}
            onClick={onCreateSnapshot}
          >
            {snapshotPending ? "正在生成快照…" : "生成证据快照"}
          </button>
          {snapshotError && <p role="alert" style={{ color: "var(--aos-danger)" }}>{snapshotError}</p>}
          <p style={{ color: "var(--aos-muted)", fontSize: "0.75rem", marginTop: 4 }}>
            触发服务端重新计算阶段，并保留新的阶段事件。
          </p>
        </section>
      )}
    </section>
  );
}
