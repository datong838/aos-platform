import { useEffect, useState } from "react";

import type { InstallationResponse } from "../../../api/assetControl/types";
import {
  INSTALLATION_ACTION_LABELS,
  type InstallationAction,
  type InstallationActionCommand,
  validateInstallationReason,
} from "./installationActions";

export interface InstallationActionDialogProps {
  action: InstallationAction | null;
  installation: InstallationResponse;
  pending: boolean;
  onCancel: () => void;
  onConfirm: (command: InstallationActionCommand) => void;
}

const HASH_FIELDS = [
  ["Lock hash", "lockHash"],
  ["Permission diff hash", "permissionDiffHash"],
  ["Migration plan hash", "migrationPlanHash"],
  ["Contribution diff hash", "contributionDiffHash"],
] as const;

function ActionExplanation({
  action,
  installation,
}: {
  action: InstallationAction;
  installation: InstallationResponse;
}) {
  if (action === "apply") {
    return <p>服务端执行 dry apply，并在成功响应的事件中生成 <code>dry_apply</code> evidence。</p>;
  }
  if (action === "verify") {
    return <p>服务端验证后生成 <code>verification</code> evidence，并将 active pointer 指向新的当前 revision。</p>;
  }
  if (action === "rollback") {
    return (
      <div>
        <p>服务端生成 <code>rollback</code> evidence，并把 active pointer 恢复到 previous active revision；previous 为空时会清空 active pointer。</p>
        <dl>
          <div><dt>Active revision</dt><dd>{installation.activeRevision ?? "无"}</dd></div>
          <div><dt>Previous active revision</dt><dd>{installation.previousActiveRevision ?? "无"}</dd></div>
        </dl>
      </div>
    );
  }
  if (action === "uninstall") {
    return (
      <div>
        <p>服务端卸载当前 active revision 的资源并清空 active pointer，安装状态将转为 <code>uninstalled</code> 终态。</p>
        <dl>
          <div><dt>Active revision</dt><dd>{installation.activeRevision ?? "无"}</dd></div>
        </dl>
      </div>
    );
  }
  if (action === "submit") return <p>只提交当前 draft，不会自动批准或安装。</p>;
  if (action === "reject") return <p>拒绝将形成服务端 decision 和事件记录。</p>;
  return <p>批准仅确认当前服务端 revision 的四个 hash，不接受浏览器修改。</p>;
}

export function InstallationActionDialog({
  action,
  installation,
  pending,
  onCancel,
  onConfirm,
}: InstallationActionDialogProps) {
  const [reason, setReason] = useState("");
  const [hashesConfirmed, setHashesConfirmed] = useState(false);

  useEffect(() => {
    setReason("");
    setHashesConfirmed(false);
  }, [action, installation.installationId, installation.currentRevision]);

  if (!action) return null;
  const activeAction = action;

  const needsReason = activeAction === "reject" || activeAction === "rollback" || activeAction === "uninstall";
  const reasonValidation = needsReason ? validateInstallationReason(reason) : null;
  const canConfirm = !pending &&
    (activeAction !== "approve" || hashesConfirmed) &&
    (!needsReason || reasonValidation?.ok === true);

  function confirm() {
    if (!canConfirm) return;
    if (activeAction === "reject" || activeAction === "rollback" || activeAction === "uninstall") {
      const result = validateInstallationReason(reason);
      if (!result.ok) return;
      onConfirm({ action: activeAction, reason: result.reason });
      return;
    }
    onConfirm({ action: activeAction });
  }

  return (
    <section role="dialog" aria-modal="true" aria-label={`${INSTALLATION_ACTION_LABELS[action]}确认`}>
      <h4>{INSTALLATION_ACTION_LABELS[action]}确认</h4>
      <p>Installation：<code>{installation.installationId}</code> · revision {installation.currentRevision}</p>
      <ActionExplanation action={action} installation={installation} />

      {action === "approve" && (
        <div>
          <dl aria-label="批准 hash 只读确认">
            {HASH_FIELDS.map(([label, field]) => (
              <div key={field}><dt>{label}</dt><dd><code>{installation.current[field]}</code></dd></div>
            ))}
          </dl>
          <label>
            <input
              type="checkbox"
              checked={hashesConfirmed}
              disabled={pending}
              onChange={(event) => setHashesConfirmed(event.target.checked)}
            />
            我确认批准以上当前服务端 revision 的四个 hash
          </label>
        </div>
      )}

      {needsReason && (
        <label>
          原因
          <textarea
            aria-label={`${INSTALLATION_ACTION_LABELS[action]}原因`}
            value={reason}
            maxLength={2001}
            disabled={pending}
            onChange={(event) => setReason(event.target.value)}
          />
          {reason && reasonValidation && !reasonValidation.ok && <span role="alert">{reasonValidation.error}</span>}
        </label>
      )}

      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" className="btn" disabled={pending} onClick={onCancel}>取消</button>
        <button type="button" className="btn btn-primary" disabled={!canConfirm} onClick={confirm}>
          {pending ? "正在等待服务端…" : `确认${INSTALLATION_ACTION_LABELS[action]}`}
        </button>
      </div>
    </section>
  );
}
