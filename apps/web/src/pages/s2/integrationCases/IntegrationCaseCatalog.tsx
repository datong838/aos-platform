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
  return revision === null ? "—" : `r${revision}`;
}

function ScopeDisclosure({ item }: { item: IntegrationCaseListItem }) {
  if (item.scope === "reference") {
    return (
      <div data-testid={`reference-disclosure-${item.caseId}`}>
        <BpBadge variant="purple" size="sm">脱敏参考</BpBadge>
      </div>
    );
  }

  return (
    <dl style={{ display: "grid", gridTemplateColumns: "max-content 1fr", gap: "4px 10px", margin: 0 }}>
      <dt className="muted">Owner</dt>
      <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{item.owner}</dd>
      <dt className="muted">Installation</dt>
      <dd className="mono" style={{ margin: 0, overflowWrap: "anywhere" }}>{item.installationId}</dd>
      <dt className="muted">Overlay</dt>
      <dd className="mono" style={{ margin: 0, overflowWrap: "anywhere" }}>{item.overlayRevision}</dd>
    </dl>
  );
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
              aria-label={`查看案例：${item.displayName}`}
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
                  <div style={{ fontWeight: 600, overflowWrap: "anywhere" }}>{item.displayName}</div>
                  <div className="muted mono" style={{ fontSize: "0.7rem", marginTop: 3 }}>{item.caseId}</div>
                </div>
                <BpBadge variant="info" size="sm">{STAGE_LABELS[item.computedStage]}</BpBadge>
              </div>

              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", margin: "12px 0" }}>
                <span>Snapshot {snapshotLabel(item.snapshotRevision)}</span>
                <span>阻塞 {item.blockerCount}</span>
                <span>ETag {item.etagVersion}</span>
              </div>

              <ScopeDisclosure item={item} />

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
