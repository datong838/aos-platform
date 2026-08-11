export const ACTION_PROPOSAL_STATUSES = [
  "proposed", "drafted", "approved", "rejected", "expired", "leased", "executing",
  "applied", "failed", "unknown", "reconciled", "compensated",
] as const;
export type ActionProposalStatus = (typeof ACTION_PROPOSAL_STATUSES)[number];
export type ActionRiskLevel = "R0" | "R1" | "R2" | "R3" | "R4";
export type ReceiptStatus = "accepted" | "applied" | "failed" | "unknown" | "reconciled";

export type ActorRef = { actorType: string; actorId: string };
export type ResourceRef = { resourceType: string; resourceId: string; revision: string | null; authority: string };
export type ActionTypeRevisionRef = { actionTypeId: string; revisionHash: string; objectType: string };

export type ActionProposal = {
  id: string;
  actionType: ActionTypeRevisionRef;
  taskId: string | null;
  runId: string | null;
  objectRef: ResourceRef | null;
  purpose: string;
  riskLevel: ActionRiskLevel;
  payload: Record<string, unknown>;
  proposalHash: string;
  status: ActionProposalStatus;
  expiresAt: string;
  version: number;
  createdBy: ActorRef;
  createdAt: string;
  updatedAt: string;
};

export type ActionDraft = {
  id: string;
  proposalId: string;
  proposalVersion: number;
  proposalHash: string;
  diff: Record<string, unknown>;
  evidenceRefs: ResourceRef[];
  status: string;
  createdAt: string;
};

export type ApprovalEvent = {
  id: string;
  proposalId: string;
  proposalVersion: number;
  proposalHash: string;
  decision: "approved" | "rejected";
  actor: ActorRef;
  reason: string;
  expiresAt: string | null;
  createdAt: string;
};

export type ActionDraftBundle = { proposal: ActionProposal; draft: ActionDraft; approvals: ApprovalEvent[] };
export type ActionProposalList = { items: ActionDraftBundle[]; count: number };
export type ActionTimelineEvent = {
  id: string; type: string; actorId: string; proposalVersion: number;
  proposalHash: string; payload: Record<string, unknown>; createdAt: string;
};
export type ActionProposalTimeline = { bundle: ActionDraftBundle; events: ActionTimelineEvent[] };

export type ExecutionLease = {
  id: string; proposalId: string; proposalHash: string; attempt: number;
  expiresAt: string; createdAt: string;
};
export type ActionReceipt = {
  id: string; proposalId: string; leaseId: string; status: ReceiptStatus;
  providerRequestId: string | null; evidenceRefs: ResourceRef[]; createdAt: string;
  receiptKind: string; supersedesReceiptId: string | null; requestFingerprint: string;
  payload: Record<string, unknown>;
};
export type ActionExecutionView = { proposal: ActionProposal; lease: ExecutionLease | null; receipts: ActionReceipt[] };

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
function positiveInt(value: unknown, label: string): number {
  if (!Number.isSafeInteger(value) || (value as number) < 1) throw new TypeError(`${label} 无效`);
  return value as number;
}
function objectValue(value: unknown, label: string): Record<string, unknown> {
  return record(value ?? {}, label);
}
function hash(value: unknown, label: string): string {
  const result = stringValue(value, label).toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(result)) throw new TypeError(`${label} 不是 sha256`);
  return result;
}
function actor(value: unknown, label: string): ActorRef {
  const item = record(value, label);
  return { actorType: stringValue(item.actorType, `${label}.actorType`), actorId: stringValue(item.actorId, `${label}.actorId`) };
}
function resource(value: unknown, label: string): ResourceRef {
  const item = record(value, label);
  return {
    resourceType: stringValue(item.resourceType, `${label}.resourceType`),
    resourceId: stringValue(item.resourceId, `${label}.resourceId`),
    revision: nullableString(item.revision, `${label}.revision`),
    authority: stringValue(item.authority, `${label}.authority`),
  };
}
function resources(value: unknown, label: string): ResourceRef[] {
  if (!Array.isArray(value)) throw new TypeError(`${label} 必须是数组`);
  return value.map((item, index) => resource(item, `${label}[${index}]`));
}

