"""Fixed L retirement and M replacement through existing lifecycle owners."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

import a0v_j_uninstall_reinstall_recovery as previous
import a0v_l_product_window2 as product
from a0v_qyh_current_product_event_first_chain import _approve


ROOT=previous.ROOT
STATE=previous.STATE/'recovery-m'
M_DIR=STATE/'m'
N_DIR=STATE/'n'
L_ID='19620ea4-4a36-4cf1-a14a-8b24ee7d9fc3'
L_GENERATION='64742c68-5e71-485b-a3c8-edc20be3d101'
L_LOCK='sha256:15ac55d0ca7098c4df286ad70b6a20e79c327b0ec9c53baceea7cbb7059fcae8'
GROUP='6a402d31-83ad-546c-807f-508c87498ce1'
PREFIX='a0v-event-complete-m-rebuild-20260917'
ACTIONS=('preflight','disable-policy9','disable-policy9-recovered','approve-event-fence','event-fence',
         'inspect-event-drain','approve-event-shrink','event-shrink','settle-l',
         'observe','create-m','uninstall-l','prepare-m','verify-m','stage-m',
         'configure-m','enable-m','reset-m','create-n','uninstall-m','prepare-n',
         'verify-n','stage-n','configure-n','enable-n')
RELEASED_EVENT_ACTIONS=frozenset(('disable-policy9','approve-event-fence','event-fence',
    'approve-event-shrink','event-shrink'))


def profile():
    current=previous.profile()
    current.STATE=STATE
    def initial(label):
        if label=='l':return previous.profile()._initial('l')
        if label not in {'m','n'}:raise ValueError('only fixed L/M/N labels are allowed')
        value=json.loads(({'m':M_DIR,'n':N_DIR}[label]/'create-result.json').read_text())
        identity=value.get('installationId')
        if not isinstance(identity,str) or str(UUID(identity))!=identity:
            raise ValueError('canonical M installation required')
        return value
    current._initial=initial
    return current


def require_interrupted_m(current, *, reset=False):
    snapshot=current.observe_installation(current._initial('m')['installationId'])
    head=snapshot['head'];operations=snapshot['operations']
    expected=('applied',4) if reset else ('approved',5)
    if ((head['state'],head['etag_version'])!=expected
        or head['lock_hash']!=current._initial('m')['lockHash']
        or snapshot['bindings']!=[] or len(snapshot['resources'])!=3
        or any(row['cleanup_state']!='released' or row['observed_release'] is not True
               for row in snapshot['resources'])
        or len(operations)!=2
        or {row['kind'] for row in operations}!={'runtime-apply','runtime-verify'}
        or (reset and not any(row['kind']=='runtime-verify' and row['status']=='accepted'
                              and row['phase']=='accepted' and row['deadline_expired'] is True
                              for row in operations))
        or (not reset and any(row['status'] not in {'succeeded','failed','cancelled'}
                              for row in operations))
        or snapshot['canaryInstallations']!=0):
        raise ValueError('exact resettable or terminal released M interruption required')
    return snapshot


def reset_m(current):
    m=require_interrupted_m(current,reset=True);m_id=str(m['head']['installation_id'])
    current._freeze_or_match(STATE/'m-reset-intent.json',dict(
        installationId=m_id,etag=4,
        verifyOperationId=str(next(row['operation_id'] for row in m['operations']
                                   if row['kind']=='runtime-verify'))))
    activation,_store,lifecycle,_disable,_dependent=current._setup_runtime_plane()
    receipt=lifecycle.reset_preparation(**current.SCOPE,installation_id=m_id,
        actor=activation.ACTOR,roles=activation.ROLES,markings=activation.MARKINGS,
        idempotency_key=PREFIX+'-reset-m',if_match='"4"')
    after=current.observe_installation(m_id);require_interrupted_m(current)
    return dict(outcome='M_INTERRUPTED_PREPARATION_RESET',receipt=receipt.response_json,
                replayed=receipt.replayed,state=after['head']['state'],
                revision=after['head']['etag_version'])


def create_n(current):
    m=require_interrupted_m(current)
    l=current.observe_installation(L_ID);database=database_state(phase='detached')
    if l['head']['state']!='uninstalled':
        raise ValueError('uninstalled L required before clean N')
    if N_DIR.exists():raise ValueError('N intent/result already exists; inspect only')
    helper=current._load('a0v_ecommerce_growth_1_5_registry_successor')
    installer=current._load('a0v_canonical_ecommerce_first_install')
    N_DIR.mkdir(parents=True,exist_ok=False,mode=0o700)
    backup=helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER,state_dir=N_DIR)
    current._freeze(N_DIR/'create-intent.json',dict(label='n',predecessor=None,
        interruptedInstallationId=str(m['head']['installation_id']),
        versions=previous.transaction.VERSIONS,backup=backup,database=database))
    connect=installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER,database_name=helper.DATABASE_NAME)
    result=installer.create_approved_first_installation(connect_factory=connect,
        state_dir=current.TRUST_STATE,
        core_version=previous.transaction.VERSIONS['domain.ecommerce.core'],
        adapter_version=previous.transaction.VERSIONS['platform.ecommerce.niushop'],
        growth_version=previous.transaction.VERSIONS['solution.ecommerce.growth'],
        idempotency_prefix=PREFIX+'-clean-n')
    if result['installationState']!='approved':raise ValueError('N approved clean installation required')
    current._freeze(N_DIR/'create-result.json',result)
    return {'outcome':'N_CLEAN_INSTALLATION_APPROVED_AFTER_M_INTERRUPTION',**result}


def uninstall_m(current):
    m=require_interrupted_m(current);n=current.observe_installation(current._initial('n')['installationId'])
    if (n['head']['state'],n['head']['etag_version'],n['bindings'])!=('approved',3,[]):
        raise ValueError('approved unprepared N required before M uninstall')
    m_id=str(m['head']['installation_id'])
    current._freeze_or_match(STATE/'m-uninstall-intent.json',dict(
        installationId=m_id,etag=5,successorInstallationId=str(n['head']['installation_id'])))
    legacy=current._load('a0v_ecommerce_invalid_baseline_uninstall')
    store,service=legacy._build(current._installation_connection,
        current.TRUST_STATE/'signing/trust-roots.json')
    from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest
    receipt=service.uninstall(**current.SCOPE,installation_id=m_id,
        request=UninstallInstallationRequest(
            reason='M preparation interrupted and resources released; recover through clean N'),
        actor='a0v-ecommerce-growth-1.4-runtime-owner',roles=['admin'],markings=[],
        idempotency_key=PREFIX+'-uninstall-m',if_match='"5"')
    record=store.get_installation(**current.SCOPE,installation_id=m_id)
    if record.state!='uninstalled' or record.active_revision is not None:
        raise ValueError('M uninstall readback differs')
    return dict(outcome='M_INTERRUPTED_INSTALLATION_UNINSTALLED',
                receipt=receipt.response_json,replayed=receipt.replayed,state=record.state,
                successorInstallationId=str(n['head']['installation_id']))


def require_l(current, *, settled=False):
    value=current.observe_installation(L_ID)
    head,binding=value['head'],value['bindings']
    expected_revision=9 if settled else 7
    expected_epoch=5 if settled else 4
    if (str(head['installation_id'])!=L_ID or head['etag_version']!=5
        or head['state']!='active' or head['lock_hash']!=L_LOCK
        or len(binding)!=1 or str(binding[0]['generation'])!=L_GENERATION
        or binding[0]['revision']!=expected_revision
        or binding[0]['execution_epoch']!=expected_epoch
        or binding[0]['enabled'] is not False or binding[0]['operation_fence'] is not True
        or binding[0]['desired_state']!=('disabled' if settled else 'enabled')
        or binding[0]['observed_state']!='unknown'
        or len(value['resources'])!=3
        or any(r['cleanup_state']!='released' or r['observed_release'] is not True
               for r in value['resources'])
        or any(o['status'] not in {'succeeded','failed','cancelled'} for o in value['operations'])
        or value['canaryInstallations']!=0):
        raise ValueError('exact released L state required')
    return value


def database_state(*, phase='expanded'):
    from a0v_formal_text_model_renewal import database_connect
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    with database_connect('aos_meta_head')() as conn:
        routes=[dict(row) for row in conn.execute('''SELECT operation_id,handler_kind,
            installation_id,generation,execution_epoch,operation_fence,revision,cutover_group_revision
            FROM extension_operation_dispatch_binding WHERE org_id='org-org'
            AND project_id='dev-project' AND cutover_group_id=%s ORDER BY operation_id''',(GROUP,)).fetchall()]
        schedule=conn.execute('''SELECT policy_revision,policy_hash,revision,enabled,installation_id,
            generation,execution_epoch,cadence FROM automation_schedule_binding
            WHERE org_id='org-org' AND project_id='dev-project' AND policy_id=%s
            AND policy_revision=9''',(product.policy_profile().POLICY,)).fetchone()
        inflight=dict(conn.execute('''SELECT
          (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
            AND project_id='dev-project' AND installation_id=%s AND generation=%s AND state='running') running,
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
            USING(org_id,project_id,occurrence_id) WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND o.installation_id=%s AND o.generation=%s AND a.status IN ('claimed','unknown')) unresolved''',
            (L_ID,L_GENERATION,L_ID,L_GENERATION)).fetchone())
    if inflight!={'running':0,'unresolved':0}:raise ValueError('L inflight work remains')
    business=set(ECOMMERCE_GROWTH_OPERATIONS);operations={r['operation_id'] for r in routes}
    expected=business|({'ecommerce_growth_event_control'}
                       if phase in {'expanded','disabled','fenced'} else set())
    if len(routes)!=len(expected) or operations!=expected:
        raise ValueError('exact current route group required')
    if schedule is None or str(schedule['installation_id'])!=L_ID or str(schedule['generation'])!=L_GENERATION \
            or schedule['execution_epoch']!=3 or schedule['cadence']!='event' \
            or schedule['revision']!=(1 if phase=='expanded' else 2) \
            or schedule['enabled'] is not (phase=='expanded'):
        raise ValueError('exact Policy9 event binding required')
    if phase=='detached':
        if any(r['handler_kind']!='legacy' or r['installation_id'] is not None
               or r['generation'] is not None or r['operation_fence'] is not True
               or r['cutover_group_revision']!=41 for r in routes):
            raise ValueError('L routes are not detached')
    else:
        if any(r['handler_kind']!='extension' or str(r['installation_id'])!=L_ID
               or str(r['generation'])!=L_GENERATION or r['execution_epoch']!=3
               for r in routes):raise ValueError('exact L routes required')
        group={'expanded':37,'disabled':37,'fenced':38,'business':39}[phase]
        if any(r['cutover_group_revision']!=group for r in routes):
            raise ValueError('exact L route group revision required')
        if phase in {'expanded','disabled'} and any(r['operation_fence'] for r in routes):
            raise ValueError('expanded L routes must be executable before released retirement')
        if phase=='fenced':
            control=next(r for r in routes if r['operation_id']=='ecommerce_growth_event_control')
            if control['operation_fence'] is not True or control['revision']!=2 \
                    or any(r['operation_fence'] for r in routes if r is not control):
                raise ValueError('only the event route may be fenced')
        if phase=='business' and any(r['operation_fence'] for r in routes):
            raise ValueError('business routes changed before runtime disable')
    return {'phase':phase,'routes':routes,'schedule':dict(schedule),'inflight':inflight}


def preflight(current):
    installation=require_l(current)
    database=database_state(phase='expanded')
    return {'outcome':'L_TO_M_REBUILD_PREFLIGHT_GREEN','installation':installation,
            'database':database,'externalEffects':0}


def settle_l(current):
    require_l(current);database_state(phase='business')
    return current.settle_released('l')


def disable_policy9(current,*,recovered=False):
    require_l(current);database_state(phase='expanded')
    policy=product.policy_profile();command=dict(
        schemaVersion='aos.ecommerce.product-event-control-command/v1',
        idempotencyKey=PREFIX+'-disable-policy9',policyRef=policy.load('put')['receiptRef'],
        expectedBindingRevision=1,intent='disable',approvalRef=None)
    intent=STATE/'disable-policy9-intent.json'
    if recovered:
        from a0v_formal_text_model_renewal import database_connect
        original=dict(command);original.pop('approvalRef')
        if not intent.is_file() or json.loads(intent.read_text())!=original:
            raise ValueError('exact failed Policy9 disable intent required')
        with database_connect('aos_meta_head')() as conn:
            receipt_count=conn.execute('''SELECT count(*) AS n FROM ecommerce_product_event_control_receipt
                WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key=%s''',
                (command['idempotencyKey'],)).fetchone()['n']
        if receipt_count!=0:raise ValueError('Policy9 disable outcome requires receipt readback')
        current._freeze_or_match(STATE/'disable-policy9-recovered-precheck.json',
            {'originalIntent':original,'receiptCount':receipt_count,'bindingRevision':1,'enabled':True})
    else:current._freeze_or_match(intent,command)
    from aos_api.ecommerce_growth_runtime_connection import connect_serializable
    from aos_api.ecommerce_released_event_control import (
        ReleasedEventTarget,ReleasedProductEventControlService)
    from aos_api.tenant_scope import TenantScope
    scope=TenantScope('org-org','dev-project');plane=product.current.setup()
    service=ReleasedProductEventControlService(plane.pipeline_control_factory.build_event_control_owner(scope),
        actor=product.current.ACTOR,connect_factory=connect_serializable)
    receipt=service.disable(scope=scope,command=command,target=ReleasedEventTarget(
        installation_id=L_ID,generation=L_GENERATION,execution_epoch=3,runtime_revision=7,
        cutover_group_id=GROUP,cutover_group_revision=37))
    database_state(phase='disabled')
    return {'outcome':'L_POLICY9_RELEASED_DISABLE_GREEN','receipt':receipt}


def event_request(phase):
    current_phase='disabled' if phase=='fence' else 'fenced'
    database_state(phase=current_phase);policy=product.policy_profile()
    return dict(schemaVersion='aos.ecommerce.event-control-dispatch/v1',phase=phase,
        installationRef=dict(installationId=L_ID,revision=5,lockHash=L_LOCK,
            overlayRevision='a0v-canonical-ecommerce-v1'),generation=L_GENERATION,
        executionEpoch=3,runtimeRevision=7,cutoverGroupId=GROUP,
        expectedGroupRevision=37 if phase=='fence' else 38,caseId=policy.CASE,
        schedulePolicyId=policy.POLICY,idempotencyKey=PREFIX+'-event-'+phase)


def load_result(name):
    path=STATE/(name+'-result.json')
    if not path.is_file() or path.stat().st_mode & 0o777!=0o600:
        raise ValueError('private preceding M recovery result required')
    return json.loads(path.read_text())


def event_action(current,action):
    from aos_api.tenant_scope import TenantScope
    plane=product.current.setup();scope=TenantScope('org-org','dev-project')
    if action.startswith('approve-event-'):
        phase=action.removeprefix('approve-event-')
        if phase=='fence':load_result('disable-policy9')
        else:load_result('event-fence');load_result('inspect-event-drain')
        request=event_request(phase);payload=dict(caseId=product.policy_profile().CASE,
            schedulePolicyId=product.policy_profile().POLICY,dispatchIntent=request)
        current._freeze_or_match(STATE/(action+'-intent.json'),payload)
        bundle,approval=_approve('ecommerce_growth_event_dispatch',payload,
            PREFIX+'-event-'+phase+'-approval')
        return {'request':request,'approvalRef':approval,'proposalId':bundle.proposal.id}
    if action=='inspect-event-drain':
        load_result('event-fence');state=database_state(phase='fenced')
        return {'outcome':'L_EVENT_ROUTE_DRAINED','inflight':state['inflight']}
    phase=action.removeprefix('event-');approved=load_result('approve-event-'+phase)
    if event_request(phase)!=approved['request']:
        raise ValueError('approved released event retirement drifted')
    from aos_api.ecommerce_event_control_dispatch_lifecycle import EventControlDispatchRequest
    request=EventControlDispatchRequest.model_validate(
        {**approved['request'],'approvalRef':approved['approvalRef']})
    current._freeze_or_match(STATE/(action+'-intent.json'),request.wire())
    service=plane.pipeline_control_factory.build_event_dispatch_lifecycle(scope)
    receipt=service.transition(scope=scope,request=request,actor=product.current.ACTOR)
    replay=service.transition(scope=scope,request=request,actor=product.current.ACTOR)
    if receipt['receiptId']!=replay['receiptId'] or replay['replayed'] is not True:
        raise ValueError('released event retirement replay differs')
    database_state(phase='fenced' if phase=='fence' else 'business')
    return {'outcome':'L_RELEASED_EVENT_'+phase.upper()+'_GREEN','receipt':receipt,
            'sameKeyReplay':True}


def create_m(current):
    l=require_l(current,settled=True);database=database_state(phase='detached')
    if M_DIR.exists():raise ValueError('M intent/result already exists; inspect only')
    predecessor=current.replacement_ref(l)
    helper=current._load('a0v_ecommerce_growth_1_5_registry_successor')
    installer=current._load('a0v_canonical_ecommerce_first_install')
    M_DIR.mkdir(parents=True,exist_ok=False,mode=0o700)
    backup=helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER,state_dir=M_DIR)
    current._freeze(M_DIR/'create-intent.json',{'label':'m','predecessor':predecessor,
        'versions':previous.transaction.VERSIONS,'backup':backup,'database':database})
    connect=installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER,database_name=helper.DATABASE_NAME)
    result=installer.create_approved_first_installation(connect_factory=connect,
        state_dir=current.TRUST_STATE,
        core_version=previous.transaction.VERSIONS['domain.ecommerce.core'],
        adapter_version=previous.transaction.VERSIONS['platform.ecommerce.niushop'],
        growth_version=previous.transaction.VERSIONS['solution.ecommerce.growth'],
        idempotency_prefix=PREFIX,current_installation_ref=predecessor)
    if result['installationState']!='approved':raise ValueError('M approved replacement required')
    current._freeze(M_DIR/'create-result.json',result)
    return {'outcome':'M_REPLACEMENT_APPROVED',**result}


def uninstall_l(current):
    require_l(current,settled=True);database_state(phase='detached')
    m=current.observe_installation(current._initial('m')['installationId'])
    if (m['head']['state'],m['head']['etag_version'],m['bindings'])!=('approved',3,[]):
        raise ValueError('approved unprepared M required')
    current._freeze_or_match(STATE/'l-uninstall-intent.json',{'installationId':L_ID,
        'etag':5,'generation':L_GENERATION,'bindingRevision':9,
        'successorInstallationId':str(m['head']['installation_id'])})
    legacy=current._load('a0v_ecommerce_invalid_baseline_uninstall')
    store,service=legacy._build(current._installation_connection,
        current.TRUST_STATE/'signing/trust-roots.json')
    from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest
    receipt=service.uninstall(**current.SCOPE,installation_id=L_ID,
        request=UninstallInstallationRequest(reason='L released and detached; replace with approved M'),
        actor='a0v-ecommerce-growth-1.4-runtime-owner',roles=['admin'],markings=[],
        idempotency_key=PREFIX+'-uninstall-l',if_match='"5"')
    record=store.get_installation(**current.SCOPE,installation_id=L_ID)
    if record.state!='uninstalled' or record.active_revision is not None:
        raise ValueError('L uninstall readback differs')
    return {'outcome':'L_UNINSTALLED_FOR_M_REBUILD','receipt':receipt.response_json,
            'replayed':receipt.replayed,'successorInstallationId':str(m['head']['installation_id'])}


def run(action):
    if action not in ACTIONS:raise ValueError('unsupported L/M recovery action')
    if action in RELEASED_EVENT_ACTIONS and (STATE/(action+'-intent.json')).exists():
        raise ValueError('existing released event intent requires read-only inspection')
    current=profile()
    if action=='preflight':return preflight(current)
    if action=='disable-policy9':return disable_policy9(current)
    if action=='disable-policy9-recovered':return disable_policy9(current,recovered=True)
    if action.startswith('approve-event-') or action.startswith('event-') \
            or action=='inspect-event-drain':return event_action(current,action)
    if action=='settle-l':return settle_l(current)
    if action=='create-m':return create_m(current)
    if action=='uninstall-l':return uninstall_l(current)
    if action=='reset-m':return reset_m(current)
    if action=='create-n':return create_n(current)
    if action=='uninstall-m':return uninstall_m(current)
    if action=='observe':
        value={'l':current.observe_installation(L_ID)}
        if (M_DIR/'create-result.json').exists():
            value['m']=current.observe_installation(current._initial('m')['installationId'])
        if (N_DIR/'create-result.json').exists():
            value['n']=current.observe_installation(current._initial('n')['installationId'])
        return value
    phase,label=action.split('-')
    if label not in {'m','n'}:raise ValueError('only M/N lifecycle may continue')
    predecessor=L_ID if label=='m' else current._initial('m')['installationId']
    predecessor_name={'m':'L','n':'M'}[label]
    if current.observe_installation(predecessor)['head']['state']!='uninstalled':
        raise ValueError(f'{predecessor_name} must be uninstalled before {label.upper()} lifecycle')
    if phase in {'prepare','verify'}:return current.lifecycle(label,phase)
    return current.configure(label,phase)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=ACTIONS)
    parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    if args.output.exists():raise ValueError('immutable action result exists; inspect only')
    result=run(args.action);current=profile()
    if args.action not in {'preflight','observe'}:
        state_action='disable-policy9' if args.action=='disable-policy9-recovered' else args.action
        state_result=STATE/(state_action+'-result.json')
        if state_result.exists():
            if json.loads(state_result.read_text())!=result:
                raise ValueError('retained action result differs')
        else:current._freeze(state_result,result)
    current._freeze(args.output,result)
    print(json.dumps(result,ensure_ascii=False,default=str,indent=2))


if __name__=='__main__':main()
