import { describe, expect, it } from "vitest";
import type { IdempotentCommand } from "../../../api/assetControl/idempotency";
import type {
  InstallationResponse,
  InstallationState,
} from "../../../api/assetControl/types";
import {
  INSTALLATION_ACTIONS,
  createInstallationActionAttempt,
  exactActionSuccessWasObserved,
  installationActionEligibility,
  normalizeInstallationActionReason,
  type InstallationActionName,
} from "./installationActionModel";

const command = { idempotencyKey: "key-1" } as unknown as Readonly<IdempotentCommand>;

describe("M3-4 installation action model", () => {
  it("exposes exactly the legal state edge and required role", () => {
    const cases: readonly [InstallationState, readonly InstallationActionName[], string][] = [
      ["draft", ["submit"], "developer"],
      ["submitted", ["approve", "reject"], "asset-install-approver"],
      ["approved", ["apply"], "asset-installer"],
      ["applied", ["verify"], "asset-installer"],
      ["active", ["rollback", "uninstall"], "asset-installer"],
    ];
    for (const [state, expected, role] of cases) {
      const installation = record(state);
      for (const action of INSTALLATION_ACTIONS) {
        expect(
          installationActionEligibility(
            installation,
            { subject: "reviewer", roles: [role] },
            action,
          ).allowed,
          `${state}/${action}`,
        ).toBe(expected.includes(action));
      }
    }
    for (const state of ["rejected", "rolled_back", "uninstalled"] as const) {
      expect(
        INSTALLATION_ACTIONS.every(
          (action) =>
            !installationActionEligibility(
              record(state),
              { subject: "admin-2", roles: ["admin"] },
              action,
            ).allowed,
        ),
      ).toBe(true);
    }
  });

  it("fails closed for unknown principal and enforces maker-checker even for admin", () => {
    const submitted = record("submitted");
    expect(
      installationActionEligibility(
        submitted,
        { subject: null, roles: ["admin"] },
        "approve",
      ).reason,
    ).toBe("principal_unknown");
    expect(
      installationActionEligibility(
        submitted,
        { subject: "requester", roles: ["admin"] },
        "approve",
      ).reason,
    ).toBe("maker_checker");
    expect(
      installationActionEligibility(
        submitted,
        { subject: "reviewer", roles: ["developer"] },
        "approve",
      ).reason,
    ).toBe("role_denied");
  });

  it("normalizes reasons and rejects empty, oversized, or control-character input", () => {
    expect(normalizeInstallationActionReason("  rollback because unsafe  ")).toBe(
      "rollback because unsafe",
    );
    expect(() => normalizeInstallationActionReason("   ")).toThrow("1-2000");
    expect(() => normalizeInstallationActionReason("x".repeat(2_001))).toThrow("1-2000");
    expect(() => normalizeInstallationActionReason("unsafe\nreason")).toThrow("1-2000");
  });

  it("freezes the complete attempt and only confirms an exact successor event", () => {
    const source = record("active", 5, 8);
    const attempt = createInstallationActionAttempt({
      action: "rollback",
      installation: source,
      body: { reason: "unsafe" },
      command,
      actorSubject: "installer",
    });
    expect(Object.isFrozen(attempt)).toBe(true);
    expect(Object.isFrozen(attempt.source)).toBe(true);
    expect(Object.isFrozen(attempt.body)).toBe(true);

    const successor = record("rolled_back", 6, 9, {
      fromRevision: 5,
      toRevision: 6,
      fromState: "active",
      toState: "rolled_back",
      actor: "installer",
      reason: "unsafe",
      evidenceType: "rollback",
    });
    expect(exactActionSuccessWasObserved(attempt, successor)).toBe(true);
    expect(
      exactActionSuccessWasObserved(attempt, {
        ...successor,
        events: [{ ...successor.events[0], evidence: null }],
      }),
    ).toBe(false);
    expect(
      exactActionSuccessWasObserved(attempt, {
        ...successor,
        events: [{ ...successor.events[0], actor: "someone-else" }],
      }),
    ).toBe(false);
  });
});

function record(
  state: InstallationState,
  currentRevision = 4,
  etagVersion = 6,
  event?: {
    fromRevision: number;
    toRevision: number;
    fromState: InstallationState;
    toState: InstallationState;
    actor: string;
    reason: string | null;
    evidenceType?: "dry_apply" | "verification" | "rollback";
  },
): InstallationResponse {
  return {
    installationId: "11111111-1111-4111-8111-111111111111",
    displayName: "Commerce",
    state,
    currentRevision,
    activeRevision: state === "active" ? currentRevision : null,
    previousActiveRevision: null,
    etagVersion,
    current: {
      installationId: "11111111-1111-4111-8111-111111111111",
      revision: currentRevision,
      parentRevision: currentRevision === 1 ? null : currentRevision - 1,
      state,
      compositionId: "22222222-2222-4222-8222-222222222222",
      lockRevision: 3,
      lockHash: "sha256:lock",
      permissionDiffHash: "sha256:permission",
      migrationPlanHash: "sha256:migration",
      contributionDiffHash: "sha256:contribution",
      overlayRevision: "overlay-1",
      requestedBy: "requester",
      decisionId: null,
      createdAt: "2026-08-03T00:00:00Z",
    },
    decision: null,
    events: event
      ? [{
          sequence: 1,
          evidence: event.evidenceType
            ? {
                type: event.evidenceType,
                evidenceRef: "evidence://server-generated",
                evidenceHash: "sha256:evidence",
                status: "valid" as const,
                observedAt: "2026-08-03T00:00:00Z",
              }
            : null,
          createdAt: "2026-08-03T00:00:00Z",
          ...event,
        }]
      : [],
    createdAt: "2026-08-03T00:00:00Z",
    updatedAt: "2026-08-03T00:00:00Z",
  };
}
