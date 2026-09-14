"""Current original event -> canonical initialization draft, without execution authority."""
from copy import deepcopy
from aos_api.aip_action_models import CreateActionProposalRequest
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_analysis_bootstrap_authority import AnalysisBootstrapCurrentBinding, require_current_bootstrap_review_identity
from aos_api.ecommerce_analysis_bootstrap_contract import AnalysisBootstrapIntent
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.extension_runtime.runtime_gate import _reject_deferred


class _BootstrapActionGuard:
    def __init__(self, current, conn, claimed, intent, preview_ref):
        if type(current) is not AnalysisBootstrapCurrentBinding:
            raise TypeError('exact bootstrap current binding required')
        self.current, self.conn, self.claimed = current, conn, claimed
        self.intent = AnalysisBootstrapIntent.model_validate(intent).checked()
        self.preview_ref = ExactRevisionRef.model_validate(preview_ref)

    def check(self, conn, scope, actor, *, action_snapshot, payload, task_id, run_id, preview_ref, checker):
        if scope != self.current.analysis.scope:
            raise PermissionError('bootstrap action tenant differs')
        statement = 'SELECT pg_backend_pid() AS pid,txid_current() AS xid'
        if conn.execute(statement).fetchone() != self.conn.execute(statement).fetchone():
            raise PermissionError('bootstrap action transaction differs')
        if (task_id != self.intent.compilation_receipt.task_id or run_id is not None
                or preview_ref is None or ExactRevisionRef.model_validate(preview_ref) != self.preview_ref
                or payload != {'bootstrapIntent': self.intent.model_dump(mode='json', by_alias=True)}):
            raise ValueError('bootstrap action intent Task or Preview differs')
        return self.current.run_current(self.conn, claimed=self.claimed,
            intent=self.intent.model_dump(mode='json', by_alias=True), preview_ref=self.preview_ref,
            execute=lambda _: require_current_bootstrap_review_identity(transaction=HostTransaction(self.conn),
                scope=scope, actor=actor, maker=self.current.analysis.source.actor,
                action_snapshot=action_snapshot, checker=checker))


class AnalysisBootstrapActionPreparation:
    def __init__(self, current):
        if type(current) is not AnalysisBootstrapCurrentBinding:
            raise TypeError('exact bootstrap current binding required')
        self.current = current

    def run_current(self, conn, *, claimed, intent, preview_ref, execute):
        from aos_api.aip_action_store import AipActionStore
        if not callable(execute):
            raise TypeError('synchronous bootstrap action callback required')
        scope, actor = self.current.analysis.scope, self.current.analysis.source.actor
        guard = _BootstrapActionGuard(self.current, conn, claimed, intent, preview_ref)
        store = AipActionStore(TransactionBoundConnectFactory(HostTransaction(conn), scope), bootstrap_guard=guard)
        def prepare(current):
            snapshot = store.action_type_snapshot(scope, 'ecommerce_analysis_bootstrap')
            body = CreateActionProposalRequest(actionTypeId='ecommerce_analysis_bootstrap',
                taskId=current['task']['task_id'], purpose='初始化分析承接位置，暂不执行经营步骤',
                payload={'bootstrapIntent': deepcopy(current['intent'])}, impactPreviewRef=guard.preview_ref,
                expiresAt=current['preview']['expires_at'])
            risk = classify_action_risk(body.action_type_id, snapshot, body.payload, body.risk_hint)
            key = 'analysis-bootstrap-action-' + canonical_sha256([*scope.key, guard.intent.content_hash]).removeprefix('sha256:')
            bundle = store.create_proposal(scope, actor, key, body, snapshot, risk)
            before = conn.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                                  (*scope.key, bundle.proposal.id)).fetchone()
            if before is None or before['status'] != 'drafted' or before['policy_snapshot'].get('draftOnly') is not True:
                raise ValueError('bootstrap initialization draft must remain non-executable')
            result = execute(bundle)
            _reject_deferred(result)
            guard.check(conn, scope, actor, action_snapshot=snapshot, payload=body.payload,
                        task_id=body.task_id, run_id=body.run_id, preview_ref=body.impact_preview_ref, checker=False)
            after = conn.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                                 (*scope.key, bundle.proposal.id)).fetchone()
            if after != before:
                raise ValueError('bootstrap draft changed during callback')
            return result
        return self.current.run_current(conn, claimed=claimed, intent=intent, preview_ref=preview_ref, execute=prepare)
