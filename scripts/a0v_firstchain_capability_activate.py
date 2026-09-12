"""Bounded first-chain capability Owner transitions using actual health evidence."""
import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from a0v_firstchain_capability_bindings import prepare, database_connect, SCOPE
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_agent_registry_store import AipAgentRegistryNotFound
from aos_api.aip_agent_registry_contracts import EvaluateOperationalBindingRequest, UpdateCapabilityBindingRequest
from aos_api.aip_model_runtime_store import AipModelRuntimeStore

ACTOR='a0v-firstchain-capability-owner'


def latest_health(connect, provider):
    with connect(SCOPE) as conn:
        row=conn.execute("SELECT * FROM aip_provider_health_observation WHERE org_id=%s AND project_id=%s AND provider_ref->>'assetId'=%s ORDER BY observed_at DESC,observation_id DESC LIMIT 1",(*SCOPE.key,provider.asset_id)).fetchone()
    now=datetime.now(UTC)
    if (row is None or row['status']!='healthy' or not row['observed_at']<=now<row['expires_at']
            or row['provider_ref']!=provider.model_dump(mode='json',by_alias=True)):
        raise ValueError('FIRSTCHAIN_CURRENT_EXACT_HEALTH_REQUIRED')
    return AipModelRuntimeStore._health_from_row(SCOPE,row)


def copy_health_to_clone():
    source=database_connect('aos_meta_head');target=database_connect('aos_text_renewal_20260912')
    source_store=AipModelRuntimeStore(source);target_store=AipModelRuntimeStore(target)
    provider=source_store.get_provider(SCOPE,'a0v-agnes-text-readonly-dev')
    clone_provider=target_store.get_provider(SCOPE,provider.provider_instance_id)
    if provider!=clone_provider or provider.lifecycle.value!='active':
        raise ValueError('FIRSTCHAIN_CLONE_PROVIDER_DIFFERS')
    from a0v_firstchain_capability_bindings import exact
    observation=latest_health(source,exact('ProviderInstanceRevision',provider.provider_instance_id,provider.revision,provider.content_hash))
    result=target_store.record_health(SCOPE,ACTOR,'clone-replay-'+observation.observation_id,observation)
    if result!=observation:raise ValueError('FIRSTCHAIN_CLONE_OBSERVATION_DIFFERS')
    return {'sourceDatabase':'aos_meta_head','targetDatabase':'aos_text_renewal_20260912','observationId':result.observation_id,
        'observedAt':result.observed_at,'expiresAt':result.expires_at,'newProviderCalls':0}


def run(database, logic_ids=('D01','D02','D03')):
    connect,readiness,items=prepare(database,logic_ids)
    if any(result.readiness.value!='available' or result.reasons for _,_,_,result in items):
        raise ValueError('FIRSTCHAIN_DEPENDENCIES_BLOCKED')
    service=AipCapabilityBindingService(connect,readiness_service=readiness)
    results=[]
    for skill,request,deps,preview in items:
        health=latest_health(connect,deps.provider_ref)
        key='a0v-bind-'+request.binding_id
        try:
            service.get(SCOPE,request.binding_id)
            existed=True
        except AipAgentRegistryNotFound:
            existed=False
        binding,receipt=service.create(SCOPE,request,idempotency_key=key+'-create',actor=ACTOR,occurred_at=datetime.now(UTC))
        if binding.capability!=request.binding.capability or binding.secret_ref!=request.binding.secret_ref:
            raise ValueError('FIRSTCHAIN_BINDING_TARGET_DRIFT')
        epoch=health.observation_id
        if binding.status=='active':
            if binding.dependencies!=deps:
                raise ValueError('FIRSTCHAIN_ACTIVE_BINDING_DEPENDENCY_DRIFT')
            if binding.readiness_expires_at<=datetime.now(UTC) or binding.observed_at!=health.observed_at:
                binding,_=service.update(SCOPE,binding.binding_id,
                    UpdateCapabilityBindingRequest(expected_version=binding.version,from_status='active',to_status='suspended',
                        health=health.status,observed_at=health.observed_at),idempotency_key=key+'-suspend-'+epoch,actor=ACTOR)
        if binding.status in {'provisioning','suspended'}:
            if (binding.dependency_snapshot_hash!=preview.dependency_snapshot_hash
                    or binding.readiness_expires_at is None or binding.readiness_expires_at<=datetime.now(UTC)
                    or binding.last_evaluated_at is None or binding.last_evaluated_at<health.observed_at):
                binding,result,_=service.evaluate(SCOPE,binding.binding_id,
                    EvaluateOperationalBindingRequest(expected_version=binding.version,dependencies=deps,
                        expected_dependency_snapshot_hash=preview.dependency_snapshot_hash),
                    idempotency_key=key+'-evaluate-v'+str(binding.version),actor=ACTOR,evaluated_at=datetime.now(UTC))
                if result.readiness.value!='available':raise ValueError('FIRSTCHAIN_READINESS_CHANGED')
            previous=binding.status
            binding,_=service.update(SCOPE,binding.binding_id,
                UpdateCapabilityBindingRequest(expected_version=binding.version,from_status=previous,to_status='active',
                    health='healthy',observed_at=health.observed_at),
                idempotency_key=key+('-activate' if previous=='provisioning' else '-reactivate-'+epoch),actor=ACTOR)
        elif binding.status!='active':
            raise ValueError('FIRSTCHAIN_BINDING_STATE_UNSUPPORTED')
        results.append({'skillId':skill,'bindingId':binding.binding_id,'status':binding.status,'version':binding.version,
            'health':binding.health.value,'readiness':binding.operational_readiness.value,'dependencySnapshotHash':binding.dependency_snapshot_hash,
            'observedAt':binding.observed_at,'readinessExpiresAt':binding.readiness_expires_at,'bindingExistedBefore':existed})
    return {'database':database,'bindings':results,'providerCalls':0,'agentActivations':0,'businessRuns':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--database-name',choices=['aos_meta_head','aos_text_renewal_20260912'])
    parser.add_argument('--apply',action='store_true');parser.add_argument('--copy-health-to-clone',action='store_true');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.apply:raise ValueError('FIRSTCHAIN_EXPLICIT_APPLY_REQUIRED')
    if args.copy_health_to_clone:
        if args.database_name is not None:raise ValueError('HEALTH_COPY_MODE_EXCLUSIVE')
        result=copy_health_to_clone()
    else:
        if args.database_name is None:raise ValueError('EXACT_DATABASE_REQUIRED')
        result=run(args.database_name)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,default=str,ensure_ascii=False,indent=2))
