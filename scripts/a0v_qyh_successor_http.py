#!/usr/bin/env python3
"""Formal external-identity, read-only HTTP entry for the qualified successor."""
import argparse
import json
import os
from pathlib import Path
import sys
import a0v_qyh_successor_installation as successor

ROOT=Path(__file__).resolve().parents[1]
OIDC_PUBLIC_ENV=('AOS_OIDC_ISSUER','AOS_OIDC_ISSUERS','AOS_OIDC_AUDIENCE','AOS_OIDC_JWKS_URL','AOS_OIDC_JWKS_URLS')
LAUNCH_FILES=('scripts/a0v_qyh_successor_http.py','scripts/a0v_qyh_successor_installation.py',
    'scripts/validate_ecommerce_qyh_successor_signing.py','scripts/a0v_qyh_restored_http.py',
    'scripts/a0v_current_preview_http.py')


class SuccessorHttpBlocked(ValueError):
    pass


def require_launch_source(source):
    for file in LAUNCH_FILES:
        path=source/file
        if path.is_symlink() or not path.is_file() or path.read_bytes()!=(ROOT/file).read_bytes():
            raise SuccessorHttpBlocked('SUCCESSOR_LAUNCH_SOURCE_DRIFT')


def prepare(*,build,build_receipt,qualification_receipt,signed_root,trust_roots_file,identity_file,installation_id,source_candidate):
    entry=successor.load_entry()
    # Use the original gate before any credential-file, DB or process action.
    try:
        entry.previous._require_external_oidc()
    except entry.previous.PreviewBlocked:
        raise SuccessorHttpBlocked('EXTERNAL_OIDC_CONFIGURATION_REQUIRED') from None
    original_source=entry.require_api_source_candidate
    def source_checked(path):
        source=original_source(path)
        require_launch_source(source)
        return source
    entry.require_api_source_candidate=source_checked
    def successor_checked(**arguments):
        return successor.run(build=build,build_receipt=build_receipt,
            qualification_receipt=qualification_receipt,signed_root=arguments['bundle_root'],
            trust_roots_file=arguments['trust_roots_file'],identity_file=arguments['identity_file'],
            installation_id=arguments['installation_id'])
    entry.select_current_installation=successor_checked
    try:
        _,original_environment,public=entry.prepare_limited_launch(identity_file=identity_file,
            bundle_root=signed_root,trust_roots_file=trust_roots_file,
            installation_id=installation_id,source_candidate=source_candidate)
    except (entry.RestorationBlocked,successor.SuccessorInstallationBlocked):
        raise SuccessorHttpBlocked('SUCCESSOR_FORMAL_START_PREFLIGHT_REFUSED') from None
    source=Path(original_environment['PYTHONPATH']).parents[1]
    # Allow only the original fixed safety flags, public verifier settings and
    # the exact verified local connection; protected command identities stay out.
    environment={k:v for k,v in original_environment.items()
        if k in {'PATH','LANG','LC_ALL','LC_CTYPE','TZ','TMPDIR'}}
    environment.update(entry.previous.FLAGS)
    environment.update({k:os.environ[k] for k in OIDC_PUBLIC_ENV if k in os.environ})
    from psycopg.conninfo import conninfo_to_dict,make_conninfo
    connection=conninfo_to_dict(original_environment['AOS_DATABASE_URL'])
    connection['options']='-c default_transaction_read_only=on'
    environment.update({'AOS_DATABASE_URL':make_conninfo(**connection),
        'PGPASSFILE':original_environment['PGPASSFILE'],
        'AOS_AUTH_EXTERNAL_ONLY':'1','AOS_AUTH_ALLOW_DEV':'0','AOS_REST_CONNECTOR_MOCK':'0',
        'AOS_BUNDLE_ROOT':original_environment['AOS_BUNDLE_ROOT'],
        'AOS_BUNDLE_TRUST_ROOTS_FILE':original_environment['AOS_BUNDLE_TRUST_ROOTS_FILE'],
        'PYTHONDONTWRITEBYTECODE':'1',
        'PYTHONPATH':os.pathsep.join([str(source/'services/aos-api'),str(source/'scripts')])})
    command=[sys.executable,'-m','uvicorn','a0v_qyh_successor_http:formal_readonly_app',
        '--factory','--host','127.0.0.1','--port',str(entry.LIMITED_PORT),
        '--workers','1','--no-access-log','--log-level','warning']
    return command,environment,{**public,'outcome':'QYH_SUCCESSOR_FORMAL_READONLY_HTTP_PREPARED',
        'databaseReadOnly':True,'mutationRequestsAllowed':False,'apiStarted':False,
        'formalIdentityAuthenticated':False,'runtimeAuthorized':False}


def formal_readonly_app():
    if os.environ.get('AOS_AUTH_EXTERNAL_ONLY')!='1' or os.environ.get('AOS_AUTH_ALLOW_DEV')!='0':
        raise SuccessorHttpBlocked('SUCCESSOR_EXTERNAL_IDENTITY_MODE_REQUIRED')
    from psycopg import connect
    from psycopg.conninfo import conninfo_to_dict
    dsn=os.environ.get('AOS_DATABASE_URL','')
    try:
        parameters=conninfo_to_dict(dsn)
    except Exception:
        raise SuccessorHttpBlocked('SUCCESSOR_DATABASE_READONLY_TARGET_REQUIRED') from None
    expected={'host':'127.0.0.1','port':'18446','dbname':'aos_meta_head',
        'user':'qyh_restored_api_login','options':'-c default_transaction_read_only=on'}
    if parameters!=expected:
        raise SuccessorHttpBlocked('SUCCESSOR_DATABASE_READONLY_TARGET_REQUIRED')
    import a0v_qyh_restored_http as original
    if any(os.environ.get(k)!=v for k,v in original.previous.FLAGS.items()) or os.environ.get('AOS_REST_CONNECTOR_MOCK')!='0':
        raise SuccessorHttpBlocked('SUCCESSOR_WORKER_OR_MIGRATION_FLAGS_DRIFT')
    passfile=original._private(Path(os.environ.get('PGPASSFILE','')))
    try:
        with connect(dsn,passfile=str(passfile)) as connection:
            if connection.execute('SHOW transaction_read_only').fetchone()!=('on',):
                raise SuccessorHttpBlocked('SUCCESSOR_DATABASE_NOT_READONLY')
    except Exception:
        raise SuccessorHttpBlocked('SUCCESSOR_DATABASE_READONLY_CONNECTION_REQUIRED') from None
    from aos_api.main import app
    if Path(sys.modules['aos_api.main'].__file__).resolve()!=Path.cwd()/'services/aos-api/aos_api/main.py':
        raise SuccessorHttpBlocked('SUCCESSOR_API_SOURCE_IMPORT_DRIFT')
    return original.ReadOnlyManagementApp(app)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('build','build-receipt','qualification-receipt','signed-root','trust-roots-file','identity-file','source-candidate'):
        parser.add_argument('--'+arg,type=Path,required=True)
    parser.add_argument('--installation-id',required=True)
    parser.add_argument('--serve',action='store_true')
    args=vars(parser.parse_args());serve=args.pop('serve')
    try:
        command,environment,public=prepare(**args)
    except Exception:
        print(json.dumps({'outcome':'QYH_SUCCESSOR_FORMAL_HTTP_REFUSED','apiStarted':False,'runtimeAuthorized':False}))
        return 1
    print(json.dumps(public,ensure_ascii=False),flush=True)
    if serve:
        os.chdir(Path(environment['PYTHONPATH'].split(os.pathsep)[0]).parents[1])
        os.execve(sys.executable,command,environment)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
