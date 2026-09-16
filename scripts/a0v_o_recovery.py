"""Fail-closed N retirement before creating clean successor O."""
import argparse
import json
from pathlib import Path
from uuid import UUID

import a0v_m_reinstall_recovery as recovery
import a0v_n_product_window as product
from a0v_qyh_current_product_event_first_chain import _approve


ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT.parent/'.aos-recovery-20260916/state/original-transaction-recovery/install/recovery-n/business/successor-o/recovery'
O_DIR=STATE/'o'
P_DIR=STATE/'p'
N_ID='d42cd39a-bc44-403b-a184-c241cae7769e'
N_GENERATION='677046ff-6147-4b3b-905d-9e12964b6581'
LOCK='sha256:15ac55d0ca7098c4df286ad70b6a20e79c327b0ec9c53baceea7cbb7059fcae8'
GROUP='6a402d31-83ad-546c-807f-508c87498ce1'
PREFIX='a0v-qyh-n-to-o-recovery-20260917'
RUN_ID='scr-304a30c952564b38'
SOURCE_REVISION='a84b6c79-8654-48f0-98c2-57d41b067b3d'
ACTIONS=('preflight','disable-policy10','approve-event-fence','event-fence',
  'inspect-event-drain','approve-event-shrink','event-shrink','settle-n','observe',
  'create-o','uninstall-n','prepare-o','verify-o','reset-o','create-p','uninstall-o',
  'prepare-p','verify-p','stage-p','configure-p','enable-p')


def current():
    profile=recovery.profile();profile.STATE=STATE
    inherited=profile._initial
    def initial(label):
        if label=='n':return inherited('n')
        if label not in {'o','p'}:raise ValueError('only fixed N/O/P labels are allowed')
        value=json.loads(({'o':O_DIR,'p':P_DIR}[label]/'create-result.json').read_text())
        identity=value.get('installationId')
        if not isinstance(identity,str) or str(UUID(identity))!=identity:
            raise ValueError('canonical O installation required')
        return value
    profile._initial=initial
    return profile


def require_n(snapshot,*,settled=False):
    head=snapshot['head'];bindings=snapshot['bindings']
    expected=(9,5,'disabled') if settled else (7,4,'enabled')
    if (str(head['installation_id'])!=N_ID or head['etag_version']!=5
        or head['state']!='active' or head['lock_hash']!=LOCK
        or len(bindings)!=1 or str(bindings[0]['generation'])!=N_GENERATION
        or (bindings[0]['revision'],bindings[0]['execution_epoch'],bindings[0]['desired_state'])!=expected
        or bindings[0]['enabled'] is not False or bindings[0]['operation_fence'] is not True
        or bindings[0]['observed_state']!='unknown' or len(snapshot['resources'])!=3
        or any(row['cleanup_state']!='released' or row['observed_release'] is not True
               for row in snapshot['resources'])
        or any(row['status'] not in {'succeeded','failed','cancelled'}
               for row in snapshot['operations']) or snapshot['canaryInstallations']!=0):
        raise ValueError('exact released N state required')
    return snapshot


