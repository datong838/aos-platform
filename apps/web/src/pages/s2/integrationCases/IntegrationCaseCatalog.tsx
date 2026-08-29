import type {
  IntegrationCaseListItem,
  IntegrationCaseScope,
  IntegrationCaseStage,
} from "../../../api/integrationCases/types";
import { BpBadge, BpEmpty } from "../../../components/bp";

export interface IntegrationCaseCatalogProps {
  scope: IntegrationCaseScope;
  items: readonly IntegrationCaseListItem[];
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
}
const STAGE_LABELS: Record<IntegrationCaseStage, string> = {
  planned: "已规划",
  connection_verified: "连接已验证",
  data_verified: "数据已验证",
  ontology_verified: "本体已验证",
  logic_verified: "逻辑已验证",
  workshop_verified: "Workshop 已验证",
  production_ready: "生产就绪",
  production_active: "生产运行",
};

const DATE_FORMAT = new Intl.DateTimeFormat("zh-CN", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Asia/Shanghai",
});

function dateTime(value: string): string {
  return DATE_FORMAT.format(new Date(value));
}

function snapshotLabel(revision: number | null): string {
  return revision === null ? "尚无" : `第 ${revision} 版`;
}

export function businessCaseName(value: string): string {
  const match = value.match(/^(.*?)\s*[（(]([^）)]*[DWL]\d+[^）)]*)[）)]\s*$/i);
  if (!match) return value.trim() || "未命名接入案例";
  const detail = match[2]
    .replace(/[DWL]\d+\s*[：:]?/gi, "")
    .replace(/decision_tag/gi, "决策标签")
    .replace(/\b(?:overlay|installation|composition)\b/gi, "配置")
    .replace(/注入/g, "配置")
    .replace(/\s*\+\s*/g, "与")
    .replace(/\s+/g, "")
    .replace(/^[：:\s]+|[：:\s]+$/g, "")
    .trim();
  const base = match[1].trim();
  return detail ? `${base}（${detail}）` : base || "未命名接入案例";
}

export function IntegrationCaseCatalog({
  scope,
  items,
  selectedCaseId,
  onSelectCase,
}: IntegrationCaseCatalogProps) {
  if (items.some((item) => item.scope !== scope)) {
    return (
      <div className="bp-banner bp-banner-warn" role="alert" data-testid="integration-case-scope-mismatch">
        案例数据作用域不一致，已停止展示
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <BpEmpty
        title={scope === "current" ? "暂无当前接入案例" : "暂无脱敏参考案例"}
        description="当前筛选条件下没有服务端返回的案例"
      />
    );
  }

  return (
    <section aria-label={scope === "current" ? "当前接入案例目录" : "参考接入案例目录"}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: "0.75rem",
        }}
      >
        {items.map((item) => {
          const selected = selectedCaseId === item.caseId;
          return (
            <button
              key={item.caseId}
              type="button"
              className="bp-card bp-card-outlined bp-card-pad-md bp-card-hover bp-card-clickable"
              aria-pressed={selected}
              aria-label={`查看案例：${businessCaseName(item.displayName)}`}
              data-case-id={item.caseId}
              onClick={() => onSelectCase(item.caseId)}
              style={{
                width: "100%",
                textAlign: "left",
                color: "inherit",
                font: "inherit",
                borderColor: selected ? "var(--aos-accent)" : undefined,
                background: selected ? "var(--aos-accent-light)" : undefined,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "flex-start" }}>
                <div>
                  <div style={{ fontWeight: 600, overflowWrap: "anywhere" }}>{businessCaseName(item.displayName)}</div>
                </div>
                <BpBadge variant="info" size="sm">{STAGE_LABELS[item.computedStage]}</BpBadge>
              </div>

              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", margin: "12px 0" }}>
                <span>证据快照 {snapshotLabel(item.snapshotRevision)}</span>
                <span>待处理 {item.blockerCount}</span>
              </div>

              <div className="muted" style={{ fontSize: "0.72rem", marginTop: 12 }}>
                更新于 {dateTime(item.updatedAt)}
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
