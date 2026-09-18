#!/usr/bin/env python3
"""Transfer the one frozen snapshot group from AK to AL without rereading its source."""
from __future__ import annotations

import argparse
from datetime import datetime,timedelta
import json
import os
from pathlib import Path

import a0v_u_twelve_source_snapshot as snapshot
import a0v_al_replacement_recovery as replacement
import a0v_al_successor_business as successor
from a0v_qyh_current_product_event_first_chain import freeze


STATE=snapshot.STATE.parent/'al-saved-snapshot-recovery-v1'
GROUP='c5ff1926-45b0-56de-b6b3-07d5b7d053a1'
MANIFEST='sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01'
ACTIONS=('prepare','schedule-ingest','controls','transfer','renew','enable','inspect','pause-failed','pause','disable')
FAILED_ATTEMPT='3e319ca5-9e8d-4b0e-a034-295cd3e5b645'
LINK_COMMAND_HASH='sha256:f16b566f1974831e0c662ea67049c77acc1febd12c7bd8ff98e9651d0d396970'
LINK_IDEMPOTENCY_KEY=('snapshot-group-links:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:'
                      'bc77b98d9144f128154e876db40e4ebf8850b90c0d9196a7e67d0a908de33d4b')


def profile():
    snapshot.STATE=STATE
    snapshot.current.U_ID=replacement.load('create-al')['installationId']
    snapshot.current.U_GENERATION=successor.AL_GENERATION
    snapshot.CONTROL_PREFIX='a0v-al-snapshot'
    snapshot.DISABLE_KEY='a0v-al-saved-snapshot-disable-complete-v1'
    snapshot.preview.INSTALLATION=snapshot.current.U_ID
    snapshot.preview.GENERATION=snapshot.current.U_GENERATION
    return snapshot.current.U_ID,snapshot.current.U_GENERATION


def load(name):
    path=STATE/f'{name}-result.json'
    if not path.is_file() or path.stat().st_mode & 0o777!=0o600:
        raise RuntimeError(f'private {name} result required')
    return json.loads(path.read_text(encoding='utf-8'))


def prepare(plane):
    installation,generation=profile()
    value=snapshot.prepare(plane)
    if (value['installationRef']['installationId'],value['generation'])!=(installation,generation):
        raise RuntimeError('exact AL preview required')
    return {**value,'outcome':'AL_SAVED_SNAPSHOT_PREPARED'}


def schedule_ingest(plane):
    profile()
    value=snapshot.schedule_ingest(plane)
    return {**value,'outcome':'AL_SAVED_SNAPSHOT_SCHEDULES_CONFIRMED'}


def controls(plane):
    profile()
    value=snapshot.controls(plane)
    return {**value,'outcome':'AL_SAVED_SNAPSHOT_CONTROLS_CURRENT'}


def service_and_options(plane):
    from aos_api.tenant_scope import TenantScope
    installation,generation=profile()
    service=plane.pipeline_control_factory.build_snapshot_schedule(
        TenantScope(**snapshot.baseline.SCOPE),source_controls=True)
    options=service.options(actor=snapshot.ACTOR,installation_id=installation,generation=generation)
    if options.get('status')!='ready' or len(options.get('members',[]))!=12 or not options.get('policies'):
        raise RuntimeError('exact AL twelve-source options required')
    confirmed={item['scheduleId']:item for item in load('controls')['members']}
    members=[{'scheduleId':item['scheduleId'],'bindingRef':item['bindingRef']} for item in options['members']]
    if any(confirmed.get(item['scheduleId'],{}).get('bindingRef')!=item['bindingRef'] for item in members):
        raise RuntimeError('AL options differ from frozen controls')
    return service,members


def snapshot_service(plane):
    from aos_api.tenant_scope import TenantScope
    profile()
    return plane.pipeline_control_factory.build_snapshot_schedule(
        TenantScope(**snapshot.baseline.SCOPE),source_controls=True)


