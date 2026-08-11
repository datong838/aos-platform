import { aipClient, type AipClient } from "../aip/client";
import {
  parseActionDraftBundle,
  parseActionExecution,
  parseActionProposalList,
  parseActionTimeline,
  type ActionDraftBundle,
  type ActionExecutionView,
  type ActionProposalList,
  type ActionProposalTimeline,
} from "./contracts";

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
}

export const aipActionsSdk = new AipActionsSdk();
