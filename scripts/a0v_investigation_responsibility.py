"""Materialize the existing six-role investigation plan through canonical Owners."""
import argparse
import json
from pathlib import Path
from a0v_formal_text_model_renewal import database_connect
from a0v_firstchain_contract_materialize import require_target
from a0v_firstchain_skill_bindings import ROLE_SKILLS
from a0v_formal_text_model import SCOPE
from aos_api.ecommerce_business_investigation_aip_authority import BusinessInvestigationAuthorityMaterializer


def run(database):
    connect=database_connect(database);require_target(connect,database)
    with connect(SCOPE) as conn:
        rows=conn.execute("SELECT instance_id,status,version FROM aip_agent_instance WHERE org_id=%s AND project_id=%s AND instance_id=ANY(%s) ORDER BY instance_id",(*SCOPE.key,list(ROLE_SKILLS))).fetchall()
    if len(rows)!=6 or any(row['status']!='active' for row in rows):
        raise ValueError('INVESTIGATION_SIX_ACTIVE_ROLES_REQUIRED')
    result=BusinessInvestigationAuthorityMaterializer(connect_factory=connect).ensure(SCOPE,actor='a0v-investigation-responsibility-owner')
    stage=result.stage_template;plan=result.responsibility_plan
    return {'database':database,'stageTemplate':stage.model_dump(mode='json',by_alias=True),
        'responsibilityPlan':plan.model_dump(mode='json',by_alias=True),
        'ready':stage.lifecycle.value=='frozen' and plan.lifecycle.value=='frozen' and plan.readiness.value=='ready' and not plan.blockers,
        'providerCalls':0,'businessRuns':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--database-name',required=True);parser.add_argument('--apply',action='store_true');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.apply:raise ValueError('EXPLICIT_RESPONSIBILITY_APPLY_REQUIRED')
    result=run(args.database_name)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,default=str,indent=2)+'\n')
    print(json.dumps({'database':result['database'],'ready':result['ready'],'planId':result['responsibilityPlan']['planId'],'blockers':result['responsibilityPlan']['blockers']},ensure_ascii=False))
