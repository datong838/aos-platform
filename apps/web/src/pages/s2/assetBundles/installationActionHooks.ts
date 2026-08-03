import { useCallback, useMemo, useRef, useState } from "react";
import { assetControlClient } from "../../../api/assetControl/client";
import { normalizeAssetControlError, type AssetControlError } from "../../../api/assetControl/errors";
import { buildApproveInstallationRequest } from "../../../api/assetControl/installationActions";
import {
  createIdempotentCommand,
  idempotencyKeyFor,
  type IdempotentCommand,
  type IdempotencyKey,
} from "../../../api/assetControl/idempotency";
import type {
  ApproveInstallationRequest,
  InstallationResponse,
  RejectInstallationRequest,
  RollbackInstallationRequest,
  StoredCompositionLock,
} from "../../../api/assetControl/types";
import {
  INSTALLATION_ACTIONS,
  createInstallationActionAttempt,
  exactActionSuccessWasObserved,
  initialInstallationActionState,
  installationActionEligibility,
  normalizeInstallationActionReason,
  phaseForInstallationActionError,
  type InstallationActionAttempt,
  type InstallationActionBody,
  type InstallationActionCommandState,
  type InstallationActionEligibility,
  type InstallationActionName,
  type InstallationActionPrincipal,
  type InstallationActionReconciliation,
} from "./installationActionModel";

export interface InstallationActionDependencies {
  readonly createCommand: () => Readonly<IdempotentCommand>;
  readonly getInstallation: (installationId: string) => Promise<InstallationResponse>;
  readonly getCompositionLock: (
    compositionId: string,
    revision: number,
  ) => Promise<StoredCompositionLock>;
  readonly buildApproveRequest: (
    installation: InstallationResponse,
    lock: StoredCompositionLock,
  ) => ApproveInstallationRequest;
  readonly submitInstallation: (
    installationId: string,
    options: ActionOptions,
  ) => Promise<InstallationResponse>;
  readonly approveInstallation: (
    installationId: string,
    body: ApproveInstallationRequest,
    options: ActionOptions,
  ) => Promise<InstallationResponse>;
  readonly rejectInstallation: (
    installationId: string,
    body: RejectInstallationRequest,
    options: ActionOptions,
  ) => Promise<InstallationResponse>;
  readonly applyInstallation: (
    installationId: string,
    options: ActionOptions,
  ) => Promise<InstallationResponse>;
  readonly verifyInstallation: (
    installationId: string,
    options: ActionOptions,
  ) => Promise<InstallationResponse>;
  readonly rollbackInstallation: (
    installationId: string,
    body: RollbackInstallationRequest,
    options: ActionOptions,
  ) => Promise<InstallationResponse>;
}

interface ActionOptions {
  readonly idempotencyKey: IdempotencyKey;
  readonly etagVersion: number;
}

export interface InstallationActionInput {
  readonly reason?: string;
}

export interface InstallationActionCommands {
  readonly state: InstallationActionCommandState;
  readonly availability: Readonly<
    Record<InstallationActionName, InstallationActionEligibility>
  >;
  readonly execute: (
    action: InstallationActionName,
    input?: InstallationActionInput,
  ) => Promise<boolean>;
  readonly recoverUnknown: () => Promise<boolean>;
}

export interface InstallationActionOptions {
  readonly installation: InstallationResponse | null;
  readonly principal: InstallationActionPrincipal;
  readonly dependencies?: InstallationActionDependencies;
  readonly onSuccess?: (installation: InstallationResponse) => void;
  readonly onReconciled?: (installation: InstallationResponse) => void;
}

const defaultDependencies: InstallationActionDependencies = {
  createCommand: createIdempotentCommand,
  getInstallation: (installationId) =>
    assetControlClient.getInstallation(installationId),
  getCompositionLock: (compositionId, revision) =>
    assetControlClient.getCompositionLock(compositionId, revision),
  buildApproveRequest: buildApproveInstallationRequest,
  submitInstallation: (installationId, options) =>
    assetControlClient.submitInstallation(installationId, options),
  approveInstallation: (installationId, body, options) =>
    assetControlClient.approveInstallation(installationId, body, options),
  rejectInstallation: (installationId, body, options) =>
    assetControlClient.rejectInstallation(installationId, body, options),
  applyInstallation: (installationId, options) =>
    assetControlClient.applyInstallation(installationId, options),
  verifyInstallation: (installationId, options) =>
    assetControlClient.verifyInstallation(installationId, options),
  rollbackInstallation: (installationId, body, options) =>
    assetControlClient.rollbackInstallation(installationId, body, options),
};

