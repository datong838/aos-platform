const IDEMPOTENCY_KEY_PREFIX = "integration-case-";
const MAX_IDEMPOTENCY_KEY_LENGTH = 160;

declare const idempotencyKeyBrand: unique symbol;

export type IntegrationCaseIdempotencyKey = string & {
  readonly [idempotencyKeyBrand]: true;
};

export interface IntegrationCaseCommand {
  readonly idempotencyKey: IntegrationCaseIdempotencyKey;
}

export function createIntegrationCaseCommand(): Readonly<IntegrationCaseCommand> {
  if (typeof globalThis.crypto?.randomUUID !== "function") {
    throw new Error("secure random UUID generation is unavailable");
  }
  const value = `${IDEMPOTENCY_KEY_PREFIX}${globalThis.crypto.randomUUID()}`;
  if (value.length < 1 || value.length > MAX_IDEMPOTENCY_KEY_LENGTH) {
    throw new Error("generated Idempotency-Key is outside the 1-160 character limit");
  }
  return Object.freeze({ idempotencyKey: value as IntegrationCaseIdempotencyKey });
}

export function integrationCaseIdempotencyKeyFor(
  command: IntegrationCaseCommand,
): IntegrationCaseIdempotencyKey {
  return command.idempotencyKey;
}
