#!/usr/bin/env python3
"""Create and activate clean T after exact released S retirement."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from uuid import UUID


ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT.parent/'.aos-recovery-20260917/state/q-advisor-baseline/replacement-t'
T_DIR=STATE/'t'
BUNDLE_ROOT=(ROOT.parent/
    '.aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete')
S_ID='77b8e5c2-db96-4d55-a808-1b62e00163d2'
S_GENERATION='e621100a-baea-440f-9075-ae8a5290845a'
LOCK='sha256:15ac55d0ca7098c4df286ad70b6a20e79c327b0ec9c53baceea7cbb7059fcae8'
GROUP='6a402d31-83ad-546c-807f-508c87498ce1'
S_DISABLE_OPERATION='5243452a-161c-40cb-aa9c-6dc5dd8f544b'
VERSIONS={'domain.ecommerce.core':'1.4.0','platform.ecommerce.niushop':'1.23.0',
          'solution.ecommerce.growth':'1.10.0','solution.ecommerce.operations-base':'1.2.0'}
PREFIX='a0v-qyh-clean-t-20260917'
ACTIONS=('preflight','create-t','uninstall-s','prepare-t','verify-t','stage-t',
         'configure-t','enable-t','observe')


def load_profile():
    spec=importlib.util.spec_from_file_location('t_base_profile',ROOT/'scripts/a0v_ecommerce_current_reinstall.py')
    profile=importlib.util.module_from_spec(spec);assert spec.loader is not None;spec.loader.exec_module(profile)
    profile.STATE=STATE;profile.BUNDLE_ROOT=BUNDLE_ROOT;profile.VERSIONS=dict(VERSIONS)
    def initial(label):
        if label!='t':raise ValueError('only fixed T installation allowed')
        value=json.loads((T_DIR/'create-result.json').read_text(encoding='utf-8'))
        identity=value.get('installationId')
        try:canonical=str(UUID(identity)) if isinstance(identity,str) else None
        except ValueError:canonical=None
        if canonical!=identity:
            raise ValueError('canonical T installation required')
        return value
    profile._initial=initial
    return profile


def freeze(path,value):load_profile()._freeze(path,value)


def load(name):
    path=STATE/f'{name}-result.json'
    if not path.is_file() or path.stat().st_mode&0o777!=0o600:
        raise ValueError(f'private {name} result required')
    return json.loads(path.read_text(encoding='utf-8'))


def detached_s(profile):
    snapshot=profile.observe_installation(S_ID);head=snapshot['head'];bindings=snapshot['bindings']
    if (str(head['installation_id'])!=S_ID or head['state']!='active' or head['etag_version']!=5
            or head['lock_hash']!=LOCK or len(bindings)!=1
            or str(bindings[0]['generation'])!=S_GENERATION
            or (bindings[0]['revision'],bindings[0]['execution_epoch'])!=(9,5)
            or bindings[0]['enabled'] is not False or bindings[0]['operation_fence'] is not True
            or bindings[0]['desired_state']!='disabled' or bindings[0]['observed_state']!='unknown'
            or len(snapshot['resources'])!=3 or any(r['cleanup_state']!='released'
                or r['observed_release'] is not True for r in snapshot['resources'])
            or any(o['status'] not in {'succeeded','failed','cancelled'} for o in snapshot['operations'])
            or snapshot['canaryInstallations']!=0):
        raise ValueError('exact detached S installation required')
    from a0v_formal_text_model_renewal import database_connect
    with database_connect('aos_meta_head')() as conn:
        routes=conn.execute("""SELECT handler_kind,installation_id,generation,execution_epoch,
          operation_fence,cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s""",(GROUP,)).fetchall()
        op=conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND operation_id=%s""",
          (S_DISABLE_OPERATION,)).fetchone()
        phases=[r['phase'] for r in conn.execute("""SELECT phase FROM extension_dispatch_lifecycle_receipt
          WHERE org_id='org-org' AND project_id='dev-project' AND runtime_operation_id=%s
          ORDER BY created_at""",(S_DISABLE_OPERATION,)).fetchall()]
    if (len(routes)!=9 or any(r['handler_kind']!='legacy' or r['installation_id'] is not None
            or r['generation'] is not None or r['execution_epoch'] is not None
            or r['operation_fence'] is not True or r['cutover_group_revision']!=62 for r in routes)
            or op is None or dict(op)!={'status':'succeeded','phase':'succeeded'}
            or phases!=['fence','detach']):
        raise ValueError('exact S detach Receipt required')
    return snapshot


def preflight(profile):
    value=detached_s(profile)
    if T_DIR.exists():raise ValueError('T intent already exists; inspect without resending')
    return {'outcome':'T_REPLACEMENT_PREFLIGHT_GREEN','s':value,'versions':VERSIONS,'externalEffects':0}


