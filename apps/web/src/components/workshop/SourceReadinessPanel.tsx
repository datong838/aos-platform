import { AsyncStateBoundary } from "./AsyncStateBoundary";
import {
  SourceReadinessProvider,
  type SourceReadinessClient,
  useSourceReadinessSnapshot,
} from "./SourceReadinessContext";
import type { SourceReadinessItem, SourceReadinessStatus } from "../../api/ecommerceWorkshop";

const PIPELINE_LABELS: Record<string, string> = {
  P01: "店铺",
  P02: "商品",
  P03: "商品规格",
  P04: "商品类目",
  P05: "订单",
  P06: "订单明细",
  P07: "发货履约",
  P08: "客户",
  P09: "小程序",
  P10: "系统配置",
  P11: "商品评价",
  P12: "支付",
};

const STATUS_LABELS: Record<SourceReadinessStatus, string> = {
  ready: "就绪",
  empty: "暂无数据",
  degraded: "部分可用",
  unknown: "待核对",
  stale: "数据已过期",
  failed: "运行失败",
  blocked: "等待条件",
  forbidden: "无访问权限",
};

const CONDITION_LABELS: Record<string, string> = {
  FRESHNESS_POLICY_REF_MISSING: "新鲜度规则待补齐",
  LATEST_RUN_NOT_SUCCEEDED: "最近一次计划读取未成功",
  MAPPING_EXACT_REF_MISSING: "字段映射权威待补齐",
  MASKING_POLICY_EXACT_REF_MISSING: "脱敏规则权威待补齐",
  PIPELINE_NOT_FOUND: "数据读取流程尚未配置",
  QUALITY_POLICY_REF_MISSING: "数据质量规则待补齐",
  QUERY_CAPABILITY_REF_MISSING: "查询能力待补齐",
  RECONCILIATION_POLICY_REF_MISSING: "对账规则待补齐",
  SCHEDULE_CRON_POLICY_MISMATCH: "读取计划与约定时段不一致",
  SCHEDULE_DISABLED: "计划读取尚未启用",
  SCHEDULE_INGEST_KIND_MISMATCH: "计划读取方式待核对",
  SCHEDULE_NOT_FOUND: "计划读取尚未配置",
  SCHEDULE_PIPELINE_REF_MISMATCH: "计划与数据流程绑定待核对",
  SCHEDULE_SOURCE_REF_MISMATCH: "计划与数据来源绑定待核对",
  SCHEMA_EXACT_REF_MISSING: "数据结构权威待补齐",
  SOURCE_CONFIG_EXACT_REF_MISSING: "源配置权威待补齐",
  SOURCE_DATA_STALE: "数据已超过新鲜度期限",
  SOURCE_EMPTY: "源系统当前没有可读取数据",
  SOURCE_NOT_FOUND: "数据来源尚未配置",
  SOURCE_QUALITY_FAILED: "数据质量检查未通过",
  SOURCE_READINESS_TENANT_SCOPE_MISMATCH: "数据所属工作区不一致",
  SOURCE_RECONCILIATION_FAILED: "数据对账未通过",
};

const ERROR_LABELS: Record<string, string> = {
  SSH_TUNNEL_NOT_READY: "数据连接尚未就绪",
  SSH_CONNECT_TIMEOUT: "数据连接超时",
  SSH_AUTHENTICATION_FAILED: "数据连接认证失败",
  SSH_CONNECTION_REFUSED: "数据连接被拒绝",
  SSH_HOST_RESOLUTION_FAILED: "数据地址解析失败",
  SSH_HOST_KEY_VERIFICATION_FAILED: "数据连接身份校验失败",
  SSH_LOCAL_FORWARD_BIND_FAILED: "本地数据通道建立失败",
  SSH_FORWARD_FAILED: "数据转发失败",
  SSH_PROCESS_FAILED: "数据连接进程异常",
  MYSQL_CONNECT_FAILED: "数据库连接失败",
  MYSQL_SERVER_GONE: "数据库连接已中断",
  MYSQL_CONNECTION_LOST: "数据读取期间连接中断",
  PIPELINE_EXECUTOR_FAILED: "数据读取运行失败",
  SCHEDULE_EXECUTOR_EXCEPTION: "计划读取运行失败",
};

const NEXT_ACTIONS: Record<SourceReadinessStatus, string> = {
  ready: "无需处理",
  empty: "确认源系统是否存在可读取业务数据",
  degraded: "补齐并核对所需数据治理条件",
  unknown: "补齐并核对所需数据治理条件",
  stale: "等待下一次计划读取更新数据",
  failed: "查看运行审计后等待下一次计划读取",
  blocked: "补齐并核对所需数据治理条件",
  forbidden: "联系管理员确认数据访问权限",
};

