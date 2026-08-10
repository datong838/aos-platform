import { parseAipErrorBody, type AipErrorBody } from "./contracts";

export class AipClientError extends Error {
  readonly status: number;
  readonly body: AipErrorBody;
  readonly operationId: string;
  readonly outcomeUnknown: boolean;

  constructor(status: number, body: AipErrorBody, operationId: string, options?: { cause?: unknown }) {
    super(body.message);
    this.name = "AipClientError";
    this.status = status;
    this.body = body;
    this.operationId = operationId;
    this.outcomeUnknown = body.code === "AIP_OUTCOME_UNKNOWN" || (status === 0 && operationId.startsWith("mutate:"));
    if (options?.cause !== undefined) (this as Error & { cause?: unknown }).cause = options.cause;
  }
}

export function aipClientError(
  value: unknown,
  options: { status: number; operationId: string; fallbackMessage: string },
): AipClientError {
  if (value instanceof AipClientError) return value;
  const parsed = parseAipErrorBody(value);
  const body = parsed ?? {
    code: options.status === 0 ? "AIP_DEPENDENCY_UNAVAILABLE" : "INVALID_ERROR_RESPONSE",
    message: options.fallbackMessage,
    details: null,
    traceId: "",
  };
  return new AipClientError(options.status, body, options.operationId, { cause: value });
}