export function useInstallationActionCommands(
  options: InstallationActionOptions,
): InstallationActionCommands {
  const dependenciesRef = useRef(options.dependencies ?? defaultDependencies);
  dependenciesRef.current = options.dependencies ?? defaultDependencies;
  const installationRef = useRef(options.installation);
  installationRef.current = options.installation;
  const principalRef = useRef(options.principal);
  principalRef.current = options.principal;
  const onSuccessRef = useRef(options.onSuccess);
  onSuccessRef.current = options.onSuccess;
  const onReconciledRef = useRef(options.onReconciled);
  onReconciledRef.current = options.onReconciled;

  const [state, setState] = useState<InstallationActionCommandState>(
    initialInstallationActionState,
  );
  const stateRef = useRef(state);
  const busyRef = useRef(false);

  const commit = useCallback((next: InstallationActionCommandState) => {
    stateRef.current = next;
    setState(next);
  }, []);

  const notifySuccess = useCallback((installation: InstallationResponse) => {
    try {
      onSuccessRef.current?.(installation);
    } catch (callbackError) {
      console.error("installation action success callback failed", callbackError);
    }
  }, []);

  const notifyReconciled = useCallback((installation: InstallationResponse) => {
    try {
      onReconciledRef.current?.(installation);
    } catch (callbackError) {
      console.error("installation action reconciliation callback failed", callbackError);
    }
  }, []);

  const finalReadAfterSuccess = useCallback(
    async (
      attempt: Readonly<InstallationActionAttempt>,
      commandResponse: InstallationResponse,
    ): Promise<boolean> => {
      commit({
        ...stateRef.current,
        phase: "reconciling",
        action: attempt.action,
        data: commandResponse,
        error: null,
        reconcileError: null,
        attempt,
        reconciliation: "final_read",
        requiresRefresh: false,
        canRecoverUnknown: false,
        mutationConfirmed: true,
      });
      try {
        const current = await dependenciesRef.current.getInstallation(
          attempt.installationId,
        );
        commit({
          phase: "succeeded",
          action: attempt.action,
          data: current,
          error: null,
          reconcileError: null,
          attempt: null,
          reconciliation: "confirmed",
          requiresRefresh: false,
          canRecoverUnknown: false,
          mutationConfirmed: true,
        });
        notifySuccess(current);
        return true;
      } catch (cause) {
        const reconcileError = normalizeAssetControlError(cause);
        commit({
          phase: "error",
          action: attempt.action,
          data: commandResponse,
          error: reconcileError,
          reconcileError,
          attempt: null,
          reconciliation: "unavailable",
          requiresRefresh: true,
          canRecoverUnknown: false,
          mutationConfirmed: true,
        });
        return false;
      }
    },
    [commit, notifySuccess],
  );

  const reconcileConflict = useCallback(
    async (
      attempt: Readonly<InstallationActionAttempt>,
      conflict: AssetControlError,
    ): Promise<boolean> => {
      commit({
        ...stateRef.current,
        phase: "reconciling",
        action: attempt.action,
        error: conflict,
        reconcileError: null,
        attempt: null,
        reconciliation: "final_read",
        requiresRefresh: true,
        canRecoverUnknown: false,
        mutationConfirmed: false,
      });
      try {
        const current = await dependenciesRef.current.getInstallation(
          attempt.installationId,
        );
        commit({
          phase: "conflict",
          action: attempt.action,
          data: current,
          error: conflict,
          reconcileError: null,
          attempt: null,
          reconciliation: "diverged",
          requiresRefresh: false,
          canRecoverUnknown: false,
          mutationConfirmed: false,
        });
        notifyReconciled(current);
      } catch (cause) {
        commit({
          phase: "conflict",
          action: attempt.action,
          data: null,
          error: conflict,
          reconcileError: normalizeAssetControlError(cause),
          attempt: null,
          reconciliation: "unavailable",
          requiresRefresh: true,
          canRecoverUnknown: false,
          mutationConfirmed: false,
        });
      }
      return false;
    },
    [commit, notifyReconciled],
  );

  const recordPostFailure = useCallback(
    async (
      attempt: Readonly<InstallationActionAttempt>,
      cause: unknown,
    ): Promise<boolean> => {
      const error = normalizeAssetControlError(cause);
      if (error.isConflict) return reconcileConflict(attempt, error);
      if (error.outcomeUnknown) {
        commit({
          phase: "unknown_outcome",
          action: attempt.action,
          data: null,
          error,
          reconcileError: null,
          attempt,
          reconciliation: "none",
          requiresRefresh: true,
          canRecoverUnknown: true,
          mutationConfirmed: false,
        });
        return false;
      }
      commit({
        phase: phaseForInstallationActionError(error),
        action: attempt.action,
        data: null,
        error,
        reconcileError: null,
        attempt: null,
        reconciliation: "none",
        requiresRefresh: error.requiresRefresh,
        canRecoverUnknown: false,
        mutationConfirmed: false,
      });
      return false;
    },
    [commit, reconcileConflict],
  );

  const performAttempt = useCallback(
    async (attempt: Readonly<InstallationActionAttempt>): Promise<InstallationResponse> => {
      const dependencies = dependenciesRef.current;
      const actionOptions: ActionOptions = {
        idempotencyKey: idempotencyKeyFor(attempt.command),
        etagVersion: attempt.source.etagVersion,
      };
      switch (attempt.action) {
        case "submit":
          return dependencies.submitInstallation(attempt.installationId, actionOptions);
        case "approve":
          return dependencies.approveInstallation(
            attempt.installationId,
            attempt.body as ApproveInstallationRequest,
            actionOptions,
          );
        case "reject":
          return dependencies.rejectInstallation(
            attempt.installationId,
            attempt.body as RejectInstallationRequest,
            actionOptions,
          );
        case "apply":
          return dependencies.applyInstallation(attempt.installationId, actionOptions);
        case "verify":
          return dependencies.verifyInstallation(attempt.installationId, actionOptions);
        case "rollback":
          return dependencies.rollbackInstallation(
            attempt.installationId,
            attempt.body as RollbackInstallationRequest,
            actionOptions,
          );
      }
    },
    [],
  );

  const execute = useCallback(
    async (
      action: InstallationActionName,
      input: InstallationActionInput = {},
    ): Promise<boolean> => {
      const displayed = installationRef.current;
      const principal = principalRef.current;
      if (
        busyRef.current ||
        stateRef.current.phase === "running" ||
        stateRef.current.phase === "reconciling" ||
        stateRef.current.phase === "unknown_outcome" ||
        !installationActionEligibility(displayed, principal, action).allowed ||
        displayed === null
      ) {
        return false;
      }

      busyRef.current = true;
      commit({
        phase: "reconciling",
        action,
        data: displayed,
        error: null,
        reconcileError: null,
        attempt: null,
        reconciliation: "preflight",
        requiresRefresh: false,
        canRecoverUnknown: false,
        mutationConfirmed: false,
      });

      try {
        const current = await dependenciesRef.current.getInstallation(
          displayed.installationId,
        );
        if (!sameConfirmedInstallationFacts(displayed, current)) {
          commit({
            phase: "conflict",
            action,
            data: current,
            error: null,
            reconcileError: null,
            attempt: null,
            reconciliation: "diverged",
            requiresRefresh: false,
            canRecoverUnknown: false,
            mutationConfirmed: false,
          });
          notifyReconciled(current);
          return false;
        }
        if (!installationActionEligibility(current, principal, action).allowed) {
          commit({
            ...initialInstallationActionState(),
            phase: "conflict",
            action,
            data: current,
            reconciliation: "diverged",
            requiresRefresh: false,
          });
          notifyReconciled(current);
          return false;
        }

        const body = await buildActionBody(
          action,
          input,
          current,
          dependenciesRef.current,
        );
        const command = dependenciesRef.current.createCommand();
        const subject = principal.subject?.trim();
        if (!subject) return false;
        const attempt = createInstallationActionAttempt({
          action,
          installation: current,
          body,
          command,
          actorSubject: subject,
        });
        commit({
          phase: "running",
          action,
          data: current,
          error: null,
          reconcileError: null,
          attempt,
          reconciliation: "none",
          requiresRefresh: false,
          canRecoverUnknown: false,
          mutationConfirmed: false,
        });

        try {
          const response = await performAttempt(attempt);
          return await finalReadAfterSuccess(attempt, response);
        } catch (cause) {
          return await recordPostFailure(attempt, cause);
        }
      } catch (cause) {
        const error = normalizeAssetControlError(cause);
        commit({
          phase:
            error.kind === "forbidden"
              ? "forbidden"
              : error.kind === "not_visible_or_missing"
                ? "not_visible_or_missing"
                : "error",
          action,
          data: null,
          error,
          reconcileError: null,
          attempt: null,
          reconciliation: "unavailable",
          requiresRefresh: error.requiresRefresh,
          canRecoverUnknown: false,
          mutationConfirmed: false,
        });
        return false;
      } finally {
        busyRef.current = false;
      }
    },
    [
      commit,
      finalReadAfterSuccess,
      notifyReconciled,
      performAttempt,
      recordPostFailure,
    ],
  );

  const recoverUnknown = useCallback(async (): Promise<boolean> => {
    const attempt = stateRef.current.attempt;
    if (
      busyRef.current ||
      stateRef.current.phase !== "unknown_outcome" ||
      !stateRef.current.canRecoverUnknown ||
      attempt === null
    ) {
      return false;
    }
    busyRef.current = true;
    commit({
      ...stateRef.current,
      phase: "reconciling",
      error: null,
      reconcileError: null,
      reconciliation: "preflight",
      canRecoverUnknown: false,
    });

    try {
      let current: InstallationResponse;
      try {
        current = await dependenciesRef.current.getInstallation(
          attempt.installationId,
        );
      } catch (cause) {
        commitUnknownAfterRecoveryFailure(attempt, cause, "unavailable", commit);
        return false;
      }

      if (exactActionSuccessWasObserved(attempt, current)) {
        commit({
          phase: "succeeded",
          action: attempt.action,
          data: current,
          error: null,
          reconcileError: null,
          attempt: null,
          reconciliation: "confirmed",
          requiresRefresh: false,
          canRecoverUnknown: false,
          mutationConfirmed: true,
        });
        notifySuccess(current);
        return true;
      }

      const unchanged = installationIsUnchanged(attempt, current);
      if (!unchanged) {
        commit({
          phase: "conflict",
          action: attempt.action,
          data: current,
          error: stateRef.current.error,
          reconcileError: null,
          attempt: null,
          reconciliation: "diverged",
          requiresRefresh: false,
          canRecoverUnknown: false,
          mutationConfirmed: false,
        });
        notifyReconciled(current);
        return false;
      }

      const reconciliation: InstallationActionReconciliation = "unchanged";
      commit({
        ...stateRef.current,
        phase: "running",
        data: current,
        error: null,
        reconcileError: null,
        attempt,
        reconciliation,
        requiresRefresh: false,
        canRecoverUnknown: false,
      });
      try {
        const response = await performAttempt(attempt);
        return await finalReadAfterSuccess(attempt, response);
      } catch (cause) {
        return await recordPostFailure(attempt, cause);
      }
    } finally {
      busyRef.current = false;
    }
  }, [
    commit,
    finalReadAfterSuccess,
    notifySuccess,
    performAttempt,
    recordPostFailure,
  ]);

  const availability = useMemo(() => {
    const result = {} as Record<InstallationActionName, InstallationActionEligibility>;
    for (const action of INSTALLATION_ACTIONS) {
      result[action] = installationActionEligibility(
        options.installation,
        options.principal,
        action,
      );
    }
    return result;
  }, [options.installation, options.principal]);

  return useMemo(
    () => ({ state, availability, execute, recoverUnknown }),
    [availability, execute, recoverUnknown, state],
  );
}

