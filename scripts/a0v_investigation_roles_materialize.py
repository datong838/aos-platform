"""Publish the five existing role skills required by the investigation template."""
import argparse
import json
from pathlib import Path
from a0v_formal_text_model_renewal import database_connect
from a0v_firstchain_contract_materialize import require_target
from a0v_firstchain_skill_publication import materialize_contracts

ROLE_LOGICS=('S01','P01','C06','A02','G06')


def run(database):
    connect=database_connect(database)
    return materialize_contracts(connect,require_target=lambda c:require_target(c,database),database=database,
        authority_scope='development-readonly-investigation-role-contracts',logic_ids=ROLE_LOGICS)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--database-name',required=True);parser.add_argument('--apply',action='store_true');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.apply:raise ValueError('EXPLICIT_ROLE_CONTRACT_APPLY_REQUIRED')
    result=run(args.database_name)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,default=str,indent=2)+'\n')
    print(json.dumps(result,default=str,indent=2))
