"""Private Product API profile; original diagnostic launcher remains unchanged."""
from pathlib import Path
import json
import os
import importlib.util
import hashlib
import sys


def registration_identity_reference(root):
    state=root.parent/'.aos-recovery-20260913/state/registration-deployment'
    identity=state/'registration-main-identity.json';proof=state/'identity-main.json'
    if not identity.exists() and not proof.exists():return None
    if not identity.is_file() or not proof.is_file():raise ValueError('registration deployment evidence incomplete')
    value=json.loads(proof.read_text())
    if (value.get('outcome')!='REGISTRATION_IDENTITY_READ_VERIFIED' or value.get('database')!='aos_meta_head'
            or value.get('role')!='aos_ecommerce_registration_control'
            or value.get('defaultActorDenied') is not True or value.get('negativeTenantDenied') is not True):
        raise ValueError('registration deployment evidence differs')
    return str(identity)


UI_ENV = 'AOS_RUNTIME_UI_READ_CREDENTIAL_FILE'
UI_ORIGINS = {'AOS_EXTENSION_UI_RESOURCE_ORIGIN': 'http://127.0.0.1:18181',
              'AOS_EXTENSION_UI_PARENT_ORIGIN': 'http://127.0.0.1:5173'}


def ui_identity_reference(root):
    state=root.parent/'.aos-recovery-20260913/state/ui-read-deployment'
    identity=state/'ui-read-main-identity.json'; proof=state/'ui-identity-main-proof.json'
    if not identity.exists() and not proof.exists():return None
    if not identity.is_file() or not proof.is_file():raise ValueError('UI identity evidence incomplete')
    value=json.loads(proof.read_text())
    if (value.get('outcome')!='UI_READ_TRANSPORT_IDENTITY_VERIFIED'
        or value.get('database')!='aos_meta_head' or value.get('role')!='aos_ui_read_transport_20260913'
        or value.get('reachableRole')!='aos_ui_read_api' or value.get('positiveSubjectVerified') is not True
        or value.get('absentRequestReturnedNull') is not True
        or value.get('denials')!=['subject-mismatch','negative-tenant','direct-table','host-function']):
        raise ValueError('UI identity proof differs')
    sys.path.insert(0,str(root/'services/aos-api'))
    from aos_api.extension_runtime.ui_read_connection import _identity
    previous=os.environ.get(UI_ENV);os.environ[UI_ENV]=str(identity)
    try:parsed=_identity()
    finally:
        if previous is None:os.environ.pop(UI_ENV,None)
        else:os.environ[UI_ENV]=previous
    if (parsed['role']!=value['role']
        or value.get('identityFileHash')!='sha256:'+hashlib.sha256(identity.read_bytes()).hexdigest()):
        raise ValueError('UI identity digest differs')
    return str(identity)


def ui_identity_preflight():
    from aos_api.extension_runtime.ui_read_connection import ui_read_connection
    from aos_api.tenant_scope import TenantScope
    subject='a0v-ecommerce-growth-1.4-runtime-owner'
    with ui_read_connection(scope=TenantScope('org-org','dev-project'),subject=subject) as conn:
        row=dict(conn.execute('SELECT session_user,current_user,current_database()').fetchone())
        if row!={'session_user':'aos_ui_read_transport_20260913','current_user':'aos_ui_read_api','current_database':'aos_meta_head'}:
            raise ValueError('UI identity current database differs')
        result=conn.execute('SELECT public.extension_ui_read_metadata_a0v_035(%s,%s::uuid) AS result',
            (subject,'00000000-0000-0000-0000-000000000000')).fetchone()
        if result['result'] is not None:raise ValueError('UI missing request differs')
    return row


def load_launcher():
    path=Path(__file__).with_name('a0v_controlled_api.py')
    spec=importlib.util.spec_from_file_location('product_controlled_api',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.BUNDLE_ROOT=(module.ROOT.parent/
        '.aos-recovery-20260915/state/current-ecommerce-package/registry/signed-bundles-current-ecommerce')
    configure=module.configure_environment
    def configure_product():
        configure()
        reference=registration_identity_reference(module.ROOT)
        if reference is None:os.environ.pop('AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE',None)
        else:os.environ['AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE']=reference
        reference=ui_identity_reference(module.ROOT)
        if reference is None:
            for key in (UI_ENV,*UI_ORIGINS):os.environ.pop(key,None)
        else:
            os.environ[UI_ENV]=reference
            os.environ.update(UI_ORIGINS)
    module.configure_environment=configure_product
    preflight=module.preflight
    def product_preflight():
        result=preflight()
        if os.environ.get(UI_ENV):
            result['identities']['uiReadTransport']=ui_identity_preflight()
            result['uiReadResourceOrigins']=dict(UI_ORIGINS)
        return result
    module.preflight=product_preflight
    return module


if __name__=='__main__':
    load_launcher().main()