def transfer(plane):
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope
    service,members=service_and_options(plane)
    scope=TenantScope(**snapshot.baseline.SCOPE)
    with consumer_connection(runtime_worker_connection,snapshot.baseline.SCOPE) as conn:
        current=service._owner.read(conn,scope=scope,definition_id=snapshot.DEFINITION_ID)
    if (current is None or current['body']['state']!='disabled'
            or current['body']['installationId']!=successor.AK_ID or current['body']['revision']!=48):
        raise RuntimeError('exact disabled AK definition revision48 required')
    original=json.loads((snapshot.STATE.parent/'ak-saved-snapshot-recovery-v1'/'renew-result.json').read_text(encoding='utf-8'))
    recovery_ref=original['recovery']['receipt']['ref']
    result=service.transfer_saved_recovery(definition_id=snapshot.DEFINITION_ID,group_id=GROUP,
        actor=snapshot.ACTOR,members=members,expected_ref=current['ref'],
        expected_recovery_ref=recovery_ref,idempotency_key='a0v-al-saved-definition-transfer-v1')
    return {'outcome':'AL_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED','definition':result,
        'groupId':GROUP,'inputManifestHash':MANIFEST,'sourceReads':0}


def renew(plane):
    service,_=service_and_options(plane)
    transferred=load('transfer')['definition']
    context=service.read_recovery_context(group_id=GROUP,actor=snapshot.ACTOR)
    if (context['expectedDefinitionRef']!=transferred['ref'] or context['inputManifestHash']!=MANIFEST
            or context['expectedRecoveryRef'] is None):
        raise RuntimeError('exact AL transferred saved recovery context required')
    now=datetime.fromisoformat(context['windowRules']['currentTime'])
    expires=now+timedelta(hours=6)
    if expires<=datetime.fromisoformat(context['windowRules']['expiresAfter']):
        raise RuntimeError('six-hour saved recovery window does not advance predecessor')
    result=service.renew_saved_group(group_id=GROUP,actor=snapshot.ACTOR,
        expected_definition_ref=context['expectedDefinitionRef'],
        expected_recovery_ref=context['expectedRecoveryRef'],input_manifest_hash=MANIFEST,
        not_before=now,expires_at=expires,idempotency_key='a0v-al-saved-input-recovery-v16')
    return {'outcome':'AL_SAVED_SNAPSHOT_RECOVERY_RENEWED','context':context,
        'recovery':result,'sourceReads':0}


def enable(plane):
    service=snapshot_service(plane)
    renewed=load('renew')['recovery']['receipt']
    status=service.read_runtime_status(definition_id=snapshot.DEFINITION_ID,actor=snapshot.ACTOR)
    context=service.read_recovery_context(group_id=GROUP,actor=snapshot.ACTOR)
    if (status.get('configurationState')!='enabled'
            or status.get('definitionRef')!=renewed['body']['currentDefinitionRef']
            or context.get('expectedDefinitionRef')!=renewed['body']['currentDefinitionRef']
            or context.get('expectedRecoveryRef')!=renewed['ref']):
        raise RuntimeError('current enabled AL saved recovery authority required')
    return {'outcome':'AL_SAVED_SNAPSHOT_RECOVERY_ENABLED_CONFIRMED','definition':status,
        'recoveryRef':renewed['ref'],'sourceReads':0}


def inspect(plane):
    profile()
    return snapshot.inspect(plane)|{'outcome':'AL_SAVED_SNAPSHOT_INSPECTED'}


