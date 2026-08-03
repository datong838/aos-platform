import type {
  IntegrationCaseScope,
  IntegrationCaseStats as IntegrationCaseStatsValue,
  IntegrationMetric,
} from "../../../api/integrationCases/types";
import { BpMetricGrid } from "../blueprintUi";

export interface IntegrationCaseStatsProps {
  scope: IntegrationCaseScope;
  stats: IntegrationCaseStatsValue | null;
}

type MetricSpec = {
  key: keyof IntegrationCaseStatsValue;
  code: string;
  label: string;
  suffix?: string;
};

const METRICS: readonly MetricSpec[] = [
  { key: "caseCount", code: "CASE", label: "当前案例" },
  { key: "productionActiveCount", code: "ACTIVE", label: "生产运行" },
  { key: "connectorCount", code: "CONN", label: "连接器" },
  { key: "pipelineCount", code: "PIPE", label: "Pipeline" },
  { key: "datasetRowCount", code: "ROWS", label: "数据集行数" },
  { key: "latencyMs", code: "LAT", label: "最大延迟", suffix: " ms" },
];

const NUMBER_FORMAT = new Intl.NumberFormat("zh-CN", {
  maximumFractionDigits: 2,
});

function metricValue(metric: IntegrationMetric, suffix = ""): string {
  if (metric.value === null) return "—";
  return `${NUMBER_FORMAT.format(metric.value)}${suffix}`;
}

function metricHint(metric: IntegrationMetric): string {
  return `已测量 ${NUMBER_FORMAT.format(metric.measuredCaseCount)} / 可计量 ${NUMBER_FORMAT.format(metric.eligibleCaseCount)}`;
}

export function IntegrationCaseStats({ scope, stats }: IntegrationCaseStatsProps) {
  if (scope === "reference") {
    if (stats !== null) {
      return (
        <div className="bp-banner bp-banner-warn" role="alert" data-testid="integration-case-stats-scope-mismatch">
          参考案例统计响应不符合披露契约
        </div>
      );
    }
    return (
      <div className="bp-banner bp-banner-info" role="status" data-testid="integration-case-reference-stats">
        脱敏参考案例不提供当前工作区统计
      </div>
    );
  }

  if (stats === null) {
    return (
      <div className="bp-banner bp-banner-warn" role="status" data-testid="integration-case-stats-unavailable">
        当前案例统计暂不可用
      </div>
    );
  }

  return (
    <section aria-label="接入案例统计" data-testid="integration-case-stats">
      <BpMetricGrid
        items={METRICS.map(({ key, code, label, suffix }) => {
          const metric = stats[key];
          return {
            code,
            label,
            value: metricValue(metric, suffix),
            hint: metricHint(metric),
            tone: metric.value === null ? "muted" as const : "ok" as const,
          };
        })}
      />
    </section>
  );
}
