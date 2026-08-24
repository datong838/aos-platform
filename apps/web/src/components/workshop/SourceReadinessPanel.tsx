import { AsyncStateBoundary } from "./AsyncStateBoundary";
import {
  SourceReadinessProvider,
  type SourceReadinessClient,
  useSourceReadinessSnapshot,
} from "./SourceReadinessContext";

function count(value: number | null): string {
  return value === null ? "未知" : String(value);
}

function SourceReadinessPanelView() {
  const snapshot = useSourceReadinessSnapshot();
  const phase = snapshot?.phase ?? "failed";
  const response = snapshot?.response ?? null;
  if (phase !== "ready" || response === null) {
    return (
      <section className="source-readiness-panel" aria-labelledby="source-readiness-title">
        <h2 id="source-readiness-title">数据源就绪度</h2>
        <AsyncStateBoundary
          state={phase}
          action={phase === "failed" && snapshot ? <button type="button" onClick={snapshot.reload}>重新读取就绪度</button> : undefined}
        />
      </section>
    );
  }

  const blockers = [...new Set(response.sources.flatMap((source) => source.blockers))].sort();
  return (
    <section className="source-readiness-panel" aria-labelledby="source-readiness-title" data-testid="source-readiness-panel">
      <div className="source-readiness-heading">
        <div><p className="ecommerce-workshop-eyebrow">Canonical P01–P12</p><h2 id="source-readiness-title">数据源就绪度</h2></div>
        <span className={`source-readiness-status is-${response.status}`}>{response.status}</span>
      </div>
      <dl className="source-readiness-summary">
        <div><dt>源</dt><dd>{response.sources.length}</dd></div>
        <div><dt>阻断项</dt><dd>{blockers.length}</dd></div>
        <div><dt>检查时间</dt><dd>{response.checkedAt}</dd></div>
        <div><dt>一致 cutoff</dt><dd>{response.cutoffAt}</dd></div>
      </dl>
      {blockers.length > 0 ? <p className="source-readiness-blockers"><strong>当前不具备 operational GREEN：</strong>{blockers.join(" · ")}</p> : null}
      <div className="source-readiness-table-wrap">
        <table>
          <thead><tr><th scope="col">Pipeline</th><th scope="col">对象</th><th scope="col">状态</th><th scope="col">源 / 投影</th><th scope="col">原因</th></tr></thead>
          <tbody>{response.sources.map((source) => <tr key={source.pipelineId}><th scope="row">{source.pipelineId}</th><td>{source.objectType}</td><td><span className={`source-readiness-status is-${source.status}`}>{source.status}</span></td><td>{count(source.counts.sourceTotal)} / {count(source.counts.projectionTotal)}</td><td>{source.blockers.length > 0 ? source.blockers.join(" · ") : "无 blocker"}</td></tr>)}</tbody>
        </table>
      </div>
    </section>
  );
}

export function SourceReadinessPanel({ client }: { client?: SourceReadinessClient }) {
  return client ? <SourceReadinessProvider client={client}><SourceReadinessPanelView /></SourceReadinessProvider> : <SourceReadinessPanelView />;
}