def pause_failed(plane):
    """Stop scheduling after AL crossed its exact budget-policy window."""
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope
    installation,generation=profile()
    scope=TenantScope(**snapshot.baseline.SCOPE)
    service=plane.pipeline_control_factory.build_snapshot_schedule(scope,source_controls=True)
    status=service.read_runtime_status(definition_id=snapshot.DEFINITION_ID,actor=snapshot.ACTOR)
    if status.get('configurationState')!='enabled' or status['definitionRef']['revision']!=50:
        raise RuntimeError('exact enabled AL failed recovery definition revision50 required')
    with consumer_connection(runtime_worker_connection,snapshot.baseline.SCOPE) as conn:
        facts=dict(conn.execute('''SELECT
          (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id=%s AND project_id=%s
            AND attempt_id=%s AND installation_id=%s AND generation=%s AND state='failed'
            AND revision=382) failed_attempt,
          (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id=%s AND project_id=%s
            AND installation_id=%s AND generation=%s AND state='running') running_attempts,
          (SELECT count(*) FROM pipeline_snapshot_schedule_member
            WHERE org_id=%s AND project_id=%s AND group_id=%s) members,
          (SELECT count(*) FROM meta_schedule_run r JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
            WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s
              AND r.status='running' AND r.executor_stopped IS FALSE AND r.finished_at IS NULL) running,
          (SELECT count(*) FROM pipeline_snapshot_group_input
            WHERE org_id=%s AND project_id=%s AND group_id=%s AND manifest_hash=%s) saved_input,
          (SELECT count(*) FROM pipeline_snapshot_group_recovery_receipt
            WHERE org_id=%s AND project_id=%s AND group_id=%s) recoveries,
          (SELECT count(*) FROM ecommerce_ingress_dataset_receipt d JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(d.org_id,d.project_id,d.run_id)
            WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s) dataset_receipts,
          (SELECT count(*) FROM pipeline_snapshot_group_relationship
            WHERE org_id=%s AND project_id=%s AND group_id=%s) relationships,
          (SELECT count(*) FROM pipeline_snapshot_group_link_command
            WHERE org_id=%s AND project_id=%s AND group_id=%s
              AND command_hash=%s) links,
          (SELECT coalesce(max(link_count),0) FROM pipeline_snapshot_group_link_command
            WHERE org_id=%s AND project_id=%s AND group_id=%s
              AND command_hash=%s) link_count,
          (SELECT count(*) FROM pipeline_snapshot_group_retirement
            WHERE org_id=%s AND project_id=%s AND group_id=%s) retirements,
          (SELECT count(*) FROM ecom_ingest_receipt WHERE org_id=%s AND workspace_id=%s
            AND idempotency_key=%s) store_receipt,
          (SELECT count(*) FROM ecom_link WHERE org_id=%s AND workspace_id=%s) store_links,
          (SELECT count(*) FROM projection_outbox WHERE org_id=%s AND workspace_id=%s
            AND event_source='authoritative_store'
            AND change_kind=ANY(ARRAY['links_written','links_tombstoned'])) store_outbox,
          (SELECT count(*) FROM projection_outbox WHERE org_id=%s AND workspace_id=%s
            AND projected IS FALSE) projection_pending,
          (SELECT count(*) FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s
            AND installation_id=%s AND generation=%s AND revision=6 AND execution_epoch=3
            AND enabled IS TRUE AND operation_fence IS FALSE AND desired_state='enabled'
            AND observed_state='ready') live_binding,
          (SELECT count(*) FROM extension_runtime_resource_lease WHERE org_id=%s AND project_id=%s
            AND generation=%s AND cleanup_state='pending' AND observed_release IS FALSE) live_resources,
          (SELECT count(*) FROM aip_model_governance_policy_head h
            JOIN aip_model_governance_policy_revision r
              ON (r.org_id,r.project_id,r.policy_kind,r.policy_id,r.revision)=
                 (h.org_id,h.project_id,h.policy_kind,h.policy_id,h.current_revision)
            WHERE h.org_id=%s AND h.project_id=%s AND h.policy_kind='budget'
              AND h.policy_id='a0v-ecommerce-budget-policy-v1' AND h.current_revision=7
              AND r.lifecycle='active' AND r.effective_until<=clock_timestamp()) expired_budget_policy,
          (SELECT count(*) FROM extension_runtime_binding WHERE org_id='dev-org'
            AND project_id='dev-project') canary''',
          (*scope.key,FAILED_ATTEMPT,installation,generation,*scope.key,installation,generation,
           *scope.key,GROUP,*scope.key,GROUP,*scope.key,GROUP,MANIFEST,*scope.key,GROUP,
           *scope.key,GROUP,*scope.key,GROUP,*scope.key,GROUP,LINK_COMMAND_HASH,
           *scope.key,GROUP,LINK_COMMAND_HASH,*scope.key,GROUP,
           scope.org_id,scope.project_id,LINK_IDEMPOTENCY_KEY,
           scope.org_id,scope.project_id,scope.org_id,scope.project_id,
           scope.org_id,scope.project_id,*scope.key,installation,generation,
           *scope.key,generation,*scope.key)).fetchone())
    expected={'failed_attempt':1,'running_attempts':0,'members':12,'running':12,
        'saved_input':1,'recoveries':16,'dataset_receipts':12,'relationships':1,
        'links':1,'link_count':1168,'retirements':0,'store_receipt':0,'store_links':0,
        'store_outbox':0,'projection_pending':0,'live_binding':1,'live_resources':3,
        'expired_budget_policy':1,'canary':0}
    if facts!=expected:
        raise RuntimeError('exact failed AL saved-input recovery facts required')
    result=service.transition(definition_id=snapshot.DEFINITION_ID,actor=snapshot.ACTOR,intent='disable',
        expected_ref=status['definitionRef'],idempotency_key='a0v-al-saved-snapshot-pause-failed-v1')
    return {'outcome':'AL_SAVED_SNAPSHOT_FAILED_RECOVERY_PAUSED','facts':expected,
        'definition':result,'sourceReads':0}


