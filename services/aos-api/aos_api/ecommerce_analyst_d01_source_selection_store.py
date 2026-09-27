"""Transaction-bound D01 selection proposal Owner; no commit or runtime grant."""
from __future__ import annotations

from datetime import datetime

from psycopg.types.json import Jsonb

from aos_api.aip_task_store import AipTaskStore
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.ecommerce_analyst_d01_source_selection import D01SourceSelectionProposal
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope


class D01SourceSelectionStore:
    @staticmethod
    def _proposal_row(transaction: HostTransaction, scope: TenantScope,
                      selection_id: str) -> tuple[D01SourceSelectionProposal, dict]:
        row = transaction.execute(
            """SELECT selection_id,payload,content_hash,request_hash,proposal_key
               FROM public.ecommerce_d01_source_proposal
               WHERE org_id=%s AND project_id=%s AND selection_id=%s""",
            (*scope.key, selection_id),
        ).fetchone()
        if row is None:
            raise ValueError('D01 proposal authority unavailable')
        proposal = D01SourceSelectionProposal.model_validate(row['payload'])
        if (proposal.selection_id != selection_id
                or canonical_hash(row['payload']) != row['content_hash']
                or canonical_hash({'key': row['proposal_key'],
                                   'proposal': row['payload']}) != row['request_hash']):
            raise ValueError('D01 proposal independent hash readback differs')
        return proposal, row

    def propose(self, transaction: HostTransaction, scope: TenantScope,
                proposal: D01SourceSelectionProposal, *, key: str, actor: str) -> dict:
        if (type(transaction) is not HostTransaction or type(scope) is not TenantScope
                or type(proposal) is not D01SourceSelectionProposal
                or (proposal.tenant.org_id, proposal.tenant.project_id) != scope.key
                or type(key) is not str or not 1 <= len(key) <= 160
                or key != key.strip() or type(actor) is not str
                or actor != proposal.proposed_by):
            raise ValueError('exact scoped D01 selection proposal required')
        proposal = D01SourceSelectionProposal.model_validate(
            proposal.model_dump(mode='python'))
        timeline = AipTaskStore(
            TransactionBoundConnectFactory(transaction, scope)
        ).timeline(scope, proposal.task_run_ref.resource_id)
        run, task, plan = timeline.run, timeline.task, timeline.plan
        schema = plan.steps[0].input_schema_ref if plan.steps else None
        if (run.id != proposal.task_run_ref.resource_id
                or str(run.version) != proposal.task_run_ref.revision
                or run.plan_revision_id != proposal.plan_ref.resource_id
                or run.task_id != task.id
                or getattr(run.status, 'value', run.status) != 'running'
                or plan.id != proposal.plan_ref.resource_id
                or str(plan.revision) != proposal.plan_ref.revision
                or plan.task_id != task.id
                or plan.content_hash != proposal.plan_content_hash
                or getattr(plan.approval_status, 'value', plan.approval_status) != 'approved'
                or not plan.steps or plan.steps[0].step_key != 'portrait'
                or schema is None or plan.steps[0].input_refs != [schema]
                or schema.revision is None or not schema.authority
                or task.selection_ref is None
                or task.selection_ref.resource_type != 'SourceSelectionRevision'
                or task.selection_ref.resource_id != proposal.source_selection_ref.resource_id
                or task.selection_ref.revision != str(proposal.source_selection_ref.revision)
                or task.selection_ref.authority != 'postgresql'):
            raise ValueError('original approved D01 proposal lineage unavailable')
        payload = proposal.model_dump(mode='json', by_alias=True)
        request_hash = canonical_hash({'key': key, 'proposal': payload})
        content_hash = canonical_hash(payload)
        transaction.execute("SELECT set_config('aos.subject',%s,true)", (actor,))
        receipt = transaction.execute(
            """SELECT public.ecommerce_d01_source_propose_a0v_107(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) AS receipt""",
            (proposal.selection_id, run.id, plan.id, proposal.plan_content_hash,
             Jsonb(proposal.source_selection_ref.model_dump(mode='json', by_alias=True)),
             Jsonb(proposal.packet.model_dump(mode='json', by_alias=True)),
             Jsonb(payload), key, request_hash, content_hash, actor, proposal.proposed_at),
        ).fetchone()['receipt']
        row = transaction.execute(
            """SELECT payload,content_hash,request_hash,proposal_key
               FROM public.ecommerce_d01_source_proposal
               WHERE org_id=%s AND project_id=%s AND selection_id=%s""",
            (*scope.key, proposal.selection_id),
        ).fetchone()
        if (row is None or row['payload'] != payload
                or row['content_hash'] != content_hash
                or row['request_hash'] != request_hash or row['proposal_key'] != key
                or receipt != {'resourceType': 'D01SourceSelectionProposal',
                               'resourceId': proposal.selection_id, 'revision': 1,
                               'contentHash': 'sha256:' + content_hash,
                               'receiptId': 'd01-proposal:' + proposal.selection_id}):
            raise ValueError('D01 proposal independent readback differs')
        return receipt

    def approve(self, transaction: HostTransaction, scope: TenantScope,
                selection_id: str, *, key: str, checker: str,
                approved_at: datetime) -> dict:
        if (type(transaction) is not HostTransaction or type(scope) is not TenantScope
                or type(selection_id) is not str or not selection_id
                or type(key) is not str or not 1 <= len(key) <= 160
                or key != key.strip() or type(checker) is not str
                or not checker or checker != checker.strip()
                or type(approved_at) is not datetime
                or approved_at.utcoffset() is None):
            raise ValueError('exact D01 checker approval required')
        proposal, row = self._proposal_row(transaction, scope, selection_id)
        if checker == proposal.proposed_by:
            raise PermissionError('D01 maker cannot approve own packet')
        request_hash = canonical_hash({
            'selectionId': selection_id, 'key': key, 'checker': checker,
            'proposalHash': row['content_hash'], 'approvedAt': approved_at.isoformat(),
        })
        transaction.execute("SELECT set_config('aos.subject',%s,true)", (checker,))
        receipt = transaction.execute(
            """SELECT public.ecommerce_d01_source_approve_a0v_107(
                %s,%s,%s,%s,%s,%s) AS receipt""",
            (selection_id, key, request_hash, row['content_hash'], checker, approved_at),
        ).fetchone()['receipt']
        stored = transaction.execute(
            """SELECT approval_key,request_hash,proposal_hash,checker,approved_at,receipt_ref
               FROM public.ecommerce_d01_source_approval
               WHERE org_id=%s AND project_id=%s AND selection_id=%s""",
            (*scope.key, selection_id),
        ).fetchone()
        if (stored is None or stored['approval_key'] != key
                or stored['request_hash'] != request_hash
                or stored['proposal_hash'] != row['content_hash']
                or stored['checker'] != checker or stored['approved_at'] != approved_at
                or stored['receipt_ref'] != receipt
                or receipt.get('resourceType') != 'D01SourceSelectionApproval'
                or receipt.get('resourceId') != selection_id
                or receipt.get('receiptId') != 'd01-approval:' + selection_id):
            raise ValueError('D01 approval independent readback differs')
        return receipt

    def revoke(self, transaction: HostTransaction, scope: TenantScope,
               selection_id: str, *, key: str, actor: str, reason: str,
               revoked_at: datetime) -> dict:
        if (type(transaction) is not HostTransaction or type(scope) is not TenantScope
                or type(selection_id) is not str or not selection_id
                or type(key) is not str or not 1 <= len(key) <= 160
                or key != key.strip() or type(actor) is not str
                or not actor or actor != actor.strip()
                or type(reason) is not str or not 1 <= len(reason) <= 500
                or reason != reason.strip() or type(revoked_at) is not datetime
                or revoked_at.utcoffset() is None):
            raise ValueError('exact D01 revocation required')
        self._proposal_row(transaction, scope, selection_id)
        request_hash = canonical_hash({
            'selectionId': selection_id, 'key': key, 'actor': actor,
            'reason': reason, 'revokedAt': revoked_at.isoformat(),
        })
        transaction.execute("SELECT set_config('aos.subject',%s,true)", (actor,))
        receipt = transaction.execute(
            """SELECT public.ecommerce_d01_source_revoke_a0v_107(
                %s,%s,%s,%s,%s,%s) AS receipt""",
            (selection_id, key, request_hash, actor, reason, revoked_at),
        ).fetchone()['receipt']
        stored = transaction.execute(
            """SELECT revocation_key,request_hash,actor,reason,revoked_at,receipt_ref
               FROM public.ecommerce_d01_source_revocation
               WHERE org_id=%s AND project_id=%s AND selection_id=%s""",
            (*scope.key, selection_id),
        ).fetchone()
        if (stored is None or stored['revocation_key'] != key
                or stored['request_hash'] != request_hash
                or stored['actor'] != actor or stored['reason'] != reason
                or stored['revoked_at'] != revoked_at or stored['receipt_ref'] != receipt
                or receipt.get('resourceType') != 'D01SourceSelectionRevocation'
                or receipt.get('resourceId') != selection_id
                or receipt.get('receiptId') != 'd01-revocation:' + selection_id):
            raise ValueError('D01 revocation independent readback differs')
        return receipt

    def read_current(self, transaction: HostTransaction, scope: TenantScope,
                     task_run_id: str, plan_id: str, actor: str,
                     occurred_at: datetime) -> tuple[object, dict]:
        """Read one approved packet on the Owner transaction; never grant by recency."""
        if (type(transaction) is not HostTransaction or type(scope) is not TenantScope
                or any(type(value) is not str or not value or value != value.strip()
                       for value in (task_run_id, plan_id, actor))
                or type(occurred_at) is not datetime
                or occurred_at.utcoffset() is None):
            raise ValueError('exact scoped D01 selection read required')
        matches = transaction.execute(
            """SELECT selection_id FROM public.ecommerce_d01_source_proposal
               WHERE org_id=%s AND project_id=%s AND task_run_id=%s
                 AND plan_revision_id=%s""",
            (*scope.key, task_run_id, plan_id),
        ).fetchall()
        if len(matches) != 1:
            raise ValueError('approved D01 selection unavailable')
        proposal, row = self._proposal_row(transaction, scope, matches[0]['selection_id'])
        approval = transaction.execute(
            """SELECT proposal_hash,checker,approved_at,receipt_ref
               FROM public.ecommerce_d01_source_approval
               WHERE org_id=%s AND project_id=%s AND selection_id=%s""",
            (*scope.key, proposal.selection_id),
        ).fetchone()
        revoked = transaction.execute(
            """SELECT selection_id FROM public.ecommerce_d01_source_revocation
               WHERE org_id=%s AND project_id=%s AND selection_id=%s""",
            (*scope.key, proposal.selection_id),
        ).fetchone()
        if approval is None or revoked is not None:
            raise ValueError('approved D01 selection unavailable')
        timeline = AipTaskStore(
            TransactionBoundConnectFactory(transaction, scope)
        ).timeline(scope, task_run_id)
        run, task, plan = timeline.run, timeline.task, timeline.plan
        schema = plan.steps[0].input_schema_ref if plan.steps else None
        receipt = approval['receipt_ref']
        if (proposal.tenant.org_id != scope.org_id
                or proposal.tenant.project_id != scope.project_id
                or proposal.task_run_ref.resource_id != task_run_id
                or proposal.task_run_ref.revision != str(run.version)
                or proposal.plan_ref.resource_id != plan_id
                or proposal.plan_ref.revision != str(plan.revision)
                or proposal.plan_content_hash != plan.content_hash
                or run.id != task_run_id or run.plan_revision_id != plan_id
                or run.task_id != task.id or plan.id != plan_id
                or plan.task_id != task.id
                or getattr(run.status, 'value', run.status) != 'running'
                or getattr(task.status, 'value', task.status) != 'executing'
                or getattr(plan.approval_status, 'value', plan.approval_status) != 'approved'
                or not plan.steps or plan.steps[0].step_key != 'portrait'
                or schema is None or plan.steps[0].input_refs != [schema]
                or schema.revision is None or not schema.authority
                or task.selection_ref is None
                or task.selection_ref.resource_type != 'SourceSelectionRevision'
                or task.selection_ref.resource_id != proposal.source_selection_ref.resource_id
                or task.selection_ref.revision != str(proposal.source_selection_ref.revision)
                or task.selection_ref.authority != 'postgresql'
                or approval['proposal_hash'] != row['content_hash']
                or approval['checker'] == proposal.proposed_by
                or approval['checker'] != getattr(plan, 'approved_by', None)
                or not isinstance(approval['approved_at'], datetime)
                or approval['approved_at'] < proposal.proposed_at
                or approval['approved_at'] > occurred_at
                or proposal.proposed_at > occurred_at
                or type(receipt) is not dict
                or receipt.get('resourceType') != 'D01SourceSelectionApproval'
                or receipt.get('resourceId') != proposal.selection_id
                or receipt.get('receiptId') != 'd01-approval:' + proposal.selection_id
                or type(receipt.get('contentHash')) is not str
                or not receipt['contentHash'].startswith('sha256:')
                or len(receipt['contentHash']) != 71
                or actor != proposal.proposed_by):
            raise ValueError('current approved D01 selection drifted')
        return proposal.packet, receipt
