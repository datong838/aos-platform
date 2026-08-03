import { useCallback, useMemo, useRef, useState } from "react";
import { assetControlClient } from "../../../api/assetControl/client";
import { normalizeAssetControlError } from "../../../api/assetControl/errors";
import {
  createIdempotentCommand,
  idempotencyKeyFor,
  type IdempotentCommand,
  type IdempotencyKey,
} from "../../../api/assetControl/idempotency";
import type {
  CompositionRequest,
  CreateInstallationRequest,
  InstallationResponse,
  StoredCompositionLock,
} from "../../../api/assetControl/types";
import {
  beginCommand,
  canCreateInstallation,
  compositionLocksEqual,
  failCommand,
  initialCommandState,
  isBusyCommand,
  markCommandInputChanged,
  reconcileCommand,
  succeedCommand,
  type CreateInstallationCommandState,
  type ResolveCommandState,
} from "./commandModel";

export type CreateInstallationDraft = Pick<
  CreateInstallationRequest,
  "overlayRevision" | "displayName"
>;

export interface ResolveCreateDependencies {
  readonly createCommand: () => Readonly<IdempotentCommand>;
  readonly resolveComposition: (
    body: CompositionRequest,
    options: { idempotencyKey: IdempotencyKey },
  ) => Promise<StoredCompositionLock>;
  readonly getCompositionLock: (
    compositionId: string,
    revision: number,
  ) => Promise<StoredCompositionLock>;
  readonly createInstallation: (
    body: CreateInstallationRequest,
    options: { idempotencyKey: IdempotencyKey },
  ) => Promise<InstallationResponse>;
}

export interface ResolveCreateCommands {
  readonly inputRevision: number;
  readonly resolveState: ResolveCommandState;
  readonly createState: CreateInstallationCommandState;
  readonly canCreate: boolean;
  readonly markInputChanged: () => boolean;
  readonly resolve: (request: CompositionRequest) => Promise<boolean>;
  readonly retryResolve: () => Promise<boolean>;
  readonly create: (draft: CreateInstallationDraft) => Promise<boolean>;
  readonly retryCreate: () => Promise<boolean>;
}

export interface ResolveCreateOptions {
  readonly dependencies?: ResolveCreateDependencies;
  readonly onCreateSuccess?: (installation: InstallationResponse) => void;
}

interface ResolveAttempt {
  readonly request: CompositionRequest;
  readonly command: Readonly<IdempotentCommand>;
  readonly inputRevision: number;
}

interface CreateAttempt {
  readonly request: CreateInstallationRequest;
  readonly command: Readonly<IdempotentCommand>;
  readonly inputRevision: number;
}

const defaultDependencies: ResolveCreateDependencies = {
  createCommand: createIdempotentCommand,
  resolveComposition: (body, options) =>
    assetControlClient.resolveComposition(body, options),
  getCompositionLock: (compositionId, revision) =>
    assetControlClient.getCompositionLock(compositionId, revision),
  createInstallation: (body, options) =>
    assetControlClient.createInstallation(body, options),
};

