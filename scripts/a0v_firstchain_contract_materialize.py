"""Explicit formal first-chain contracts; never executes the business stages."""
import argparse
import json
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect


def require_target(connect, database):
    if database not in {'aos_meta_head', 'aos_text_renewal_20260912'} or not callable(connect):
        raise ValueError('FIRSTCHAIN_EXACT_DATABASE_REQUIRED')
    from a0v_formal_text_model import SCOPE
    with connect(SCOPE) as conn:
        row = conn.execute('SELECT current_database() AS database').fetchone()
        if row is None or row['database'] != database:
            raise ValueError('FIRSTCHAIN_EXACT_DATABASE_MISMATCH')


def run(args):
    connect = database_connect(args.database_name)
    require_target(connect, args.database_name)
    if not args.apply:
        return {'outcome': 'FIRSTCHAIN_CONTRACT_PLAN_ONLY', 'providerCalls': 0, 'databaseWrites': 0}
    from a0v_firstchain_skill_publication import materialize_contracts
    return materialize_contracts(connect,
        require_target=lambda factory: require_target(factory, args.database_name),
        database=args.database_name, authority_scope='development-firstchain-contract-materialization')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database-name', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = run(args)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))
