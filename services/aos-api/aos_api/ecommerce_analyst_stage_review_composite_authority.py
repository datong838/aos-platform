"""Compose five installed-package validations from host-owned review proofs."""

from aos_api.asset_registry.canonical_json import canonical_json,canonical_sha256
from aos_api.ecommerce_analyst_stage_review_authority import read_stage_review_responsibility_authority
from aos_api.ecommerce_analyst_stage_review_command import (
    read_stage_review_eval_source_authority,require_stage_review_command_identity)
from aos_api.ecommerce_analyst_stage_review_coordinator import StageReviewValidationExchange
from aos_api.ecommerce_analyst_stage_review_runtime import read_stage_review_runtime_authority
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


class StageReviewCompositeAuthorityReader:
    def __init__(self,markings):
        if type(markings) not in {list,tuple} or not markings or any(
                type(value) is not str or not value or value.strip()!=value for value in markings):
            raise ValueError('explicit stage review markings required')
        self.markings=tuple(markings)

    def __call__(self,transaction,scope,item,actor,key,expected_version):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError('stage review composite requires HostTransaction and TenantScope')
        item=require_stage_review_command_identity(scope,item,actor=actor,key=key,
            expected_version=expected_version)
        responsibility=read_stage_review_responsibility_authority(transaction,scope,
            responsibility_plan_ref=item.responsibility_plan_ref,stage=item.stage,actor=actor)
        runtime=read_stage_review_runtime_authority(transaction,scope,
            **{name:getattr(item,name) for name in (
                'task_run_id','plan_ref','stage','stage_attempt_ref','subject_ref')})
        initial_shapes=((responsibility,{'reviewer','snapshot','payload','expected'}),
            (runtime,{'plan','snapshot','payload','expected'}))
        if any(type(value) is not dict or set(value)!=fields for value,fields in initial_shapes):
            raise ValueError('stage review authority proof shape drifted')
        evaluated=read_stage_review_eval_source_authority(transaction,scope,item,runtime['plan'],
            list(self.markings))
        if (type(evaluated) is not dict or set(evaluated)!={
                'snapshot','evalPayload','evalExpected','structurePayload','structureExpected'}):
            raise ValueError('stage review authority proof shape drifted')
        command_payload=dict(kind='validate_command_identity',
            tenant=item.tenant.model_dump(mode='json',by_alias=True),
            item=item.model_dump(mode='json',by_alias=True),actor=actor,key=key,
            expectedVersion=expected_version)
        command_expected={'decisionRef':{'resourceType':'AnalystStageDecisionRevision',
            'resourceId':item.decision_id,'revision':item.revision,'contentHash':item.content_hash}}
        pairs=((command_payload,command_expected),(responsibility['payload'],responsibility['expected']),
            (runtime['payload'],runtime['expected']),(evaluated['evalPayload'],evaluated['evalExpected']),
            (evaluated['structurePayload'],evaluated['structureExpected']))
        for payload,expected in pairs:canonical_json(payload);canonical_json(expected)
        snapshot={'schemaVersion':'aos.stage-review-composite-snapshot/v1',
            'commandHash':canonical_sha256(command_payload),'responsibility':responsibility['snapshot'],
            'runtime':runtime['snapshot'],'evalSource':evaluated['snapshot']}
        canonical_json(snapshot)
        return snapshot,tuple(StageReviewValidationExchange(payload,expected) for payload,expected in pairs)


__all__=['StageReviewCompositeAuthorityReader']