export function useResolveCreateCommands(
  options: ResolveCreateOptions = {},
): ResolveCreateCommands {
  const dependenciesRef = useRef(options.dependencies ?? defaultDependencies);
  dependenciesRef.current = options.dependencies ?? defaultDependencies;
  const onCreateSuccessRef = useRef(options.onCreateSuccess);
  onCreateSuccessRef.current = options.onCreateSuccess;

  const [inputRevision, setInputRevision] = useState(0);
  const inputRevisionRef = useRef(0);

  const [resolveState, setResolveState] = useState<ResolveCommandState>(() =>
    initialCommandState<StoredCompositionLock>(0),
  );
  const resolveStateRef = useRef(resolveState);
  const [createState, setCreateState] = useState<CreateInstallationCommandState>(() =>
    initialCommandState<InstallationResponse>(0),
  );
  const createStateRef = useRef(createState);

  const resolveAttemptRef = useRef<ResolveAttempt | null>(null);
  const createAttemptRef = useRef<CreateAttempt | null>(null);
  const resolveSequenceRef = useRef(0);
  const createSequenceRef = useRef(0);
  const resolveBusyRef = useRef(false);
  const createBusyRef = useRef(false);

  const commitResolve = useCallback((next: ResolveCommandState) => {
    resolveStateRef.current = next;
    setResolveState(next);
  }, []);

  const commitCreate = useCallback((next: CreateInstallationCommandState) => {
    createStateRef.current = next;
    setCreateState(next);
  }, []);

  const runResolve = useCallback(
    async (attempt: ResolveAttempt): Promise<boolean> => {
      if (resolveBusyRef.current) return false;
      resolveBusyRef.current = true;
      const sequence = ++resolveSequenceRef.current;
      resolveAttemptRef.current = attempt;
      commitResolve(
        beginCommand(resolveStateRef.current, attempt.command, attempt.inputRevision),
      );

      try {
        const commandResponse = await dependenciesRef.current.resolveComposition(
          attempt.request,
          { idempotencyKey: idempotencyKeyFor(attempt.command) },
        );
        if (sequence !== resolveSequenceRef.current) return false;

        commitResolve(reconcileCommand(resolveStateRef.current, commandResponse));
        const persistedResponse = await dependenciesRef.current.getCompositionLock(
          commandResponse.compositionId,
          commandResponse.revision,
        );
        if (sequence !== resolveSequenceRef.current) return false;
        if (!compositionLocksEqual(commandResponse, persistedResponse)) {
          throw new Error("resolve response does not match the persisted composition lock");
        }

        commitResolve(
          succeedCommand(resolveStateRef.current, persistedResponse, attempt.inputRevision),
        );
        resolveAttemptRef.current = null;
        return true;
      } catch (cause) {
        if (sequence !== resolveSequenceRef.current) return false;
        const failed = failCommand(
          resolveStateRef.current,
          normalizeAssetControlError(cause),
        );
        commitResolve(failed);
        if (!failed.canRetrySameCommand) resolveAttemptRef.current = null;
        return false;
      } finally {
        if (sequence === resolveSequenceRef.current) resolveBusyRef.current = false;
      }
    },
    [commitResolve],
  );

  const resolve = useCallback(
    async (request: CompositionRequest): Promise<boolean> => {
      const current = resolveStateRef.current;
      if (
        resolveBusyRef.current ||
        isBusyCommand(current) ||
        current.phase === "unknown_outcome"
      ) {
        return false;
      }

      let command: Readonly<IdempotentCommand>;
      try {
        command = dependenciesRef.current.createCommand();
      } catch (cause) {
        commitResolve(failCommand(current, normalizeAssetControlError(cause)));
        return false;
      }

      return runResolve({ request, command, inputRevision: inputRevisionRef.current });
    },
    [commitResolve, runResolve],
  );

  const retryResolve = useCallback(async (): Promise<boolean> => {
    const attempt = resolveAttemptRef.current;
    const current = resolveStateRef.current;
    if (
      !attempt ||
      resolveBusyRef.current ||
      current.phase !== "unknown_outcome" ||
      !current.canRetrySameCommand
    ) {
      return false;
    }
    return runResolve(attempt);
  }, [runResolve]);

  const runCreate = useCallback(
    async (attempt: CreateAttempt): Promise<boolean> => {
      if (createBusyRef.current) return false;
      createBusyRef.current = true;
      const sequence = ++createSequenceRef.current;
      createAttemptRef.current = attempt;
      commitCreate(
        beginCommand(createStateRef.current, attempt.command, attempt.inputRevision),
      );

      try {
        const installation = await dependenciesRef.current.createInstallation(
          attempt.request,
          { idempotencyKey: idempotencyKeyFor(attempt.command) },
        );
        if (sequence !== createSequenceRef.current) return false;

        commitCreate(
          succeedCommand(createStateRef.current, installation, attempt.inputRevision),
        );
        createAttemptRef.current = null;
        try {
          onCreateSuccessRef.current?.(installation);
        } catch (callbackError) {
          console.error("installation success callback failed", callbackError);
        }
        return true;
      } catch (cause) {
        if (sequence !== createSequenceRef.current) return false;
        const failed = failCommand(
          createStateRef.current,
          normalizeAssetControlError(cause),
        );
        commitCreate(failed);
        if (!failed.canRetrySameCommand) createAttemptRef.current = null;
        return false;
      } finally {
        if (sequence === createSequenceRef.current) createBusyRef.current = false;
      }
    },
    [commitCreate],
  );

  const create = useCallback(
    async (draft: CreateInstallationDraft): Promise<boolean> => {
      const currentCreate = createStateRef.current;
      const currentResolve = resolveStateRef.current;
      const currentRevision = inputRevisionRef.current;
      if (
        createBusyRef.current ||
        isBusyCommand(currentCreate) ||
        currentCreate.phase === "unknown_outcome" ||
        !canCreateInstallation(currentResolve, currentRevision) ||
        !isValidCreateDraft(draft)
      ) {
        return false;
      }

      let command: Readonly<IdempotentCommand>;
      try {
        command = dependenciesRef.current.createCommand();
      } catch (cause) {
        commitCreate(failCommand(currentCreate, normalizeAssetControlError(cause)));
        return false;
      }

      const lock = currentResolve.data;
      if (lock === null) return false;
      const request: CreateInstallationRequest = {
        compositionId: lock.compositionId,
        lockRevision: lock.revision,
        overlayRevision: draft.overlayRevision,
        displayName: draft.displayName,
      };
      return runCreate({ request, command, inputRevision: currentRevision });
    },
    [commitCreate, runCreate],
  );

  const retryCreate = useCallback(async (): Promise<boolean> => {
    const attempt = createAttemptRef.current;
    const current = createStateRef.current;
    if (
      !attempt ||
      createBusyRef.current ||
      current.phase !== "unknown_outcome" ||
      !current.canRetrySameCommand
    ) {
      return false;
    }
    return runCreate(attempt);
  }, [runCreate]);

  const markInputChanged = useCallback((): boolean => {
    const currentResolve = resolveStateRef.current;
    const currentCreate = createStateRef.current;
    if (
      createBusyRef.current ||
      isBusyCommand(currentCreate) ||
      currentCreate.phase === "unknown_outcome" ||
      currentResolve.phase === "unknown_outcome"
    ) {
      return false;
    }

    if (resolveBusyRef.current || isBusyCommand(currentResolve)) {
      ++resolveSequenceRef.current;
      resolveBusyRef.current = false;
      resolveAttemptRef.current = null;
    }

    const nextRevision = inputRevisionRef.current + 1;
    inputRevisionRef.current = nextRevision;
    setInputRevision(nextRevision);
    commitResolve(markCommandInputChanged(currentResolve, nextRevision));
    commitCreate(markCommandInputChanged(currentCreate, nextRevision));
    return true;
  }, [commitCreate, commitResolve]);

  const canCreate = canCreateInstallation(resolveState, inputRevision);

  return useMemo(
    () => ({
      inputRevision,
      resolveState,
      createState,
      canCreate,
      markInputChanged,
      resolve,
      retryResolve,
      create,
      retryCreate,
    }),
    [
      canCreate,
      create,
      createState,
      inputRevision,
      markInputChanged,
      resolve,
      resolveState,
      retryCreate,
      retryResolve,
    ],
  );
}

function isValidCreateDraft(draft: CreateInstallationDraft): boolean {
  return draft.overlayRevision.trim().length > 0 && draft.displayName.trim().length > 0;
}