async function buildActionBody(
  action: InstallationActionName,
  input: InstallationActionInput,
  installation: InstallationResponse,
  dependencies: InstallationActionDependencies,
): Promise<InstallationActionBody> {
  if (action === "approve") {
    const lock = await dependencies.getCompositionLock(
      installation.current.compositionId,
      installation.current.lockRevision,
    );
    return dependencies.buildApproveRequest(installation, lock);
  }
  if (action === "reject" || action === "rollback") {
    return { reason: normalizeInstallationActionReason(input.reason ?? "") };
  }
  return {};
}

function installationIsUnchanged(
  attempt: InstallationActionAttempt,
  installation: InstallationResponse,
): boolean {
  return (
    installation.installationId === attempt.installationId &&
    installation.state === attempt.source.state &&
    installation.currentRevision === attempt.source.currentRevision &&
    installation.etagVersion === attempt.source.etagVersion
  );
}

/** The user must confirm the exact server facts that will feed the action. */
function sameConfirmedInstallationFacts(
  displayed: InstallationResponse,
  current: InstallationResponse,
): boolean {
  if (
    displayed.installationId !== current.installationId ||
    displayed.state !== current.state ||
    displayed.currentRevision !== current.currentRevision ||
    displayed.etagVersion !== current.etagVersion ||
    displayed.activeRevision !== current.activeRevision ||
    displayed.previousActiveRevision !== current.previousActiveRevision ||
    displayed.current.compositionId !== current.current.compositionId ||
    displayed.current.lockRevision !== current.current.lockRevision ||
    displayed.current.requestedBy !== current.current.requestedBy
  ) {
    return false;
  }
  return ([
    "lockHash",
    "permissionDiffHash",
    "migrationPlanHash",
    "contributionDiffHash",
  ] as const).every((field) => displayed.current[field] === current.current[field]);
}

function commitUnknownAfterRecoveryFailure(
  attempt: Readonly<InstallationActionAttempt>,
  cause: unknown,
  reconciliation: InstallationActionReconciliation,
  commit: (next: InstallationActionCommandState) => void,
): void {
  const error = normalizeAssetControlError(cause);
  commit({
    phase: "unknown_outcome",
    action: attempt.action,
    data: null,
    error,
    reconcileError: error,
    attempt,
    reconciliation,
    requiresRefresh: true,
    canRecoverUnknown: true,
    mutationConfirmed: false,
  });
}
