"""Retire exact known instances through the normal uninstall authority."""
import argparse
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT.parent / '.aos-recovery-20260912'
INSTALLATION = '3d267738-ba0a-49ef-812b-d6b72d3374fd'
ACTOR = 'a0v-ecommerce-growth-1.4-runtime-owner'


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/f'{name}.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--reinstall-generation', action='store_true')
    group.add_argument('--configured-1-7', action='store_true')
    args = parser.parse_args()
    installation = 'efc4e640-1b15-403f-9d06-4c6d1a5330a7' if args.reinstall_generation else INSTALLATION
    etag = '"5"' if args.reinstall_generation else '"7"'
    key = 'a0v-ecommerce-1.6-reinstall-never-enabled-retire-v1' if args.reinstall_generation else 'a0v-ecommerce-1.6-never-enabled-retire-v1'
    if args.configured_1_7:
        installation='e42e042b-1fe7-4cfa-bb83-469ff256081d'
        etag='"5"'
        key='a0v-ecommerce-1.7-configured-disabled-retire-v1'
    if not args.apply: raise ValueError('explicit retirement required')
    host = load('a0v_ecommerce_runtime_host')
    credential_path = RECOVERY/'state/installation-control-identity.json'
    if credential_path.stat().st_mode & 0o777 != 0o600:
        raise ValueError('private installation identity required')
    credential = json.loads(credential_path.read_text())
    if credential['role'] != 'aos_a0v_installation_20260912':
        raise ValueError('exact installation identity required')
    import psycopg
    from psycopg.rows import dict_row
    @contextmanager
    def connect():
        with psycopg.connect(host='127.0.0.1',port=18435,dbname='aos_meta_head',
                user=credential['role'],password=credential['password'],row_factory=dict_row) as conn:
            if conn.info.dbname != 'aos_meta_head': raise ValueError('isolated database required')
            conn.execute('SET ROLE aos_app')
            conn.commit()
            yield conn
    legacy = load('a0v_ecommerce_invalid_baseline_uninstall')
    trust = ROOT.parent/'.aos-recovery-20260910/state/a0v-canonical-ecommerce-first-install/signing/trust-roots.json'
    store, service = legacy._build(connect, trust)
    from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest
    before = store.get_installation(org_id='org-org', project_id='dev-project', installation_id=installation)
    command = dict(installation_id=installation,
        request=UninstallInstallationRequest(reason='Retire exact disabled generation after confirmed resource cleanup'),
        org_id='org-org',project_id='dev-project',actor=ACTOR,roles=['admin'],markings=[],
        idempotency_key=key,if_match=etag)
    first = service.uninstall(**command)
    replay = service.uninstall(**command)
    after = store.get_installation(org_id='org-org', project_id='dev-project', installation_id=installation)
    if after.state != 'uninstalled' or after.active_revision is not None:
        raise ValueError('retirement readback differs')
    result = dict(installationId=installation,before=dict(state=before.state,revision=before.current_revision),
        after=dict(state=after.state,revision=after.current_revision),
        firstReplayed=first.replayed,secondReplayed=replay.replayed,receipt=first.response_json)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,default=str,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='receipt'},indent=2))


if __name__ == '__main__': main()
