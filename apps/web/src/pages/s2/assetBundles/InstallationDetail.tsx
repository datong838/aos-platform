import type {
  InstallationEvent,
  InstallationResponse,
} from "../../../api/assetControl/types";
import type { AssetReadState } from "./model";

export interface InstallationDetailProps {
  state: AssetReadState<InstallationResponse>;
}

const panelStyle = {
  border: "1px solid var(--aos-border)",
  borderRadius: 3,
  padding: 12,
} as const;

function Retry({ reload }: { reload: () => void }) {
  return <button type="button" className="btn" onClick={reload}>重试读取</button>;
}

function EventEvidence({ event }: { event: InstallationEvent }) {
  if (!event.evidence) return <span>无服务端 evidence</span>;
  return (
    <dl>
      <div><dt>Evidence 类型</dt><dd>{event.evidence.type}</dd></div>
      <div><dt>状态</dt><dd>{event.evidence.status}</dd></div>
      <div><dt>引用</dt><dd><code>{event.evidence.evidenceRef}</code></dd></div>
      <div><dt>Hash</dt><dd><code>{event.evidence.evidenceHash}</code></dd></div>
      <div><dt>观测时间</dt><dd><time dateTime={event.evidence.observedAt}>{event.evidence.observedAt}</time></dd></div>
    </dl>
  );
}

export function InstallationDetail({ state }: InstallationDetailProps) {
  const installation = state.data;
  const mayShowData = state.status === "ready" || (state.status === "error" && state.stale);

  return (
    <section aria-label="安装详情" style={panelStyle}>
      <header>
        <h3 style={{ margin: 0 }}>安装详情与事件时间线</h3>
        <p style={{ color: "var(--aos-muted)", fontSize: "0.75rem" }}>
          这里只展示当前 revision、当前 decision 与完整事件时间线；事件不等同于每个历史 revision 的完整快照。
        </p>
      </header>

      {state.status === "idle" && <p role="status">请选择一条安装记录。</p>}
      {state.status === "loading" && <p role="status">正在读取安装详情…</p>}
      {state.status === "empty" && <div role="status"><p>服务端未返回安装详情。</p><Retry reload={state.reload} /></div>}
      {state.status === "forbidden" && <div role="alert"><strong>无权查看安装详情</strong><p>请申请资产安装读取权限。</p><Retry reload={state.reload} /></div>}
      {state.status === "not_visible_or_missing" && <div role="alert"><strong>安装不可见或不存在</strong><p>为避免泄漏，不区分不存在与标记不可见。</p><Retry reload={state.reload} /></div>}
      {state.status === "error" && <div role="alert"><strong>安装详情读取失败</strong><p>{state.error?.message ?? "未知错误"}</p><Retry reload={state.reload} /></div>}
      {state.stale && mayShowData && <div role="status">当前详情是旧数据，刷新失败。<Retry reload={state.reload} /></div>}
      {state.refreshing && <p role="status">正在刷新安装详情…</p>}

      {installation && mayShowData && (
        <div data-installation-id={installation.installationId}>
          <dl>
            <div><dt>名称</dt><dd>{installation.displayName}</dd></div>
            <div><dt>Installation ID</dt><dd><code>{installation.installationId}</code></dd></div>
            <div><dt>状态</dt><dd>{installation.state}</dd></div>
            <div><dt>当前 revision / ETag version</dt><dd>{installation.currentRevision} / {installation.etagVersion}</dd></div>
            <div><dt>Active revision</dt><dd>{installation.activeRevision ?? "无"}</dd></div>
            <div><dt>Previous active revision</dt><dd>{installation.previousActiveRevision ?? "无"}</dd></div>
          </dl>

          <section aria-label="当前 revision">
            <h4>当前 revision</h4>
            <dl>
              <div><dt>Composition</dt><dd><code>{installation.current.compositionId}</code> · lock revision {installation.current.lockRevision}</dd></div>
              <div><dt>Overlay revision</dt><dd><code>{installation.current.overlayRevision}</code></dd></div>
              <div><dt>Requested by</dt><dd>{installation.current.requestedBy}</dd></div>
              <div><dt>Lock hash</dt><dd><code>{installation.current.lockHash}</code></dd></div>
              <div><dt>Permission diff hash</dt><dd><code>{installation.current.permissionDiffHash}</code></dd></div>
              <div><dt>Migration plan hash</dt><dd><code>{installation.current.migrationPlanHash}</code></dd></div>
              <div><dt>Contribution diff hash</dt><dd><code>{installation.current.contributionDiffHash}</code></dd></div>
            </dl>
          </section>

          <section aria-label="当前审批结论">
            <h4>当前 decision</h4>
            {installation.decision ? (
              <dl>
                <div><dt>结论</dt><dd>{installation.decision.decision}</dd></div>
                <div><dt>审批人</dt><dd>{installation.decision.actor}</dd></div>
                <div><dt>Submitted revision</dt><dd>{installation.decision.submittedRevision}</dd></div>
                <div><dt>原因</dt><dd>{installation.decision.reason ?? "无"}</dd></div>
                <div><dt>Decision ID</dt><dd><code>{installation.decision.decisionId}</code></dd></div>
              </dl>
            ) : <p>当前 revision 没有关联 decision。</p>}
          </section>

          <section aria-label="安装事件时间线">
            <h4>事件时间线</h4>
            <p>共 {installation.events.length} 个服务端事件；不提供历史 revision 完整快照。</p>
            <ol>
              {installation.events.map((event) => (
                <li key={event.sequence} data-event-sequence={event.sequence}>
                  <strong>#{event.sequence} · {event.fromState ?? "初始"} → {event.toState}</strong>
                  <p>revision {event.fromRevision ?? "—"} → {event.toRevision} · actor {event.actor}</p>
                  <p>原因：{event.reason ?? "无"}</p>
                  <EventEvidence event={event} />
                  <time dateTime={event.createdAt}>{event.createdAt}</time>
                </li>
              ))}
            </ol>
          </section>
        </div>
      )}
    </section>
  );
}
