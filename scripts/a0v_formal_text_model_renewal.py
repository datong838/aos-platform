"""Explicit, journal-backed renewal of the existing development text authority."""
import argparse
import json
import os
from pathlib import Path
import sys
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/aos-api'))
os.environ['AOS_DOTENV_DISABLED'] = '1'


def database_connect(database_name):
    from a0v_real_text_provider_health import _load_first_installer, _scoped_factory
    if database_name not in {'aos_meta_head', 'aos_text_renewal_20260912'}:
        raise ValueError('TEXT_RENEWAL_DATABASE_NOT_ALLOWED')
    base_connect = _load_first_installer().container_database_connect_factory(
        context='colima-aos-extension', container='aos-a0v-recovery-pg',
        database_name='aos_meta_head')
    if database_name == 'aos_meta_head':
        connect = base_connect
    else:
        # Reuse the already verified local container endpoint, with an exact
        # dedicated clone name. Never relax the first-installer target guard.
        import psycopg
        from psycopg.rows import dict_row
        with base_connect() as conn:
            parameters = conn.info.get_parameters()
            parameters['password'] = conn.info.password
        parameters['dbname'] = 'aos_text_renewal_20260912'
        @contextmanager
        def connect():
            with psycopg.connect(**parameters, row_factory=dict_row) as conn:
                if conn.info.dbname != database_name:
                    raise ValueError('TEXT_RENEWAL_DATABASE_DRIFT')
                yield conn
    return _scoped_factory(connect)


def run(args):
    from a0v_formal_text_model import freeze_plan, apply_plan
    factory = database_connect(args.database_name)
    plan = freeze_plan(factory, args.state_dir, evidence_dir=args.evidence_dir, renew=True)
    if not args.apply:
        return {'outcome': 'TEXT_RENEWAL_PLAN_FROZEN', 'planHash': plan['planHash'],
                'providerCalls': 0, 'databaseWrites': 0}
    return apply_plan(factory, plan)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database-name', required=True)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    result = run(args)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))
