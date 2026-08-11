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