def database_state(phase):
    from a0v_formal_text_model_renewal import database_connect
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    with database_connect('aos_meta_head')() as conn:
        routes=[dict(row) for row in conn.execute('''SELECT operation_id,handler_kind,
          installation_id,generation,execution_epoch,operation_fence,revision,cutover_group_revision
          FROM extension_operation_dispatch_binding WHERE org_id='org-org' AND project_id='dev-project'
          AND cutover_group_id=%s ORDER BY operation_id''',(GROUP,)).fetchall()]
        binding=conn.execute('''SELECT policy_revision,revision,enabled,installation_id,generation,
          execution_epoch FROM automation_schedule_binding WHERE org_id='org-org' AND project_id='dev-project'
          AND policy_id=%s AND policy_revision=10''',(product.policy_profile().POLICY,)).fetchone()
        schedule=conn.execute("SELECT enabled FROM meta_schedule WHERE org_id='org-org' AND project_id='dev-project' AND id='sch-p02-qyh-controlled-20260913-v1'").fetchone()
        run=conn.execute('''SELECT status,trigger,rows_written,executor_stopped FROM meta_schedule_run
          WHERE org_id='org-org' AND project_id='dev-project' AND id=%s''',(RUN_ID,)).fetchone()
        ingress=conn.execute('''SELECT source_revision FROM ecommerce_ingress_command
          WHERE org_id='org-org' AND project_id='dev-project' AND run_id=%s''',(RUN_ID,)).fetchall()
        counts=dict(conn.execute('''SELECT
          (SELECT count(*) FROM automation_occurrence WHERE org_id='org-org' AND project_id='dev-project'
            AND created_at>='2026-09-16 19:00:00+00') occurrences,
          (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
            AND project_id='dev-project' AND state='running') running,
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
            USING(org_id,project_id,occurrence_id) WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND a.status IN ('claimed','unknown')) unresolved,
          (SELECT count(*) FROM extension_operation_dispatch_binding WHERE org_id='dev-org'
            AND project_id='dev-project') canary''').fetchone())
    business=set(ECOMMERCE_GROWTH_OPERATIONS)
    expected_operations=business if phase in {'shrunk','detached'} else business|{'ecommerce_growth_event_control'}
    if (schedule is None or schedule['enabled'] is not False or run is None
        or dict(run)!={'status':'succeeded','trigger':'cron','rows_written':65,'executor_stopped':True}
        or len(ingress)!=1 or str(ingress[0]['source_revision'])!=SOURCE_REVISION
        or counts!={'occurrences':0,'running':0,'unresolved':0,'canary':0}
        or binding is None or str(binding['installation_id'])!=N_ID
        or str(binding['generation'])!=N_GENERATION or binding['execution_epoch']!=3
        or binding['revision']!=(1 if phase=='initial' else 2)
        or binding['enabled'] is (phase!='initial')
        or len(routes)!=len(expected_operations)
        or {row['operation_id'] for row in routes}!=expected_operations):
        raise ValueError('exact N failed-chain database state required')
    if phase=='detached':
        if any(row['handler_kind']!='legacy' or row['installation_id'] is not None
               or row['generation'] is not None or row['execution_epoch'] is not None
               or row['operation_fence'] is not True or row['cutover_group_revision']!=47
               for row in routes):raise ValueError('exact detached N routes required')
    else:
        group={'initial':43,'disabled':43,'fenced':44,'shrunk':45}[phase]
        if any(row['handler_kind']!='extension' or str(row['installation_id'])!=N_ID
               or str(row['generation'])!=N_GENERATION or row['execution_epoch']!=3
               or row['cutover_group_revision']!=group for row in routes):
            raise ValueError('exact routed N state required')
        if phase=='fenced':
            event=next(row for row in routes if row['operation_id']=='ecommerce_growth_event_control')
            if event['operation_fence'] is not True or any(row['operation_fence'] for row in routes if row is not event):
                raise ValueError('only N event route may be fenced')
        elif any(row['operation_fence'] for row in routes):raise ValueError('unexpected N route fence')
    return {'phase':phase,'routes':routes,'binding':dict(binding),'run':dict(run),
      'sourceRevision':str(ingress[0]['source_revision']),'counts':counts}


def load(name):
    path=STATE/(name+'-result.json')
    if not path.is_file() or path.stat().st_mode&0o777!=0o600:
        raise ValueError('private preceding O recovery result required')
    return json.loads(path.read_text())


def disable_policy10(profile):
    require_n(profile.observe_installation(N_ID));database_state('initial')
    policy=product.policy_profile();command={'schemaVersion':'aos.ecommerce.product-event-control-command/v1',
      'idempotencyKey':PREFIX+'-disable-policy10','policyRef':policy.load('put')['receiptRef'],
      'expectedBindingRevision':1,'intent':'disable','approvalRef':None}
    profile._freeze_or_match(STATE/'disable-policy10-intent.json',command)
    from aos_api.ecommerce_growth_runtime_connection import connect_serializable
    from aos_api.ecommerce_released_event_control import ReleasedEventTarget,ReleasedProductEventControlService
    from aos_api.tenant_scope import TenantScope
    scope=TenantScope('org-org','dev-project');plane=product.current.setup()
    receipt=ReleasedProductEventControlService(
      plane.pipeline_control_factory.build_event_control_owner(scope),actor=product.current.ACTOR,
      connect_factory=connect_serializable).disable(scope=scope,command=command,target=ReleasedEventTarget(
      installation_id=N_ID,generation=N_GENERATION,execution_epoch=3,runtime_revision=7,
      cutover_group_id=GROUP,cutover_group_revision=43))
    database_state('disabled');return {'outcome':'N_POLICY10_RELEASED_DISABLE_GREEN','receipt':receipt}


