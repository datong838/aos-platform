import { aipClient, type AipClient } from "../aip/client";
import {
  parseActionDraftBundle,
  parseActionDraftRevisionSnapshot,
  parseActionExecution,
  parseActionProposalList,
  parseActionTimeline,
  type ActionDraftBundle,
  type ActionExecutionView,
  type ActionProposalList,
  type ActionProposalTimeline,
} from "./contracts";

export type ReplacementProposalInput = {
  purpose: string;
  diff: Record<string, unknown>;
  expiresAt: string;
};

function idempotencyKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

export class AipActionsSdk {
  constructor(private readonly client: AipClient = aipClient) {}

  async list(limit = 100): Promise<ActionProposalList> {
    if (!Number.isSafeInteger(limit) || limit < 1 || limit > 500) throw new TypeError("Action Proposal limit 必须在 1 到 500");
    return parseActionProposalList(await this.client.request("listActionProposals", { params: { limit: String(limit) } }));
  }

  async get(proposalId: string): Promise<ActionDraftBundle> {
    return parseActionDraftBundle(await this.client.request("getActionProposal", { params: { proposal_id: proposalId } }));
  }

  async createReplacementProposal(bundle: ActionDraftBundle, input: ReplacementProposalInput): Promise<ActionDraftBundle> {
    const purpose = input.purpose.trim();
    if (!purpose) throw new TypeError("修改说明不能为空");
    const expiry = new Date(input.expiresAt);
    if (!Number.isFinite(expiry.getTime()) || expiry.getTime() <= Date.now()) throw new TypeError("新提案有效期必须晚于当前时间");
    const snapshot = parseActionDraftRevisionSnapshot(await this.client.request("createActionDraft", {
      headers: { "Idempotency-Key": idempotencyKey("action-draft-create") },
      body: {
        actionTypeId: bundle.proposal.actionType.actionTypeId,
        taskId: bundle.proposal.taskId,
        runId: bundle.proposal.runId,
        objectRef: bundle.proposal.objectRef,
        purpose,
        riskHint: bundle.proposal.clientRiskHint || bundle.proposal.riskLevel,
        payload: bundle.proposal.payload,
        diff: input.diff,
        evidenceRefs: bundle.proposal.evidenceRefs || bundle.draft.evidenceRefs,
        impactPreviewRef: bundle.proposal.impactPreviewRef,
        expiresAt: expiry.toISOString(),
      },
    }));
    if (snapshot.lifecycle !== "draft") throw new TypeError("服务端未返回可提交草稿");
    return parseActionDraftBundle(await this.client.request("submitActionDraft", {
      params: { draft_id: snapshot.draftId },
      headers: { "Idempotency-Key": idempotencyKey("action-draft-submit") },
      body: { expectedRevision: snapshot.revision, expectedContentHash: snapshot.contentHash },
    }));
  }

  async timeline(proposalId: string): Promise<ActionProposalTimeline> {
    return parseActionTimeline(await this.client.request("getActionProposalTimeline", { params: { proposal_id: proposalId } }));
  }

  async execution(proposalId: string): Promise<ActionExecutionView> {
    return parseActionExecution(await this.client.request("getActionExecution", { params: { proposal_id: proposalId } }));
  }

  async decide(bundle: ActionDraftBundle, decision: "approved" | "rejected", reason: string): Promise<ActionDraftBundle> {
    return parseActionDraftBundle(await this.client.request("decideActionProposal", {
      params: { proposal_id: bundle.proposal.id }, headers: { "Idempotency-Key": idempotencyKey(`action-${decision}`) },
      body: {
        expectedProposalVersion: bundle.proposal.version,
        expectedProposalHash: bundle.proposal.proposalHash,
        decision,
        reason,
      },
    }));
  }

  async withdraw(bundle: ActionDraftBundle, reason: string): Promise<ActionDraftBundle> {
    const cleaned = reason.trim();
    if (!cleaned) throw new TypeError("撤回原因不能为空");
    return parseActionDraftBundle(await this.client.request("withdrawActionProposal", {
      params: { proposal_id: bundle.proposal.id },
      headers: { "Idempotency-Key": idempotencyKey("action-withdraw") },
      body: {
        expectedProposalVersion: bundle.proposal.version,
        expectedProposalHash: bundle.proposal.proposalHash,
        reason: cleaned,
      },
    }));
  }

  async acquireLease(bundle: ActionDraftBundle): Promise<ActionExecutionView> {
    return parseActionExecution(await this.client.request("acquireActionLease", {
      params: { proposal_id: bundle.proposal.id }, headers: { "Idempotency-Key": idempotencyKey("action-lease") },
      body: { expectedProposalVersion: bundle.proposal.version, expectedProposalHash: bundle.proposal.proposalHash },
    }));
  }

  async execute(view: ActionExecutionView): Promise<ActionExecutionView> {
    if (!view.lease) throw new TypeError("执行前缺少 ExecutionLease");
    return parseActionExecution(await this.client.request("executeActionLease", {
      params: { lease_id: view.lease.id }, body: { expectedProposalHash: view.proposal.proposalHash },
    }));
  }

  async reconcile(receiptId: string, reason: string): Promise<ActionExecutionView> {
    return parseActionExecution(await this.client.request("reconcileActionReceipt", {
      params: { receipt_id: receiptId }, body: { reason },
    }));
  }

  async createCompensation(bundle: ActionDraftBundle, receiptId: string, purpose: string): Promise<ActionDraftBundle> {
    const cleaned = purpose.trim();
    if (!cleaned) throw new TypeError("补偿目的不能为空");
    return parseActionDraftBundle(await this.client.request("createActionCompensation", {
      params: { proposal_id: bundle.proposal.id },
      headers: { "Idempotency-Key": idempotencyKey("action-compensation") },
      body: { receiptId, purpose: cleaned },
    }));
  }
}

export const aipActionsSdk = new AipActionsSdk();
