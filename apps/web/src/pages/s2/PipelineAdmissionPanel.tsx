import { useSyncExternalStore } from "react";
import { Link } from "react-router-dom";

import { getAuthRevision, getTenant } from "../../api/tenant";
import { useJsonGet } from "./shared";

type Readiness = {
  pipelineId: string;
  formallyRegistered: boolean;
  sourceId: string | null;
  sourceConfigurationRevision: string | null;
  graphRevision: number | null;
  ready: false;
  blockers: string[];
  nextAction: string;
};

const copy: Record<string, string> = {
  PIPELINE_NOT_FORMALLY_REGISTERED: "这条管道尚未完成正式登记",
  PIPELINE_SOURCE_DRIFT: "管道来源已偏离登记回执，需核对",
  SOURCE_CONFIGURATION_CHANGED: "来源配置不存在或已变化，需重新核对",
  GRAPH_NOT_SAVED: "还没有保存正式管道图",
  EXACT_RUNTIME_REVALIDATION_REQUIRED: "还需核对安装、运行身份、映射、结构和遮蔽策略的精确引用",
};

function scopeIdentity() {
  const tenant = getTenant();
  return JSON.stringify([tenant.orgId, tenant.projectId, tenant.subject, getAuthRevision()]);
}

function subscribe(listener: () => void) {
  window.addEventListener("aos-tenant-updated", listener);
  window.addEventListener("aos-auth-updated", listener);
  return () => {
    window.removeEventListener("aos-tenant-updated", listener);
    window.removeEventListener("aos-auth-updated", listener);
  };
}

export function PipelineAdmissionPanel({ pipelineId }: { pipelineId: string }) {
  const scope = useSyncExternalStore(subscribe, scopeIdentity, scopeIdentity);
  return <Details key={`${scope}:${pipelineId}`} pipelineId={pipelineId} />;
}

function Details({ pipelineId }: { pipelineId: string }) {
  const path = pipelineId ? `/v1/pipelines/${encodeURIComponent(pipelineId)}/source-selection-readiness` : null;
  const { data, err, loading, reload } = useJsonGet<Readiness>(path, { authoritative: true });
  const verified = !loading && !err && data?.pipelineId === pipelineId && data?.ready === false &&
    Array.isArray(data.blockers) && data.blockers.length > 0;
  return <section aria-label="来源选择准入" style={{ border: "1px solid var(--aos-border)", padding: 12, margin: "8px 0" }}>
    <h3>来源选择准入</h3>
    <p>此处只核对当前条件；不会批准来源选择、读取源数据或运行管道。</p>
    <button type="button" disabled={loading || !path} onClick={reload}>刷新当前条件</button>
    {(loading || err || !verified) && <p role="status">{loading ? "正在核对…" : "当前条件未核清，不能提交审批。"}</p>}
    {verified && <>
      <p role="status">当前仍不可审批：</p>
      <ul>{data.blockers.map(item => <li key={item}>{copy[item] || "存在尚未核清的准入条件"}</li>)}</ul>
      {data.nextAction === "REGISTER_PIPELINE" && <Link to="/data/pipelines">返回管道登记</Link>}
      {data.nextAction === "REGISTER_SOURCE" && <Link to="/data">核对数据源</Link>}
      {data.nextAction === "SAVE_GRAPH" && <p>请先保存当前画布，再刷新条件。</p>}
      {data.nextAction === "REVALIDATE_RUNTIME" && <p>待运行配置和精确引用经正式 Owner 复核；此页不会代替审批。</p>}
    </>}
  </section>;
}
