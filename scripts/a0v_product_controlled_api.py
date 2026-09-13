"""Private Product API profile; original diagnostic launcher remains unchanged."""
from pathlib import Path
import json
import os
import importlib.util


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


def load_launcher():
    path=Path(__file__).with_name('a0v_controlled_api.py')
    spec=importlib.util.spec_from_file_location('product_controlled_api',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.BUNDLE_ROOT=module.ROOT.parent/'.aos-recovery-20260913/state/niushop-1.5-registry/signed-bundles-niushop-1.5'
    configure=module.configure_environment
    def configure_product():
        configure()
        reference=registration_identity_reference(module.ROOT)
        if reference is None:os.environ.pop('AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE',None)
        else:os.environ['AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE']=reference
    module.configure_environment=configure_product
    return module


if __name__=='__main__':
    load_launcher().main()
