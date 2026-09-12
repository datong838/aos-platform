"""Bounded role bindings for the canonical readonly investigation plan."""
import argparse
import json
from pathlib import Path
from a0v_firstchain_capability_activate import run as capabilities
from a0v_firstchain_capability_bindings import prepare
from a0v_firstchain_skill_bindings import bind_items, ROLE_SKILLS, INSTANCE
from a0v_investigation_roles_materialize import ROLE_LOGICS


def run(database):
    capability_result=capabilities(database,ROLE_LOGICS)
    connect,readiness,items=prepare(database,ROLE_LOGICS)
    results=[]
    for instance,logics in ROLE_SKILLS.items():
        if instance==INSTANCE:continue
        selected=[item for item in items if item[0].rsplit('.',1)[1] in logics]
        results.append(bind_items(connect,readiness,selected,instance,database=database))
    return {'database':database,'roleBindings':results,'capabilityBindings':capability_result['bindings'],
        'scope':'readonly investigation role skills only','providerCalls':0,'businessRuns':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--database-name',required=True);parser.add_argument('--apply',action='store_true');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.apply:raise ValueError('EXPLICIT_ROLE_BINDING_APPLY_REQUIRED')
    result=run(args.database_name)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,default=str,indent=2)+'\n')
    print(json.dumps(result,default=str,indent=2))