export function parseActionProposal(value: unknown): ActionProposal {
  const item = record(value, "ActionProposal");
  const action = record(item.actionType, "ActionProposal.actionType");
  const status = stringValue(item.status, "ActionProposal.status");
  if (!ACTION_PROPOSAL_STATUSES.includes(status as ActionProposalStatus)) throw new TypeError(`ActionProposal.status 未知：${status}`);
  const risk = stringValue(item.riskLevel, "ActionProposal.riskLevel");
  if (!/R[0-4]/.test(risk)) throw new TypeError("ActionProposal.riskLevel 未知");
  return {
    id: stringValue(item.id, "ActionProposal.id"),
    actionType: {
      actionTypeId: stringValue(action.actionTypeId, "ActionProposal.actionType.actionTypeId"),
      revisionHash: hash(action.revisionHash, "ActionProposal.actionType.revisionHash"),
      objectType: stringValue(action.objectType, "ActionProposal.actionType.objectType"),
    },
    taskId: nullableString(item.taskId, "ActionProposal.taskId"),
    runId: nullableString(item.runId, "ActionProposal.runId"),
    objectRef: item.objectRef === null || item.objectRef === undefined ? null : resource(item.objectRef, "ActionProposal.objectRef"),
    purpose: stringValue(item.purpose, "ActionProposal.purpose"),
    riskLevel: risk as ActionRiskLevel,
    payload: objectValue(item.payload, "ActionProposal.payload"),
    proposalHash: hash(item.proposalHash, "ActionProposal.proposalHash"),
    status: status as ActionProposalStatus,
    expiresAt: stringValue(item.expiresAt, "ActionProposal.expiresAt"),
    version: positiveInt(item.version, "ActionProposal.version"),
    createdBy: actor(item.createdBy, "ActionProposal.createdBy"),
    createdAt: stringValue(item.createdAt, "ActionProposal.createdAt"),
    updatedAt: stringValue(item.updatedAt, "ActionProposal.updatedAt"),
  };
}

export function parseActionDraftBundle(value: unknown): ActionDraftBundle {
  const item = record(value, "ActionDraftBundle");
  const proposal = parseActionProposal(item.proposal);
  const rawDraft = record(item.draft, "ActionDraftBundle.draft");
  const draft: ActionDraft = {
    id: stringValue(rawDraft.id, "Draft.id"), proposalId: stringValue(rawDraft.proposalId, "Draft.proposalId"),
    proposalVersion: positiveInt(rawDraft.proposalVersion, "Draft.proposalVersion"),
    proposalHash: hash(rawDraft.proposalHash, "Draft.proposalHash"), diff: objectValue(rawDraft.diff, "Draft.diff"),
    evidenceRefs: resources(rawDraft.evidenceRefs ?? [], "Draft.evidenceRefs"),
    status: stringValue(rawDraft.status, "Draft.status"), createdAt: stringValue(rawDraft.createdAt, "Draft.createdAt"),
  };
  if (draft.proposalId !== proposal.id || draft.proposalHash !== proposal.proposalHash) throw new TypeError("Draft 与 Proposal 引用不一致");
  if (!Array.isArray(item.approvals)) throw new TypeError("ActionDraftBundle.approvals 必须是数组");
  const approvals = item.approvals.map((raw, index): ApprovalEvent => {
    const approval = record(raw, `Approval[${index}]`);
    const decision = stringValue(approval.decision, `Approval[${index}].decision`);
    if (decision !== "approved" && decision !== "rejected") throw new TypeError("Approval.decision 未知");
    const result = {
      id: stringValue(approval.id, "Approval.id"), proposalId: stringValue(approval.proposalId, "Approval.proposalId"),
      proposalVersion: positiveInt(approval.proposalVersion, "Approval.proposalVersion"),
      proposalHash: hash(approval.proposalHash, "Approval.proposalHash"), decision: decision as ApprovalEvent["decision"],
      actor: actor(approval.actor, "Approval.actor"), reason: typeof approval.reason === "string" ? approval.reason : "",
      expiresAt: nullableString(approval.expiresAt, "Approval.expiresAt"), createdAt: stringValue(approval.createdAt, "Approval.createdAt"),
    };
    if (result.proposalId !== proposal.id || result.proposalHash !== proposal.proposalHash) throw new TypeError("Approval 与 Proposal 引用不一致");
    return result;
  });
  return { proposal, draft, approvals };
}

