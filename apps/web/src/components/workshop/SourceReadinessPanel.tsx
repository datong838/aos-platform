import { useCallback, useEffect, useRef, useState } from "react";

import {
  EcommerceWorkshopClientError,
  ecommerceWorkshopClient,
  type SourceReadinessEnvelope,
} from "../../api/ecommerceWorkshop";
import { getTenant } from "../../api/tenant";
import { AsyncStateBoundary } from "./AsyncStateBoundary";

type Client = Pick<typeof ecommerceWorkshopClient, "getSourceReadiness">;
type Phase = "loading" | "ready" | "forbidden" | "failed";

function tenantKey(): string {
  const tenant = getTenant();
  return `${tenant.orgId}:${tenant.projectId}`;
}

function asError(cause: unknown): EcommerceWorkshopClientError {
  if (cause instanceof EcommerceWorkshopClientError) return cause;
  const message = cause instanceof Error ? cause.message : String(cause);
  return new EcommerceWorkshopClientError(message, {
    status: 0,
    operationId: "ecommerceWorkshopSourceReadinessGet",
    body: { code: "SOURCE_READINESS_READ_FAILED", message, details: null, traceId: "" },
  });
}

function count(value: number | null): string {
  return value === null ? "未知" : String(value);
}

export function SourceReadinessPanel({ client = ecommerceWorkshopClient }: { client?: Client }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [response, setResponse] = useState<SourceReadinessEnvelope | null>(null);
  const revision = useRef(0);

  const load = useCallback(() => {
    const requestId = ++revision.current;
    const expectedTenant = tenantKey();
    setPhase("loading");
    void client.getSourceReadiness().then(
      (next) => {
        if (requestId !== revision.current) return;
        if (`${next.tenant.orgId}:${next.tenant.projectId}` !== expectedTenant || tenantKey() !== expectedTenant) {
          setResponse(null);
          setPhase("failed");
          return;
        }
        setResponse(next);
        setPhase("ready");
      },
      (cause: unknown) => {
        if (requestId !== revision.current) return;
        const error = asError(cause);
        setResponse(null);
        setPhase(error.status === 401 || error.status === 403 ? "forbidden" : "failed");
      },
    );
  }, [client]);

  useEffect(() => {
    load();
    return () => { revision.current += 1; };
  }, [load]);

  if (phase !== "ready" || response === null) {
    return (
      <section className="source-readiness-panel" aria-labelledby="source-readiness-title">
        <h2 id="source-readiness-title">数据源就绪度</h2>
        <AsyncStateBoundary
          state={phase}
          action={phase === "failed" ? <button type="button" onClick={load}>重新读取就绪度</button> : undefined}
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
