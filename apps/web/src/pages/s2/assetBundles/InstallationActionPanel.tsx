import type { InstallationResponse } from "../../../api/assetControl/types";
import { InstallationActionDialog } from "./InstallationActionDialog";
import {
  INSTALLATION_ACTION_LABELS,
  installationActionAvailability,
  type InstallationAction,
  type InstallationActionCommand,
} from "./installationActions";

export interface InstallationActionPanelProps {
  installation: InstallationResponse | null;
  ready: boolean;
  stale: boolean;
  refreshing: boolean;
  offline: boolean;
  subject?: string;
  roles?: readonly string[];
  selectedAction: InstallationAction | null;
  pendingAction: InstallationAction | null;
  onSelectedActionChange: (action: InstallationAction | null) => void;
  onConfirm: (command: InstallationActionCommand) => void;
}

const panelStyle = {
  border: "1px solid var(--aos-border)",
  borderRadius: 3,
  padding: 12,
} as const;

export function InstallationActionPanel({
  installation,
  ready,
  stale,
  refreshing,
  offline,
  subject,
  roles,
  selectedAction,
  pendingAction,
  onSelectedActionChange,
  onConfirm,
}: InstallationActionPanelProps) {
  if (!installation) {
    return <section aria-label="安装动作" style={panelStyle}><h3>安装动作</h3><p role="status">请选择并加载一条安装详情。</p></section>;
  }

  const actions = installationActionAvailability({
    state: installation.state,
    requestedBy: installation.current.requestedBy,
    subject,
    roles,
    ready,
    stale,
    refreshing,
    offline,
    pendingAction,
  });
  const latestEvidence = [...installation.events]
    .reverse()
    .find((event) => event.evidence)?.evidence ?? null;
  const selectedAvailability = actions.find((item) => item.action === selectedAction);
  const dialogAction = selectedAvailability &&
    (selectedAvailability.enabled || pendingAction === selectedAction)
    ? selectedAction
    : null;

  return (
    <section aria-label="安装动作" style={panelStyle}>
      <header>
        <h3 style={{ margin: 0 }}>安装动作</h3>
        <p>浏览器只控制入口和确认；状态、权限、maker-checker 与 evidence 均由服务端最终裁决。</p>
      </header>

      <dl aria-label="服务端安装指针">
        <div><dt>Current revision</dt><dd>{installation.currentRevision}</dd></div>
        <div><dt>Active revision</dt><dd>{installation.activeRevision ?? "无"}</dd></div>
        <div><dt>Previous active revision</dt><dd>{installation.previousActiveRevision ?? "无"}</dd></div>
      </dl>

      <div aria-label="最近服务端 evidence">
        <h4>最近服务端 evidence</h4>
        {latestEvidence ? (
          <dl>
            <div><dt>类型 / 状态</dt><dd>{latestEvidence.type} / {latestEvidence.status}</dd></div>
            <div><dt>引用</dt><dd><code>{latestEvidence.evidenceRef}</code></dd></div>
            <div><dt>Hash</dt><dd><code>{latestEvidence.evidenceHash}</code></dd></div>
          </dl>
        ) : <p>当前没有服务端 evidence。</p>}
      </div>

      {actions.length === 0 ? <p role="status">当前状态是终态，没有可执行动作。</p> : (
        <div style={{ display: "flex", gap: 8 }}>
          {actions.map(({ action, enabled, disabledReason }) => (
            <button
              key={action}
              type="button"
              className={action === "reject" || action === "rollback" ? "btn" : "btn btn-primary"}
              disabled={!enabled}
              title={disabledReason ?? INSTALLATION_ACTION_LABELS[action]}
              onClick={() => { if (enabled) onSelectedActionChange(action); }}
            >
              {INSTALLATION_ACTION_LABELS[action]}
            </button>
          ))}
        </div>
      )}
      {actions.map((item) => !item.enabled && item.disabledReason ? (
        <p role="status" key={`${item.action}-reason`}>{INSTALLATION_ACTION_LABELS[item.action]}：{item.disabledReason}</p>
      ) : null)}

      <InstallationActionDialog
        action={dialogAction}
        installation={installation}
        pending={pendingAction !== null}
        onCancel={() => onSelectedActionChange(null)}
        onConfirm={onConfirm}
      />
    </section>
  );
}
