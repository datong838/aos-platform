#!/usr/bin/env python3
"""Transfer the one frozen U snapshot group to V without rereading its source."""
from __future__ import annotations

import argparse
from datetime import datetime,timedelta
import json
import os
from pathlib import Path

import a0v_u_twelve_source_snapshot as snapshot
import a0v_v_replacement_recovery as replacement
import a0v_v_successor_business as successor
from a0v_qyh_current_product_event_first_chain import freeze


STATE=snapshot.STATE.parent/'v-saved-snapshot-recovery-v1'
GROUP='c5ff1926-45b0-56de-b6b3-07d5b7d053a1'
MANIFEST='sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01'
ACTIONS=('prepare','schedule-ingest','controls','transfer','renew','enable','inspect','disable')


def profile():
    snapshot.STATE=STATE
    snapshot.current.U_ID=replacement.load('create-v')['installationId']
    snapshot.current.U_GENERATION=successor.V_GENERATION
    snapshot.CONTROL_PREFIX='a0v-v-snapshot'
    snapshot.DISABLE_KEY='a0v-v-saved-snapshot-disable-complete-v1'
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
        raise RuntimeError('exact V preview required')
    return {**value,'outcome':'V_SAVED_SNAPSHOT_PREPARED'}


def schedule_ingest(plane):
    profile()
    value=snapshot.schedule_ingest(plane)
    return {**value,'outcome':'V_SAVED_SNAPSHOT_SCHEDULES_CONFIRMED'}


def controls(plane):
    profile()
    value=snapshot.controls(plane)
    return {**value,'outcome':'V_SAVED_SNAPSHOT_CONTROLS_CURRENT'}


def service_and_options(plane):
    from aos_api.tenant_scope import TenantScope
    installation,generation=profile()
    service=plane.pipeline_control_factory.build_snapshot_schedule(
        TenantScope(**snapshot.baseline.SCOPE),source_controls=True)
    options=service.options(actor=snapshot.ACTOR,installation_id=installation,generation=generation)
    if options.get('status')!='ready' or len(options.get('members',[]))!=12 or not options.get('policies'):
        raise RuntimeError('exact V twelve-source options required')
    confirmed={item['scheduleId']:item for item in load('controls')['members']}
    members=[{'scheduleId':item['scheduleId'],'bindingRef':item['bindingRef']} for item in options['members']]
    if any(confirmed.get(item['scheduleId'],{}).get('bindingRef')!=item['bindingRef'] for item in members):
        raise RuntimeError('V options differ from frozen controls')
    return service,members


def transfer(plane):
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope
    service,members=service_and_options(plane)
    scope=TenantScope(**snapshot.baseline.SCOPE)
    with consumer_connection(runtime_worker_connection,snapshot.baseline.SCOPE) as conn:
        current=service._owner.read(conn,scope=scope,definition_id=snapshot.DEFINITION_ID)
    if (current is None or current['body']['state']!='disabled'
            or current['body']['installationId']!=replacement.U_ID or current['body']['revision']!=4):
        raise RuntimeError('exact disabled U definition revision4 required')
    original=json.loads((snapshot.STATE.parent/'u-twelve-source-snapshot-v1'/'recover-saved-result.json').read_text(encoding='utf-8'))
    recovery_ref=original['recovery']['receipt']['ref']
    result=service.transfer_saved_recovery(definition_id=snapshot.DEFINITION_ID,group_id=GROUP,
        actor=snapshot.ACTOR,members=members,expected_ref=current['ref'],
        expected_recovery_ref=recovery_ref,idempotency_key='a0v-v-saved-definition-transfer-v1')
    return {'outcome':'V_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED','definition':result,
        'groupId':GROUP,'inputManifestHash':MANIFEST,'sourceReads':0}


def renew(plane):
    service,_=service_and_options(plane)
    transferred=load('transfer')['definition']
    context=service.read_recovery_context(group_id=GROUP,actor=snapshot.ACTOR)
    if (context['expectedDefinitionRef']!=transferred['ref'] or context['inputManifestHash']!=MANIFEST
            or context['expectedRecoveryRef'] is None):
        raise RuntimeError('exact transferred saved recovery context required')
    now=datetime.fromisoformat(context['windowRules']['currentTime'])
    expires=now+timedelta(hours=6)
    if expires<=datetime.fromisoformat(context['windowRules']['expiresAfter']):
        raise RuntimeError('six-hour saved recovery window does not advance predecessor')
    result=service.renew_saved_group(group_id=GROUP,actor=snapshot.ACTOR,
        expected_definition_ref=context['expectedDefinitionRef'],
        expected_recovery_ref=context['expectedRecoveryRef'],input_manifest_hash=MANIFEST,
        not_before=now,expires_at=expires,idempotency_key='a0v-v-saved-input-recovery-v2')
    return {'outcome':'V_SAVED_SNAPSHOT_RECOVERY_RENEWED','context':context,
        'recovery':result,'sourceReads':0}


def enable(plane):
    service,_=service_and_options(plane)
    renewed=load('renew')['recovery']['receipt']
    status=service.read_runtime_status(definition_id=snapshot.DEFINITION_ID,actor=snapshot.ACTOR)
    context=service.read_recovery_context(group_id=GROUP,actor=snapshot.ACTOR)
    if (status.get('configurationState')!='enabled'
            or status.get('definitionRef')!=renewed['body']['currentDefinitionRef']
            or context.get('expectedDefinitionRef')!=renewed['body']['currentDefinitionRef']
            or context.get('expectedRecoveryRef')!=renewed['ref']):
        raise RuntimeError('current enabled V saved recovery authority required')
    return {'outcome':'V_SAVED_SNAPSHOT_RECOVERY_ENABLED_CONFIRMED','definition':status,
        'recoveryRef':renewed['ref'],'sourceReads':0}


def inspect(plane):
    profile()
    return snapshot.inspect(plane)|{'outcome':'V_SAVED_SNAPSHOT_INSPECTED'}


def disable(plane):
    profile()
    value=snapshot.disable(plane)
    return {**value,'outcome':'V_SAVED_SNAPSHOT_COMPLETE_DISABLED'}


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
