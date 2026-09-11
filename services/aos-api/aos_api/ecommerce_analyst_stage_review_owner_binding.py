"""StageDecision Owner state binding for the async review coordinator."""

from __future__ import annotations

import inspect

from aos_api.asset_registry.canonical_json import canonical_json,canonical_sha256
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.ecommerce_analyst_stage_decision import AnalystStageDecisionRevision
from aos_api.ecommerce_analyst_stage_decision_store import AnalystStageDecisionStore
from aos_api.ecommerce_analyst_stage_review_command import require_stage_review_command_identity
from aos_api.ecommerce_analyst_stage_review_coordinator import (
    PreparedStageReviewValidation,StageReviewValidationExchange)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


_KINDS=frozenset({"validate_command_identity","validate_review_slot",
    "validate_runtime","validate_eval_proof","validate_structure_case"})
_OPERATION="analyst.stage_decision_publish"


class StageReviewDecisionOwnerBinding:
    """Bind trusted authority reads to the canonical StageDecision Owner."""

    def __init__(self,scope:TenantScope,*,read_authority):
        if type(scope) is not TenantScope:
            raise TypeError("stage review owner binding requires TenantScope")
        if not callable(read_authority) or inspect.iscoroutinefunction(read_authority):
            raise TypeError("synchronous stage review authority reader required")
        self.scope,self.read_authority=scope,read_authority

    def _command(self,command):
        if type(command) is not dict or set(command)!={"scope","item","actor","key","expectedVersion"}:
            raise ValueError("exact stage review owner command required")
        raw_scope=command["scope"]
        if type(raw_scope) is not dict or set(raw_scope)!={"orgId","projectId"}:
            raise ValueError("exact stage review owner scope required")
        scope=TenantScope(raw_scope["orgId"],raw_scope["projectId"])
        if scope!=self.scope or type(command["item"]) is not dict:
            raise ValueError("stage review owner scope drifted")
        item=AnalystStageDecisionRevision.model_validate(command["item"])
        item=require_stage_review_command_identity(scope,item,actor=command["actor"],
            key=command["key"],expected_version=command["expectedVersion"])
        return item

    def _lock(self,transaction,item,key):
        for lock in sorted({canonical_hash([*self.scope.key,"stage-target",item.decision_id]),
                canonical_hash([*self.scope.key,"stage-key",key])}):
            transaction.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",(lock,))

    def _read(self,transaction,command):
        if type(transaction) is not HostTransaction:
            raise TypeError("stage review owner binding requires HostTransaction")
        item=self._command(command);self._lock(transaction,item,command["key"])
        head=transaction.execute("""SELECT current_revision,version FROM ecommerce_analyst_stage_decision_head
            WHERE org_id=%s AND project_id=%s AND decision_id=%s FOR SHARE""",
            (*self.scope.key,item.decision_id)).fetchone()
        receipt=transaction.execute("""SELECT request_hash,result_ref,created_by
            FROM ecommerce_analyst_authority_receipt WHERE org_id=%s AND project_id=%s
            AND operation=%s AND idempotency_key=%s FOR SHARE""",
            (*self.scope.key,_OPERATION,command["key"])).fetchone()
        if receipt is not None:
            raise ValueError("stage review replay must use owner fast path")
        authority=self.read_authority(transaction,self.scope,item,command["actor"])
        if type(authority) is not tuple or len(authority)!=2:
            raise TypeError("authority snapshot and exchanges required")
        authority_snapshot,exchanges=authority
        if type(authority_snapshot) is not dict or not authority_snapshot or type(exchanges) is not tuple:
            raise ValueError("complete stage review authority required")
        if (any(type(exchange) is not StageReviewValidationExchange for exchange in exchanges)
            or {exchange.payload.get("kind") for exchange in exchanges}!=_KINDS
            or len(exchanges)!=len(_KINDS)):
            raise ValueError("five exact stage review validations required")
        snapshot={"schemaVersion":"aos.stage-review-owner-snapshot/v1",
            "scope":{"orgId":self.scope.org_id,"projectId":self.scope.project_id},
            "decisionId":item.decision_id,"authority":authority_snapshot,
            "validationExchangeHash":canonical_sha256([
                [exchange.payload,exchange.expected] for exchange in exchanges]),
            "head":None if head is None else {"currentRevision":int(head["current_revision"]),
                "version":int(head["version"])},
            "receipt":None}
        canonical_json(snapshot)
        return snapshot,exchanges

    def prepare_in_transaction(self,transaction,command):
        return self._read(transaction,command)

    def load_current_snapshot(self,transaction,command):
        snapshot,_=self._read(transaction,command)
        return snapshot

    def publish_in_transaction(self,transaction,command,prepared,results):
        item=self._command(command)
        if (type(transaction) is not HostTransaction
            or type(prepared) is not PreparedStageReviewValidation
            or type(results) is not tuple or len(results)!=len(_KINDS)
            or {exchange.payload.get("kind") for exchange in prepared.exchanges}!=_KINDS
            or any(result!=exchange.expected for result,exchange in zip(results,prepared.exchanges))):
            raise ValueError("complete installed stage review validation required")
        ref=AnalystStageDecisionStore(transaction,self.scope).put(item,actor=command["actor"],
            key=command["key"],expected_version=command["expectedVersion"])
        return ref.model_dump(mode="json",by_alias=True)


__all__=["StageReviewDecisionOwnerBinding"]
