import type { AssetControlError } from "../../../api/assetControl/errors";
import type { IdempotentCommand } from "../../../api/assetControl/idempotency";
import type {
  InstallationResponse,
  StoredCompositionLock,
} from "../../../api/assetControl/types";

export type AssetCommandPhase =
  | "idle"
  | "running"
  | "reconciling"
  | "succeeded"
  | "conflict"
  | "forbidden"
  | "not_visible_or_missing"
  | "unknown_outcome"
  | "error";

export interface AssetCommandState<T> {
  readonly phase: AssetCommandPhase;
  readonly data: T | null;
  readonly error: AssetControlError | null;
  readonly command: Readonly<IdempotentCommand> | null;
  readonly inputRevision: number;
  readonly resultInputRevision: number | null;
  readonly stale: boolean;
  readonly requiresRefresh: boolean;
  readonly canRetrySameCommand: boolean;
}

export type ResolveCommandState = AssetCommandState<StoredCompositionLock>;
export type CreateInstallationCommandState = AssetCommandState<InstallationResponse>;

export function initialCommandState<T>(inputRevision = 0): AssetCommandState<T> {
  return {
    phase: "idle",
    data: null,
    error: null,
    command: null,
    inputRevision,
    resultInputRevision: null,
    stale: false,
    requiresRefresh: false,
    canRetrySameCommand: false,
  };
}

export function beginCommand<T>(
  previous: AssetCommandState<T>,
  command: Readonly<IdempotentCommand>,
  inputRevision: number,
): AssetCommandState<T> {
  return {
    ...previous,
    phase: "running",
    data: null,
    error: null,
    command,
    inputRevision,
    resultInputRevision: null,
    stale: false,
    requiresRefresh: false,
    canRetrySameCommand: false,
  };
}

export function reconcileCommand<T>(
  previous: AssetCommandState<T>,
  provisionalData: T,
): AssetCommandState<T> {
  return {
    ...previous,
    phase: "reconciling",
    data: provisionalData,
    error: null,
    stale: false,
    requiresRefresh: false,
    canRetrySameCommand: false,
  };
}

export function succeedCommand<T>(
  previous: AssetCommandState<T>,
  data: T,
  inputRevision: number,
): AssetCommandState<T> {
  return {
    ...previous,
    phase: "succeeded",
    data,
    error: null,
    inputRevision,
    resultInputRevision: inputRevision,
    stale: false,
    requiresRefresh: false,
    canRetrySameCommand: false,
  };
}

export function failCommand<T>(
  previous: AssetCommandState<T>,
  error: AssetControlError,
): AssetCommandState<T> {
  const canRetrySameCommand = error.outcomeUnknown && error.retryable;

  return {
    ...previous,
    phase: phaseForError(error),
    data: null,
    error,
    command: canRetrySameCommand ? previous.command : null,
    resultInputRevision: null,
    stale: false,
    requiresRefresh: error.requiresRefresh,
    canRetrySameCommand,
  };
}

export function markCommandInputChanged<T>(
  previous: AssetCommandState<T>,
  nextInputRevision: number,
): AssetCommandState<T> {
  const hasResult = previous.data !== null || previous.resultInputRevision !== null;
  const wasInFlight = previous.phase === "running" || previous.phase === "reconciling";

  return {
    ...previous,
    phase: wasInFlight ? "idle" : previous.phase,
    error: wasInFlight ? null : previous.error,
    command: null,
    inputRevision: nextInputRevision,
    stale: hasResult || wasInFlight,
    requiresRefresh: wasInFlight ? false : previous.requiresRefresh,
    canRetrySameCommand: false,
  };
}

export function isBusyCommand(state: AssetCommandState<unknown>): boolean {
  return state.phase === "running" || state.phase === "reconciling";
}

export function canCreateInstallation(
  resolveState: ResolveCommandState,
  currentInputRevision: number,
): boolean {
  return (
    resolveState.phase === "succeeded" &&
    resolveState.data !== null &&
    resolveState.resultInputRevision === currentInputRevision &&
    resolveState.inputRevision === currentInputRevision &&
    !resolveState.stale &&
    resolveState.error === null
  );
}

export function compositionLocksEqual(
  commandResponse: StoredCompositionLock,
  persistedResponse: StoredCompositionLock,
): boolean {
  return deepEqual(commandResponse, persistedResponse);
}

function phaseForError(error: AssetControlError): AssetCommandPhase {
  if (error.outcomeUnknown) return "unknown_outcome";
  if (error.isConflict) return "conflict";
  if (error.kind === "forbidden") return "forbidden";
  if (error.kind === "not_visible_or_missing") return "not_visible_or_missing";
  return "error";
}

function deepEqual(left: unknown, right: unknown): boolean {
  if (Object.is(left, right)) return true;
  if (typeof left !== typeof right || left === null || right === null) return false;

  if (Array.isArray(left) || Array.isArray(right)) {
    if (!Array.isArray(left) || !Array.isArray(right) || left.length !== right.length) {
      return false;
    }
    return left.every((value, index) => deepEqual(value, right[index]));
  }

  if (typeof left !== "object" || typeof right !== "object") return false;

  const leftRecord = left as Record<string, unknown>;
  const rightRecord = right as Record<string, unknown>;
  const leftKeys = Object.keys(leftRecord).sort();
  const rightKeys = Object.keys(rightRecord).sort();

  if (!deepEqual(leftKeys, rightKeys)) return false;
  return leftKeys.every((key) => deepEqual(leftRecord[key], rightRecord[key]));
}