function count(value: number | null): string {
  return value === null ? "未知" : String(value);
}

function pipelineLabel(pipelineId: string): string {
  return PIPELINE_LABELS[pipelineId.slice(0, 3)] ?? "业务数据";
}

function conditionLabel(code: string): string {
  return CONDITION_LABELS[code] ?? "需要进一步核对数据条件";
}

function diagnosis(source: SourceReadinessItem): string {
  if (source.status === "failed" && source.latestRun.errorCode) {
    return ERROR_LABELS[source.latestRun.errorCode] ?? "数据读取未完成";
  }
  const labels = [...new Set(source.blockers.map(conditionLabel))];
  if (labels.length > 0) return labels.join("；");
  return ({
    ready: "当前没有待处理条件",
    empty: "源系统当前没有可读取数据",
    degraded: "部分数据条件尚未满足",
    unknown: "需要进一步核对数据条件",
    stale: "数据已超过新鲜度期限",
    failed: "数据读取未完成",
    blocked: "所需数据条件尚未满足",
    forbidden: "当前没有数据访问权限",
  } satisfies Record<SourceReadinessStatus, string>)[source.status];
}

function nextAction(source: SourceReadinessItem): string {
  if (source.status === "failed" && source.latestRun.errorCode && /^(SSH_|MYSQL_)/.test(source.latestRun.errorCode)) {
    return "检查数据连接后等待下一次计划读取";
  }
  return NEXT_ACTIONS[source.status];
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

  const pendingSources = response.sources.filter((source) => source.status !== "ready");
  return (
    <section className="source-readiness-panel" aria-labelledby="source-readiness-title" data-testid="source-readiness-panel">
      <div className="source-readiness-heading">
        <div><p className="ecommerce-workshop-eyebrow">正式数据源 · 12 项</p><h2 id="source-readiness-title">数据源就绪度</h2></div>
        <span className={`source-readiness-status is-${response.status}`}>{STATUS_LABELS[response.status]}</span>
      </div>
      <dl className="source-readiness-summary">
        <div><dt>数据对象</dt><dd>{response.sources.length}</dd></div>
        <div><dt>待处理对象</dt><dd>{pendingSources.length}</dd></div>
        <div><dt>检查时间</dt><dd>{response.checkedAt}</dd></div>
        <div><dt>数据截止</dt><dd>{response.cutoffAt}</dd></div>
      </dl>
      {pendingSources.length > 0 ? <p className="source-readiness-blockers"><strong>当前有 {pendingSources.length} 个数据对象待处理：</strong>未知、过期或失败的数据不会显示为可用。</p> : null}
      <div className="source-readiness-table-wrap">
        <table>
          <thead><tr><th scope="col">数据对象</th><th scope="col">状态</th><th scope="col">源数据 / 页面投影</th><th scope="col">当前原因</th><th scope="col">下一步</th></tr></thead>
          <tbody>{response.sources.map((source) => (
            <tr key={source.pipelineId}>
              <th scope="row"><strong>{pipelineLabel(source.pipelineId)}</strong></th>
              <td><span className={`source-readiness-status is-${source.status}`}>{STATUS_LABELS[source.status]}</span></td>
              <td>{count(source.counts.sourceTotal)} / {count(source.counts.projectionTotal)}</td>
              <td>{diagnosis(source)}</td>
              <td>
                <span>{nextAction(source)}</span>
                <details className="source-readiness-audit">
                  <summary>查看审计码</summary>
                  <dl>
                    <div><dt>数据流程</dt><dd><code>{source.pipelineId}</code></dd></div>
                    <div><dt>对象类型</dt><dd><code>{source.objectType}</code></dd></div>
                    {source.latestRun.errorCode ? <div><dt>运行结果</dt><dd><code>{source.latestRun.errorCode}</code></dd></div> : null}
                    {source.blockers.length > 0 ? <div><dt>条件码</dt><dd>{source.blockers.map((blocker) => <code key={blocker}>{blocker}</code>)}</dd></div> : null}
                  </dl>
                </details>
              </td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  );
}

export function SourceReadinessPanel({ client }: { client?: SourceReadinessClient }) {
  return client ? <SourceReadinessProvider client={client}><SourceReadinessPanelView /></SourceReadinessProvider> : <SourceReadinessPanelView />;
}
