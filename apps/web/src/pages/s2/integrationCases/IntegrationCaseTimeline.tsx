import type { IntegrationCaseTimelineResponse } from "../../../api/integrationCases/types";
import type { IntegrationCaseReadViewState } from "./IntegrationCaseDetail";

export interface IntegrationCaseTimelineProps {
  state: IntegrationCaseReadViewState<IntegrationCaseTimelineResponse>;
  onRetry?: () => void;
}

const panelStyle = {
  border: "1px solid var(--aos-border)",
  borderRadius: 3,
  padding: 12,
} as const;

function Retry({ onRetry }: { onRetry?: () => void }) {
  if (!onRetry) return null;
  return <button type="button" className="btn" onClick={onRetry}>重试读取</button>;
}

function TimelineFailure({ state, onRetry }: IntegrationCaseTimelineProps) {
  if (state.status === "forbidden") {
    return <div role="alert"><strong>无权查看阶段事件</strong><p>请申请接入案例读取权限。</p><Retry onRetry={onRetry} /></div>;
  }
  if (state.status === "not_visible_or_missing") {
    return <div role="alert"><strong>阶段事件不可见或不存在</strong><p>为避免泄漏，不区分不存在与不可见。</p><Retry onRetry={onRetry} /></div>;
  }
  if (state.status === "error") {
    return (
      <div role="alert">
        <strong>阶段事件读取失败</strong>
        <p>{state.error?.message ?? "未知读取错误"}</p>
        {state.error?.code && <p>错误代码：<code>{state.error.code}</code></p>}
        <Retry onRetry={onRetry} />
      </div>
    );
  }
  return null;
}

function TimelineFacts({ timeline }: { timeline: IntegrationCaseTimelineResponse }) {
  return (
    <div data-timeline-case-id={timeline.caseId} data-case-scope={timeline.scope}>
      <p>Case <code>{timeline.caseId}</code> · {timeline.scope === "current" ? "当前租户" : "脱敏参考"}</p>
      <p>共 {timeline.total} 个服务端 Stage Event；当前页 {timeline.items.length} 个。</p>
      {timeline.items.length === 0 ? (
        <p role="status">服务端尚未返回 Stage Event。</p>
      ) : (
        <ol>
          {timeline.items.map((event) => (
            <li key={event.sequence} data-event-sequence={event.sequence}>
              <strong>#{event.sequence} · <code>{event.oldStage ?? "无前序阶段"}</code> → <code>{event.newStage}</code></strong>
              <dl>
                <div><dt>Snapshot revision</dt><dd>{event.snapshotRevision}</dd></div>
                <div><dt>Cause</dt><dd><code>{event.cause}</code></dd></div>
                <div><dt>原因引用</dt><dd>{event.reasonRefs.length === 0 ? "无" : <ul>{event.reasonRefs.map((ref) => <li key={ref}><code>{ref}</code></li>)}</ul>}</dd></div>
                <div><dt>创建时间</dt><dd><time dateTime={event.createdAt}>{event.createdAt}</time></dd></div>
              </dl>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export function IntegrationCaseTimeline({ state, onRetry }: IntegrationCaseTimelineProps) {
  const showData = state.data !== null && ["ready", "stale", "refreshing"].includes(state.status);
  return (
    <section aria-label="阶段事件时间线" style={panelStyle}>
      <header>
        <h3 style={{ margin: 0 }}>Stage Event 时间线</h3>
        <p>只读展示服务端事件；事件序列不用于推断未返回的阶段或 Evidence。</p>
      </header>

      {state.status === "idle" && <p role="status">请选择一个接入案例以读取阶段事件。</p>}
      {state.status === "loading" && <p role="status">正在读取阶段事件…</p>}
      {state.status === "empty" && <div role="status"><p>服务端未返回阶段事件时间线。</p><Retry onRetry={onRetry} /></div>}
      <TimelineFailure state={state} onRetry={onRetry} />
      {state.status === "stale" && <div role="status">当前时间线是最后一次成功读取的服务端事实，刷新失败。<Retry onRetry={onRetry} /></div>}
      {state.status === "refreshing" && <p role="status">正在刷新阶段事件；以下为最后一次服务端事实。</p>}
      {showData && state.data && <TimelineFacts timeline={state.data} />}
    </section>
  );
}