def event_request(phase):
    database_state('disabled' if phase=='fence' else 'fenced')
    policy=product.policy_profile()
    return {'schemaVersion':'aos.ecommerce.event-control-dispatch/v1','phase':phase,
      'installationRef':{'installationId':N_ID,'revision':5,'lockHash':LOCK,
        'overlayRevision':'a0v-canonical-ecommerce-v1'},'generation':N_GENERATION,
      'executionEpoch':3,'runtimeRevision':7,'cutoverGroupId':GROUP,
      'expectedGroupRevision':43 if phase=='fence' else 44,'caseId':policy.CASE,
      'schedulePolicyId':policy.POLICY,'idempotencyKey':PREFIX+'-event-'+phase}


def event_action(profile,action):
    plane=product.current.setup()
    target=action.removeprefix('approve-').removeprefix('event-')
    if action=='inspect-event-drain':
        load('event-fence');return {'outcome':'N_EVENT_ROUTE_DRAINED','state':database_state('fenced')}
    if action.startswith('approve-'):
        load('disable-policy10' if target=='fence' else 'inspect-event-drain')
        request=event_request(target);payload={'caseId':product.policy_profile().CASE,
          'schedulePolicyId':product.policy_profile().POLICY,'dispatchIntent':request}
        profile._freeze_or_match(STATE/(action+'-intent.json'),payload)
        bundle,ref=_approve('ecommerce_growth_event_dispatch',payload,PREFIX+'-'+target+'-approval')
        return {'request':request,'approvalRef':ref,'proposalId':bundle.proposal.id}
    approved=load('approve-event-'+target)
    if approved['request']!=event_request(target):raise ValueError('N event retirement approval drifted')
    from aos_api.ecommerce_event_control_dispatch_lifecycle import EventControlDispatchRequest
    from aos_api.tenant_scope import TenantScope
    request=EventControlDispatchRequest.model_validate({**approved['request'],'approvalRef':approved['approvalRef']})
    profile._freeze_or_match(STATE/(action+'-intent.json'),request.wire())
    scope=TenantScope('org-org','dev-project')
    receipt=plane.pipeline_control_factory.build_event_dispatch_lifecycle(scope).transition(
      scope=scope,request=request,actor=product.current.ACTOR)
    database_state('fenced' if target=='fence' else 'shrunk')
    return {'outcome':'N_RELEASED_EVENT_'+target.upper()+'_GREEN','receipt':receipt}


def create_o(profile):
    n=require_n(profile.observe_installation(N_ID),settled=True)
    database=database_state('detached')
    if O_DIR.exists():raise ValueError('O intent/result already exists; inspect only')
    predecessor=profile.replacement_ref(n)
    helper=profile._load('a0v_ecommerce_growth_1_5_registry_successor')
    installer=profile._load('a0v_canonical_ecommerce_first_install')
    versions=recovery.previous.transaction.VERSIONS
    O_DIR.mkdir(parents=True,exist_ok=False,mode=0o700)
    backup=helper._database_backup(context=helper.DOCKER_CONTEXT,
      container=helper.DATABASE_CONTAINER,state_dir=O_DIR)
    profile._freeze(O_DIR/'create-intent.json',{'label':'o','predecessor':predecessor,
      'versions':versions,'backup':backup,'database':database})
    connect=installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
      container=helper.DATABASE_CONTAINER,database_name=helper.DATABASE_NAME)
    result=installer.create_approved_first_installation(connect_factory=connect,
      state_dir=profile.TRUST_STATE,
      core_version=versions['domain.ecommerce.core'],
      adapter_version=versions['platform.ecommerce.niushop'],
      growth_version=versions['solution.ecommerce.growth'],
      idempotency_prefix=PREFIX+'-clean-o',current_installation_ref=predecessor)
    if result['installationState']!='approved':
        raise ValueError('O approved replacement required')
    profile._freeze(O_DIR/'create-result.json',result)
    return {'outcome':'O_REPLACEMENT_APPROVED',**result}


