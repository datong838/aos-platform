import type { InstallationState } from "../../../api/assetControl/types";

export type InstallationAction =
  | "submit"
  | "approve"
  | "reject"
  | "apply"
  | "verify"
  | "rollback";

export type InstallationActionCommand =
  | { action: "submit" | "approve" | "apply" | "verify" }
  | { action: "reject" | "rollback"; reason: string };

export interface InstallationActionContext {
  state: InstallationState;
  requestedBy: string;
  subject?: string;
  roles?: readonly string[];
  ready: boolean;
  stale: boolean;
  refreshing: boolean;
  offline: boolean;
  pendingAction: InstallationAction | null;
}

export interface InstallationActionAvailability {
  action: InstallationAction;
  enabled: boolean;
  disabledReason: string | null;
}

export type InstallationReasonValidation =
  | { ok: true; reason: string }
  | { ok: false; error: string };

export const INSTALLATION_ACTION_LABELS: Readonly<Record<InstallationAction, string>> = {
  submit: "提交审批",
  approve: "批准",
  reject: "拒绝",
  apply: "执行 Apply",
  verify: "验证并激活",
  rollback: "回滚",
};

const ACTIONS_BY_STATE: Readonly<Record<InstallationState, readonly InstallationAction[]>> = {
  draft: ["submit"],
  submitted: ["approve", "reject"],
  approved: ["apply"],
  rejected: [],
  applied: ["verify"],
  active: ["rollback"],
  rolled_back: [],
};

const ROLES_BY_ACTION: Readonly<Record<InstallationAction, ReadonlySet<string>>> = {
  submit: new Set(["admin", "developer", "asset-installer"]),
  approve: new Set(["admin", "asset-install-approver"]),
  reject: new Set(["admin", "asset-install-approver"]),
  apply: new Set(["admin", "asset-installer"]),
  verify: new Set(["admin", "asset-installer"]),
  rollback: new Set(["admin", "asset-installer"]),
};

const CONTROL_CHARACTER = /[\u0000-\u001f\u007f-\u009f]/u;
const MAX_REASON_LENGTH = 2000;

function normalizedIdentity(value: string | undefined): string | null {
  if (!value || value !== value.trim() || CONTROL_CHARACTER.test(value)) return null;
  return value;
}

function normalizedRoles(roles: readonly string[] | undefined): Set<string> {
  return new Set(
    (roles ?? [])
      .map((role) => role.trim())
      .filter((role) => Boolean(role) && !CONTROL_CHARACTER.test(role))
      .map((role) => role.toLowerCase()),
  );
}

function disabledReason(
  action: InstallationAction,
  context: InstallationActionContext,
): string | null {
  if (context.pendingAction) return "安装动作正在执行，请等待服务端返回";
  if (!context.ready) return "安装详情尚未就绪";
  if (context.stale) return "当前安装详情是旧数据，请先刷新";
  if (context.refreshing) return "安装详情正在刷新";
  if (context.offline) return "离线状态禁止安装写操作";

  const subject = normalizedIdentity(context.subject);
  if (!subject) return "当前登录身份尚未加载";
  const roles = normalizedRoles(context.roles);
  if (![...ROLES_BY_ACTION[action]].some((role) => roles.has(role))) {
    return "当前身份没有执行此动作的角色";
  }
  if (
    (action === "approve" || action === "reject") &&
    subject === context.requestedBy
  ) {
    return "提交人不能批准或拒绝自己提交的安装计划";
  }
  return null;
}

/** UI 早期门禁；服务端状态机、角色和 maker-checker 仍是最终裁决者。 */
export function installationActionAvailability(
  context: InstallationActionContext,
): InstallationActionAvailability[] {
  return ACTIONS_BY_STATE[context.state].map((action) => {
    const reason = disabledReason(action, context);
    return { action, enabled: reason === null, disabledReason: reason };
  });
}

/** 将 textarea 值规范化为唯一可提交的 reason，拒绝所有控制字符。 */
export function validateInstallationReason(value: string): InstallationReasonValidation {
  const reason = value.trim();
  if (!reason) return { ok: false, error: "原因不能为空" };
  if (reason.length > MAX_REASON_LENGTH) {
    return { ok: false, error: `原因不能超过 ${MAX_REASON_LENGTH} 个字符` };
  }
  if (CONTROL_CHARACTER.test(reason)) {
    return { ok: false, error: "原因不能包含控制字符或换行" };
  }
  return { ok: true, reason };
}
