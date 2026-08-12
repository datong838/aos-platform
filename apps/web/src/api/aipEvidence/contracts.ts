export const LINEAGE_ROOT_TYPES = [
  "task_run",
  "action",
  "eval_run",
  "publication",
  "research_job",
  "legacy_decision_lineage",
] as const;

export type LineageRootType = (typeof LINEAGE_ROOT_TYPES)[number];
export type EvidenceQuality = "measured" | "estimated" | "unknown";
export type TelemetrySpanKind = "internal" | "server" | "client" | "producer" | "consumer" | "model" | "tool";
export type TelemetrySpanStatus = "unset" | "ok" | "error";
export type UsageKind = "input_token" | "output_token" | "cached_token" | "cost" | "latency" | "tool_unit";

export type LineageEvent = {
  eventId: string;
  lineageId: string;
  rootType: LineageRootType;
  rootId: string;
  sequence: number;
  eventType: string;
  payloadHash: string;
  quality: EvidenceQuality;
  occurredAt: string;
  observedAt: string;
  sourceKind: string | null;
  sourceId: string | null;
  sourceHash: string | null;
  subject: Record<string, unknown> | null;
  artifact: Record<string, unknown> | null;
};

export type TelemetrySpan = {
  spanRecordId: string;
  provider: string;
  providerReceiptId: string;
  lineageId: string;
  traceId: string;
  spanId: string;
  parentSpanId: string | null;
  name: string;
  kind: TelemetrySpanKind;
  status: TelemetrySpanStatus;
  producerStartedAt: string;
  producerEndedAt: string | null;
  observedAt: string;
  attributesHash: string;
  sourceHash: string;
  quality: EvidenceQuality;
  ingestedAt: string;
};

export type UsageReceipt = {
  receiptId: string;
  provider: string;
  providerReceiptId: string;
  lineageId: string;
  usageKind: UsageKind;
  quantity: number | null;
  unit: string;
  currency: string | null;
  quality: EvidenceQuality;
  sourceHash: string;
  observedAt: string;
};

function record(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new TypeError(`${label} 响应格式无效`);
  return value as Record<string, unknown>;
}

function stringValue(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new TypeError(`${label} 缺失`);
  return value;
}

function nullableString(value: unknown, label: string): string | null {
  return value === null || value === undefined ? null : stringValue(value, label);
}

function hash(value: unknown, label: string): string {
  const result = stringValue(value, label).toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(result)) throw new TypeError(`${label} 不是 sha256`);
  return result;
}

function positiveInt(value: unknown, label: string): number {
  if (!Number.isSafeInteger(value) || (value as number) < 1) throw new TypeError(`${label} 无效`);
  return value as number;
}

function enumValue<T extends string>(value: unknown, allowed: readonly T[], label: string): T {
  const result = stringValue(value, label);
  if (!allowed.includes(result as T)) throw new TypeError(`${label} 未知`);
  return result as T;
}

function nullableNumber(value: unknown, label: string): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) throw new TypeError(`${label} 无效`);
  return value;
}

function optionalRecord(value: unknown, label: string): Record<string, unknown> | null {
  return value === null || value === undefined ? null : record(value, label);
}

export function parseLineageEvents(value: unknown): LineageEvent[] {
  if (!Array.isArray(value)) throw new TypeError("LineageEvent 列表响应格式无效");
  const events = value.map((raw, index): LineageEvent => {
    const item = record(raw, `LineageEvent[${index}]`);
    const rootType = stringValue(item.rootType, `LineageEvent[${index}].rootType`);
    if (!LINEAGE_ROOT_TYPES.includes(rootType as LineageRootType)) throw new TypeError(`LineageEvent[${index}].rootType 未知`);
    const quality = stringValue(item.quality, `LineageEvent[${index}].quality`);
    if (!["measured", "estimated", "unknown"].includes(quality)) throw new TypeError(`LineageEvent[${index}].quality 未知`);
    const sourceKind = nullableString(item.sourceKind, `LineageEvent[${index}].sourceKind`);
    const sourceId = nullableString(item.sourceId, `LineageEvent[${index}].sourceId`);
    const sourceHash = item.sourceHash === null || item.sourceHash === undefined ? null : hash(item.sourceHash, `LineageEvent[${index}].sourceHash`);
    if ([sourceKind, sourceId, sourceHash].filter((entry) => entry !== null).length % 3 !== 0) throw new TypeError("LineageEvent source tuple 不完整");
    return {
      eventId: stringValue(item.eventId, `LineageEvent[${index}].eventId`),
      lineageId: stringValue(item.lineageId, `LineageEvent[${index}].lineageId`),
      rootType: rootType as LineageRootType,
      rootId: stringValue(item.rootId, `LineageEvent[${index}].rootId`),
      sequence: positiveInt(item.sequence, `LineageEvent[${index}].sequence`),
      eventType: stringValue(item.eventType, `LineageEvent[${index}].eventType`),
      payloadHash: hash(item.payloadHash, `LineageEvent[${index}].payloadHash`),
      quality: quality as EvidenceQuality,
      occurredAt: stringValue(item.occurredAt, `LineageEvent[${index}].occurredAt`),
      observedAt: stringValue(item.observedAt, `LineageEvent[${index}].observedAt`),
      sourceKind,
      sourceId,
      sourceHash,
      subject: optionalRecord(item.subject, `LineageEvent[${index}].subject`),
      artifact: optionalRecord(item.artifact, `LineageEvent[${index}].artifact`),
    };
  });
  if (new Set(events.map((event) => event.eventId)).size !== events.length) throw new TypeError("LineageEvent 含重复 eventId");
  for (let index = 0; index < events.length; index += 1) {
    const event = events[index];
    if (event.sequence !== index + 1) throw new TypeError("LineageEvent sequence 不连续");
    if (index > 0 && (event.lineageId !== events[0].lineageId || event.rootType !== events[0].rootType || event.rootId !== events[0].rootId)) {
      throw new TypeError("LineageEvent root 引用不一致");
    }
  }
  return events;
}