export function parseActionProposalList(value: unknown): ActionProposalList {
  const item = record(value, "ActionProposalList");
  if (!Array.isArray(item.items) || typeof item.count !== "number") throw new TypeError("ActionProposalList 响应格式无效");
  const items = item.items.map(parseActionDraftBundle);
  if (items.length !== item.count) throw new TypeError("ActionProposalList count 不一致");
  if (new Set(items.map((entry) => entry.proposal.id)).size !== items.length) throw new TypeError("ActionProposalList 含重复 Proposal");
  return { items, count: item.count };
}

export function parseActionExecution(value: unknown): ActionExecutionView {
  const item = record(value, "ActionExecutionView");
  const proposal = parseActionProposal(item.proposal);
  let lease: ExecutionLease | null = null;
  if (item.lease !== null && item.lease !== undefined) {
    const raw = record(item.lease, "ExecutionLease");
    lease = {
      id: stringValue(raw.id, "ExecutionLease.id"), proposalId: stringValue(raw.proposalId, "ExecutionLease.proposalId"),
      proposalHash: hash(raw.proposalHash, "ExecutionLease.proposalHash"), attempt: positiveInt(raw.attempt, "ExecutionLease.attempt"),
      expiresAt: stringValue(raw.expiresAt, "ExecutionLease.expiresAt"), createdAt: stringValue(raw.createdAt, "ExecutionLease.createdAt"),
    };
    if (lease.proposalId !== proposal.id || lease.proposalHash !== proposal.proposalHash) throw new TypeError("Lease 与 Proposal 引用不一致");
  }
  if (!Array.isArray(item.receipts)) throw new TypeError("ActionExecutionView.receipts 必须是数组");
  const receipts = item.receipts.map((raw, index): ActionReceipt => {
    const receipt = record(raw, `Receipt[${index}]`);
    const status = stringValue(receipt.status, "Receipt.status") as ReceiptStatus;
    if (!["accepted", "applied", "failed", "unknown", "reconciled"].includes(status)) throw new TypeError("Receipt.status 未知");
    return {
      id: stringValue(receipt.id, "Receipt.id"), proposalId: stringValue(receipt.proposalId, "Receipt.proposalId"),
      leaseId: stringValue(receipt.leaseId, "Receipt.leaseId"), status,
      providerRequestId: nullableString(receipt.providerRequestId, "Receipt.providerRequestId"),
      evidenceRefs: resources(receipt.evidenceRefs ?? [], "Receipt.evidenceRefs"), createdAt: stringValue(receipt.createdAt, "Receipt.createdAt"),
      receiptKind: stringValue(receipt.receiptKind, "Receipt.receiptKind"),
      supersedesReceiptId: nullableString(receipt.supersedesReceiptId, "Receipt.supersedesReceiptId"),
      requestFingerprint: hash(receipt.requestFingerprint, "Receipt.requestFingerprint"), payload: objectValue(receipt.payload, "Receipt.payload"),
    };
  });
  if (new Set(receipts.map((receipt) => receipt.id)).size !== receipts.length) throw new TypeError("Receipt 链含重复 id");
  if (receipts.some((receipt) => receipt.proposalId !== proposal.id || (lease && receipt.leaseId !== lease.id))) throw new TypeError("Receipt 与执行资源引用不一致");
  return { proposal, lease, receipts };
}

export function parseActionTimeline(value: unknown): ActionProposalTimeline {
  const item = record(value, "ActionTimeline");
  const bundle = parseActionDraftBundle(item.bundle);
  if (!Array.isArray(item.events)) throw new TypeError("ActionTimeline.events 必须是数组");
  const events = item.events.map((raw, index): ActionTimelineEvent => {
    const event = record(raw, `ActionTimeline.events[${index}]`);
    return {
      id: stringValue(event.eventId ?? event.event_id, "ActionEvent.id"),
      type: stringValue(event.eventType ?? event.event_type, "ActionEvent.type"),
      actorId: stringValue(event.actorId ?? event.actor_id, "ActionEvent.actorId"),
      proposalVersion: positiveInt(event.proposalVersion ?? event.proposal_version, "ActionEvent.proposalVersion"),
      proposalHash: hash(event.proposalHash ?? event.proposal_hash, "ActionEvent.proposalHash"),
      payload: objectValue(event.payload, "ActionEvent.payload"),
      createdAt: stringValue(event.createdAt ?? event.created_at, "ActionEvent.createdAt"),
    };
  });
  if (events.some((event) => event.proposalHash !== bundle.proposal.proposalHash)) throw new TypeError("Timeline 与 Proposal hash 不一致");
  return { bundle, events };
}