def pause(plane):
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope
    installation,generation=profile()
    scope=TenantScope(**snapshot.baseline.SCOPE)
    service=plane.pipeline_control_factory.build_snapshot_schedule(scope,source_controls=True)
    status=service.read_runtime_status(definition_id=snapshot.DEFINITION_ID,actor=snapshot.ACTOR)
    if status.get('configurationState')!='enabled' or status['definitionRef']['revision']!=50:
        raise RuntimeError('exact enabled AL recovery definition revision50 required')
    with consumer_connection(runtime_worker_connection,snapshot.baseline.SCOPE) as conn:
        facts=conn.execute('''SELECT
          (SELECT count(*) FROM pipeline_snapshot_schedule_member
            WHERE org_id=%s AND project_id=%s AND group_id=%s) members,
          (SELECT count(*) FROM meta_schedule_run r JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
            WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s
              AND r.status='running' AND r.executor_stopped IS FALSE) running,
          (SELECT count(*) FROM pipeline_snapshot_group_input
            WHERE org_id=%s AND project_id=%s AND group_id=%s AND manifest_hash=%s) saved_input,
          (SELECT count(*) FROM pipeline_snapshot_group_recovery_receipt
            WHERE org_id=%s AND project_id=%s AND group_id=%s) recoveries,
          (SELECT count(*) FROM extension_runtime_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
              AND enabled IS FALSE AND operation_fence IS TRUE AND observed_state='unknown') fenced_binding,
          (SELECT count(*) FROM extension_runtime_resource_lease
            WHERE org_id=%s AND project_id=%s AND generation=%s
              AND cleanup_state='released' AND observed_release IS TRUE) released_resources''',
          (*scope.key,GROUP,*scope.key,GROUP,*scope.key,GROUP,MANIFEST,*scope.key,GROUP,
           *scope.key,installation,generation,*scope.key,generation)).fetchone()
    expected={'members':12,'running':12,'saved_input':1,'recoveries':16,
        'fenced_binding':1,'released_resources':3}
    if dict(facts)!=expected:
        raise RuntimeError('exact released AL saved-input recovery facts required')
    result=service.transition(definition_id=snapshot.DEFINITION_ID,actor=snapshot.ACTOR,intent='disable',
        expected_ref=status['definitionRef'],idempotency_key='a0v-al-saved-snapshot-pause-released-v1')
    return {'outcome':'AL_SAVED_SNAPSHOT_RELEASED_RECOVERY_PAUSED','facts':expected,
        'definition':result,'sourceReads':0}


def disable(plane):
    profile()
    value=snapshot.disable(plane)
    return {**value,'outcome':'AL_SAVED_SNAPSHOT_COMPLETE_DISABLED'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=ACTIONS)
    args=parser.parse_args()
    profile()
    _previous,_preflight,plane=snapshot.baseline.setup()
    value=globals()[args.action.replace('-','_')](plane)
    if args.action!='inspect':
        output=STATE/f'{args.action}-result.json'
        if output.exists():
            raise RuntimeError(f'immutable {args.action} output exists')
        freeze(output,value)
    print(json.dumps(value,ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':
    os.environ.setdefault('AOS_DOTENV_DISABLED','1')
    main()