export function parseTelemetrySpans(value: unknown, expectedLineageId?: string): TelemetrySpan[] {
  if (!Array.isArray(value)) throw new TypeError("TelemetrySpan 列表响应格式无效");
  const spans = value.map((raw, index): TelemetrySpan => {
    const label = `TelemetrySpan[${index}]`;
    const item = record(raw, label);
    const lineageId = stringValue(item.lineageId, `${label}.lineageId`);
    if (expectedLineageId && lineageId !== expectedLineageId) throw new TypeError(`${label}.lineageId 不匹配`);
    return {
      spanRecordId: stringValue(item.spanRecordId, `${label}.spanRecordId`),
      provider: stringValue(item.provider, `${label}.provider`),
      providerReceiptId: stringValue(item.providerReceiptId, `${label}.providerReceiptId`),
      lineageId,
      traceId: stringValue(item.traceId, `${label}.traceId`),
      spanId: stringValue(item.spanId, `${label}.spanId`),
      parentSpanId: nullableString(item.parentSpanId, `${label}.parentSpanId`),
      name: stringValue(item.name, `${label}.name`),
      kind: enumValue(item.kind, ["internal", "server", "client", "producer", "consumer", "model", "tool"] as const, `${label}.kind`),
      status: enumValue(item.status, ["unset", "ok", "error"] as const, `${label}.status`),
      producerStartedAt: stringValue(item.producerStartedAt, `${label}.producerStartedAt`),
      producerEndedAt: nullableString(item.producerEndedAt, `${label}.producerEndedAt`),
      observedAt: stringValue(item.observedAt, `${label}.observedAt`),
      attributesHash: hash(item.attributesHash, `${label}.attributesHash`),
      sourceHash: hash(item.sourceHash, `${label}.sourceHash`),
      quality: enumValue(item.quality, ["measured", "estimated", "unknown"] as const, `${label}.quality`),
      ingestedAt: stringValue(item.ingestedAt, `${label}.ingestedAt`),
    };
  });
  if (new Set(spans.map((span) => span.spanRecordId)).size !== spans.length) throw new TypeError("TelemetrySpan 含重复 spanRecordId");
  if (new Set(spans.map((span) => `${span.provider}:${span.providerReceiptId}`)).size !== spans.length) throw new TypeError("TelemetrySpan 含重复 provider receipt");
  return spans;
}

export function parseUsageReceipts(value: unknown, expectedLineageId?: string): UsageReceipt[] {
  if (!Array.isArray(value)) throw new TypeError("UsageReceipt 列表响应格式无效");
  const receipts = value.map((raw, index): UsageReceipt => {
    const label = `UsageReceipt[${index}]`;
    const item = record(raw, label);
    const lineageId = stringValue(item.lineageId, `${label}.lineageId`);
    if (expectedLineageId && lineageId !== expectedLineageId) throw new TypeError(`${label}.lineageId 不匹配`);
    const usageKind = enumValue(item.usageKind, ["input_token", "output_token", "cached_token", "cost", "latency", "tool_unit"] as const, `${label}.usageKind`);
    const quality = enumValue(item.quality, ["measured", "estimated", "unknown"] as const, `${label}.quality`);
    const quantity = nullableNumber(item.quantity, `${label}.quantity`);
    const currency = nullableString(item.currency, `${label}.currency`);
    if ((quality === "unknown") !== (quantity === null)) throw new TypeError(`${label} quantity/quality 不一致`);
    if ((usageKind === "cost") !== (currency !== null)) throw new TypeError(`${label} currency/usageKind 不一致`);
    if (currency && !/^[A-Z]{3}$/.test(currency)) throw new TypeError(`${label}.currency 无效`);
    return {
      receiptId: stringValue(item.receiptId, `${label}.receiptId`),
      provider: stringValue(item.provider, `${label}.provider`),
      providerReceiptId: stringValue(item.providerReceiptId, `${label}.providerReceiptId`),
      lineageId,
      usageKind,
      quantity,
      unit: stringValue(item.unit, `${label}.unit`),
      currency,
      quality,
      sourceHash: hash(item.sourceHash, `${label}.sourceHash`),
      observedAt: stringValue(item.observedAt, `${label}.observedAt`),
    };
  });
  if (new Set(receipts.map((receipt) => receipt.receiptId)).size !== receipts.length) throw new TypeError("UsageReceipt 含重复 receiptId");
  if (new Set(receipts.map((receipt) => `${receipt.provider}:${receipt.providerReceiptId}`)).size !== receipts.length) throw new TypeError("UsageReceipt 含重复 provider receipt");
  return receipts;
}