def create_t(profile):
    load('preflight');s=detached_s(profile);predecessor=profile.replacement_ref(s)
    if T_DIR.exists():raise ValueError('T intent/result exists; inspect without resending')
    T_DIR.mkdir(parents=True,exist_ok=False,mode=0o700)
    helper=profile._load('a0v_ecommerce_growth_1_5_registry_successor')
    installer=profile._load('a0v_canonical_ecommerce_first_install')
    backup=helper._database_backup(context=helper.DOCKER_CONTEXT,container=helper.DATABASE_CONTAINER,
        state_dir=T_DIR)
    profile._freeze(T_DIR/'create-intent.json',
        {'label':'t','predecessor':predecessor,'versions':VERSIONS,'backup':backup})
    connect=installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER,database_name=helper.DATABASE_NAME)
    result=installer.create_approved_first_installation(connect_factory=connect,state_dir=profile.TRUST_STATE,
        core_version=VERSIONS['domain.ecommerce.core'],adapter_version=VERSIONS['platform.ecommerce.niushop'],
        growth_version=VERSIONS['solution.ecommerce.growth'],idempotency_prefix=PREFIX,
        current_installation_ref=predecessor)
    if result['installationState']!='approved':raise ValueError('approved T replacement required')
    profile._freeze(T_DIR/'create-result.json',result)
    return {'outcome':'T_REPLACEMENT_APPROVED',**result}


def uninstall_s(profile):
    load('create-t');detached_s(profile)
    t=profile.observe_installation(profile._initial('t')['installationId'])
    if (t['head']['state'],t['head']['etag_version'],t['bindings'])!=('approved',3,[]):
        raise ValueError('approved unprepared T required before S uninstall')
    intent={'installationId':S_ID,'etag':5,'generation':S_GENERATION,'bindingRevision':9,
        'runtimeOperationId':S_DISABLE_OPERATION,'successorInstallationId':str(t['head']['installation_id']),
        'idempotencyKey':PREFIX+'-uninstall-s'}
    profile._freeze_or_match(STATE/'uninstall-s-intent.json',intent)
    legacy=profile._load('a0v_ecommerce_invalid_baseline_uninstall')
    store,service=legacy._build(profile._installation_connection,
        profile.TRUST_STATE/'signing/trust-roots.json')
    from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest
    receipt=service.uninstall(**profile.SCOPE,installation_id=S_ID,
        request=UninstallInstallationRequest(reason='S resources released and routes detached before clean T'),
        actor='a0v-ecommerce-growth-1.4-runtime-owner',roles=['admin'],markings=[],
        idempotency_key=intent['idempotencyKey'],if_match='"5"')
    record=store.get_installation(**profile.SCOPE,installation_id=S_ID)
    if record.state!='uninstalled' or record.etag_version!=6 or record.active_revision is not None:
        raise ValueError('S uninstall readback differs')
    return {'outcome':'S_FORMALLY_UNINSTALLED_BEFORE_T_PREPARE','receipt':receipt.response_json,
        'replayed':receipt.replayed,'state':record.state,'etag':record.etag_version}


def lifecycle(profile,action):
    load('uninstall-s' if action=='prepare' else 'prepare-t')
    return profile.lifecycle('t',action)


def configured(profile,action):
    predecessor={'stage':'verify-t','configure':'stage-t','enable':'configure-t'}[action]
    load(predecessor)
    return profile.configure('t',action)


def observe(profile):
    result={'outcome':'T_REPLACEMENT_OBSERVED','s':profile.observe_installation(S_ID)}
    if (T_DIR/'create-result.json').exists():
        result['t']=profile.observe_installation(profile._initial('t')['installationId'])
    return result


def run(action):
    if action not in ACTIONS:raise ValueError('unsupported T replacement action')
    if action != 'observe':
        raise ValueError('historical failed T attempt is sealed; use a0v_t_interruption_recovery.py')
    profile=load_profile()
    if action=='preflight':return preflight(profile)
    if action=='create-t':return create_t(profile)
    if action=='uninstall-s':return uninstall_s(profile)
    if action in {'prepare-t','verify-t'}:return lifecycle(profile,action.removesuffix('-t'))
    if action in {'stage-t','configure-t','enable-t'}:return configured(profile,action.removesuffix('-t'))
    if action=='observe':return observe(profile)
    raise ValueError('unsupported T replacement action')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=ACTIONS);args=parser.parse_args()
    output=STATE/f'{args.action}-result.json'
    if output.exists():raise ValueError(f'immutable {args.action} output exists')
    value=run(args.action);freeze(output,value)
    print(json.dumps(value,ensure_ascii=False,default=str,indent=2))