def uninstall_n(profile):
    require_n(profile.observe_installation(N_ID),settled=True);database_state('detached')
    o=profile.observe_installation(profile._initial('o')['installationId'])
    if (o['head']['state'],o['head']['etag_version'],o['bindings'])!=('approved',3,[]):
        raise ValueError('approved unprepared O required before N uninstall')
    profile._freeze_or_match(STATE/'n-uninstall-intent.json',{
      'installationId':N_ID,'etag':5,'generation':N_GENERATION,'bindingRevision':9,
      'successorInstallationId':str(o['head']['installation_id'])})
    legacy=profile._load('a0v_ecommerce_invalid_baseline_uninstall')
    store,service=legacy._build(profile._installation_connection,
      profile.TRUST_STATE/'signing/trust-roots.json')
    from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest
    receipt=service.uninstall(**profile.SCOPE,installation_id=N_ID,
      request=UninstallInstallationRequest(
        reason='N disabled and detached after failed natural ingress; replace with approved O'),
      actor='a0v-ecommerce-growth-1.4-runtime-owner',roles=['admin'],markings=[],
      idempotency_key=PREFIX+'-uninstall-n',if_match='"5"')
    record=store.get_installation(**profile.SCOPE,installation_id=N_ID)
    if record.state!='uninstalled' or record.active_revision is not None:
        raise ValueError('N uninstall readback differs')
    return {'outcome':'N_UNINSTALLED_FOR_O_RECOVERY','receipt':receipt.response_json,
      'replayed':receipt.replayed,'state':record.state,
      'successorInstallationId':str(o['head']['installation_id'])}


def require_interrupted_o(profile,*,reset=False):
    snapshot=profile.observe_installation(profile._initial('o')['installationId'])
    head=snapshot['head'];operations=snapshot['operations']
    expected=('applied',4) if reset else ('approved',5)
    if ((head['state'],head['etag_version'])!=expected
        or head['lock_hash']!=profile._initial('o')['lockHash']
        or snapshot['bindings']!=[] or len(snapshot['resources'])!=3
        or any(row['cleanup_state']!='released' or row['observed_release'] is not True
               for row in snapshot['resources'])
        or len(operations)!=2
        or {row['kind'] for row in operations}!={'runtime-apply','runtime-verify'}
        or (reset and not any(row['kind']=='runtime-verify' and row['status']=='accepted'
          and row['phase']=='accepted' and row['deadline_expired'] is True for row in operations))
        or (not reset and any(row['status'] not in {'succeeded','failed','cancelled'}
          for row in operations)) or snapshot['canaryInstallations']!=0):
        raise ValueError('exact resettable or terminal released O interruption required')
    return snapshot


def reset_o(profile):
    o=require_interrupted_o(profile,reset=True);o_id=str(o['head']['installation_id'])
    profile._freeze_or_match(STATE/'o-reset-intent.json',{'installationId':o_id,'etag':4,
      'verifyOperationId':str(next(row['operation_id'] for row in o['operations']
        if row['kind']=='runtime-verify'))})
    activation,_store,lifecycle,_disable,_dependent=profile._setup_runtime_plane()
    receipt=lifecycle.reset_preparation(**profile.SCOPE,installation_id=o_id,
      actor=activation.ACTOR,roles=activation.ROLES,markings=activation.MARKINGS,
      idempotency_key=PREFIX+'-reset-o',if_match='"4"')
    require_interrupted_o(profile)
    return {'outcome':'O_INTERRUPTED_PREPARATION_RESET','receipt':receipt.response_json,
      'replayed':receipt.replayed,'state':'approved','revision':5}


def create_p(profile):
    o=require_interrupted_o(profile);database=database_state('detached')
    if P_DIR.exists():raise ValueError('P intent/result already exists; inspect only')
    helper=profile._load('a0v_ecommerce_growth_1_5_registry_successor')
    installer=profile._load('a0v_canonical_ecommerce_first_install')
    versions=recovery.previous.transaction.VERSIONS
    P_DIR.mkdir(parents=True,exist_ok=False,mode=0o700)
    backup=helper._database_backup(context=helper.DOCKER_CONTEXT,
      container=helper.DATABASE_CONTAINER,state_dir=P_DIR)
    profile._freeze(P_DIR/'create-intent.json',{'label':'p','predecessor':None,
      'interruptedInstallationId':str(o['head']['installation_id']),
      'versions':versions,'backup':backup,'database':database})
    connect=installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
      container=helper.DATABASE_CONTAINER,database_name=helper.DATABASE_NAME)
    result=installer.create_approved_first_installation(connect_factory=connect,
      state_dir=profile.TRUST_STATE,
      core_version=versions['domain.ecommerce.core'],
      adapter_version=versions['platform.ecommerce.niushop'],
      growth_version=versions['solution.ecommerce.growth'],
      idempotency_prefix=PREFIX+'-clean-p')
    if result['installationState']!='approved':raise ValueError('P clean approved install required')
    profile._freeze(P_DIR/'create-result.json',result)
    return {'outcome':'P_CLEAN_INSTALLATION_APPROVED_AFTER_O_INTERRUPTION',**result}


