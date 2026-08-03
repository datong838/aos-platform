const IDEMPOTENCY_KEY_PREFIX = "asset-control-";
const MAX_IDEMPOTENCY_KEY_LENGTH = 160;

declare const idempotencyKeyBrand: unique symbol;

/** A validated, command-scoped value for the Idempotency-Key header. */
export type IdempotencyKey = string & {
  readonly [idempotencyKeyBrand]: true;
};

/**
 * In-memory command identity. Keep this object for network retries of one
 * command; create a new object when the user starts a new command.
 */
export interface IdempotentCommand {
  readonly idempotencyKey: IdempotencyKey;
}

function generateIdempotencyKey(): IdempotencyKey {
  if (typeof globalThis.crypto?.randomUUID !== "function") {
    throw new Error("secure random UUID generation is unavailable");
  }

  const value = `${IDEMPOTENCY_KEY_PREFIX}${globalThis.crypto.randomUUID()}`;
  if (value.length < 1 || value.length > MAX_IDEMPOTENCY_KEY_LENGTH) {
    throw new Error("generated Idempotency-Key is outside the 1-160 character limit");
  }
  return value as IdempotencyKey;
}

/** Create one identity for one user command. This value is never persisted. */
export function createIdempotentCommand(): Readonly<IdempotentCommand> {
  return Object.freeze({ idempotencyKey: generateIdempotencyKey() });
}

/** Return the stable key used for the initial attempt and every retry. */
export function idempotencyKeyFor(command: IdempotentCommand): IdempotencyKey {
  return command.idempotencyKey;
}
