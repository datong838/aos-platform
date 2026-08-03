import { describe, expect, it } from "vitest";

import type { InstallationState } from "../../../api/assetControl/types";
import {
  installationActionAvailability,
  type InstallationAction,
  type InstallationActionContext,
  validateInstallationReason,
} from "./installationActions";
import {
  INSTALLATION_ACTIONS,
  installationActionEligibility,
} from "./installationActionModel";
import { INSTALLATION_DRAFT_FIXTURE } from "../../../api/assetControl/installationFixtures";

const EXPECTED: Readonly<Record<InstallationState, readonly InstallationAction[]>> = {
  draft: ["submit"],
  submitted: ["approve", "reject"],
  approved: ["apply"],
  rejected: [],
  applied: ["verify"],
  active: ["rollback"],
  rolled_back: [],
};

function context(overrides: Partial<InstallationActionContext> = {}): InstallationActionContext {
  return {
    state: "draft",
    requestedBy: "maker@example.test",
    subject: "operator@example.test",
    roles: ["admin"],
    ready: true,
    stale: false,
    refreshing: false,
    offline: false,
    pendingAction: null,
    ...overrides,
  };
}

describe("installation action policy", () => {
  it("与 controller 的七状态、角色和 maker-checker 资格矩阵保持一致", () => {
    const roleSets = [
      ["admin"],
      ["developer"],
      ["asset-installer"],
      ["asset-install-approver"],
      ["viewer"],
      ["  Asset-Installer  "],
    ] as const;
    for (const state of Object.keys(EXPECTED) as InstallationState[]) {
      const installation = {
        ...INSTALLATION_DRAFT_FIXTURE,
        state,
        current: { ...INSTALLATION_DRAFT_FIXTURE.current, state },
      };
      for (const roles of roleSets) {
        const ui = installationActionAvailability(context({ state, roles }));
        for (const action of INSTALLATION_ACTIONS) {
          const uiAllowed = ui.find((item) => item.action === action)?.enabled ?? false;
          const controllerAllowed = installationActionEligibility(
            installation,
            { subject: "operator@example.test", roles },
            action,
          ).allowed;
          expect(uiAllowed, `${state}/${roles.join(",")}/${action}`).toBe(
            controllerAllowed,
          );
        }
      }
    }

    const submitted = {
      ...INSTALLATION_DRAFT_FIXTURE,
      state: "submitted" as const,
      current: {
        ...INSTALLATION_DRAFT_FIXTURE.current,
        state: "submitted" as const,
      },
    };
    const uiMaker = installationActionAvailability(context({
      state: "submitted",
      subject: submitted.current.requestedBy,
      roles: ["admin"],
    }));
    for (const action of ["approve", "reject"] as const) {
      expect(uiMaker.find((item) => item.action === action)?.enabled).toBe(false);
      expect(installationActionEligibility(
        submitted,
        { subject: submitted.current.requestedBy, roles: ["admin"] },
        action,
      ).allowed).toBe(false);
    }
  });

  it("严格映射七种服务端状态，终态没有动作", () => {
    for (const [state, actions] of Object.entries(EXPECTED) as Array<[
      InstallationState,
      readonly InstallationAction[],
    ]>) {
      expect(installationActionAvailability(context({ state })).map((item) => item.action)).toEqual(actions);
    }
  });

  it("严格映射角色并且 admin 也不能绕过 maker-checker", () => {
    expect(installationActionAvailability(context({ state: "draft", roles: ["developer"] }))[0]?.enabled).toBe(true);
    expect(installationActionAvailability(context({ state: "approved", roles: ["developer"] }))[0]?.enabled).toBe(false);
    expect(installationActionAvailability(context({ state: "approved", roles: ["asset-installer"] }))[0]?.enabled).toBe(true);
    expect(installationActionAvailability(context({ state: "approved", roles: ["  Asset-Installer  "] }))[0]?.enabled).toBe(true);
    expect(installationActionAvailability(context({ state: "submitted", roles: ["asset-install-approver"] }))).toHaveLength(2);

    const makerDecision = installationActionAvailability(context({
      state: "submitted",
      subject: "maker@example.test",
      roles: ["admin"],
    }));
    expect(makerDecision.every((item) => !item.enabled)).toBe(true);
    expect(makerDecision.every((item) => item.disabledReason?.includes("不能批准或拒绝"))).toBe(true);
  });

  it.each([
    ["身份缺失", { subject: undefined }],
    ["详情未就绪", { ready: false }],
    ["旧数据", { stale: true }],
    ["刷新中", { refreshing: true }],
    ["离线", { offline: true }],
    ["动作 pending", { pendingAction: "submit" as const }],
  ])("%s 时 fail-closed", (_label, overrides) => {
    expect(installationActionAvailability(context(overrides))[0]?.enabled).toBe(false);
  });

  it("trim 原因后提交，并拒绝空白、超长和控制字符", () => {
    expect(validateInstallationReason("  有明确业务原因  ")).toEqual({ ok: true, reason: "有明确业务原因" });
    expect(validateInstallationReason("   ").ok).toBe(false);
    expect(validateInstallationReason("x".repeat(2001)).ok).toBe(false);
    expect(validateInstallationReason("第一行\n第二行").ok).toBe(false);
    expect(validateInstallationReason("bad\u0000reason").ok).toBe(false);
  });
});