def uninstall_o(profile):
    o=require_interrupted_o(profile);p=profile.observe_installation(profile._initial('p')['installationId'])
    if (p['head']['state'],p['head']['etag_version'],p['bindings'])!=('approved',3,[]):
        raise ValueError('approved unprepared P required before O uninstall')
    o_id=str(o['head']['installation_id'])
    profile._freeze_or_match(STATE/'o-uninstall-intent.json',{'installationId':o_id,
      'etag':5,'successorInstallationId':str(p['head']['installation_id'])})
    legacy=profile._load('a0v_ecommerce_invalid_baseline_uninstall')
    store,service=legacy._build(profile._installation_connection,
      profile.TRUST_STATE/'signing/trust-roots.json')
    from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest
    receipt=service.uninstall(**profile.SCOPE,installation_id=o_id,
      request=UninstallInstallationRequest(
        reason='O replacement verify rejected after N uninstall; recover through clean P'),
      actor='a0v-ecommerce-growth-1.4-runtime-owner',roles=['admin'],markings=[],
      idempotency_key=PREFIX+'-uninstall-o',if_match='"5"')
    record=store.get_installation(**profile.SCOPE,installation_id=o_id)
    if record.state!='uninstalled' or record.active_revision is not None:
        raise ValueError('O uninstall readback differs')
    return {'outcome':'O_INTERRUPTED_INSTALLATION_UNINSTALLED',
      'receipt':receipt.response_json,'replayed':receipt.replayed,'state':record.state,
      'successorInstallationId':str(p['head']['installation_id'])}


def run(action):
    if action not in ACTIONS:raise ValueError('unsupported N to O recovery action')
    profile=current()
    if action=='preflight':
        return {'outcome':'N_TO_O_RECOVERY_PREFLIGHT_GREEN',
          'installation':require_n(profile.observe_installation(N_ID)),
          'database':database_state('initial'),'externalEffects':0}
    if action=='disable-policy10':return disable_policy10(profile)
    if action.startswith('approve-event-') or action.startswith('event-') or action=='inspect-event-drain':
        return event_action(profile,action)
    if action=='settle-n':
        require_n(profile.observe_installation(N_ID));database_state('shrunk')
        return profile.settle_released('n')
    if action=='create-o':return create_o(profile)
    if action=='uninstall-n':return uninstall_n(profile)
    if action=='reset-o':return reset_o(profile)
    if action=='create-p':return create_p(profile)
    if action=='uninstall-o':return uninstall_o(profile)
    if action=='observe':
        value=profile.observe_installation(N_ID)
        phase='detached' if value['bindings'][0]['revision']==9 else 'shrunk'
        result={'n':value,'database':database_state(phase)}
        if (O_DIR/'create-result.json').exists():
            result['o']=profile.observe_installation(profile._initial('o')['installationId'])
        if (P_DIR/'create-result.json').exists():
            result['p']=profile.observe_installation(profile._initial('p')['installationId'])
        return result
    phase,label=action.split('-')
    if label not in {'o','p'}:raise ValueError('only O/P lifecycle may continue')
    predecessor=N_ID if label=='o' else profile._initial('o')['installationId']
    if profile.observe_installation(predecessor)['head']['state']!='uninstalled':
        raise ValueError('predecessor must be formally uninstalled before lifecycle')
    if phase in {'prepare','verify'}:return profile.lifecycle(label,phase)
    return profile.configure(label,phase)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=ACTIONS);args=parser.parse_args()
    STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    result=run(args.action)
    path=STATE/(args.action+'-result.json')
    if not path.exists():current()._freeze(path,result)
    print(json.dumps(result,ensure_ascii=False,default=str,indent=2))
