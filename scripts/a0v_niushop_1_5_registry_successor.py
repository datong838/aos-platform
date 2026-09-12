"""Fixed append-only Niushop successor using the existing registry authority."""
import importlib.util
from pathlib import Path


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_successor():
    scripts = Path(__file__).resolve().parent
    module = _load(scripts / 'a0v_ecommerce_1_7_registry_successor.py', 'niushop_product_registry_successor')
    profile = _load(scripts / 'build_niushop_product_candidates.py', 'niushop_private_build_profile')
    helper = module.legacy()
    helper._builder = profile.load_builder
    module.legacy = lambda: helper
    recovery = module.ROOT.parent / '.aos-recovery-20260913'
    module.BUILD = recovery / 'state/niushop-1.5-build-v1'
    module.BUILD_RECEIPT = recovery / 'logs/niushop-1.5-build-v1.json'
    module.QUALIFICATION = recovery / 'logs/niushop-1.5-qualification-v1.json'
    module.STATE = recovery / 'state/niushop-1.5-registry'
    module.OLD_ROOT = module.RECOVERY / 'state/niushop-1.4-registry/signed-bundles-niushop-1.4'
    module.NEW_ROOT = module.STATE / 'signed-bundles-niushop-1.5'
    module.VERSIONS = dict(module.VERSIONS, **{'platform.ecommerce.niushop': '1.5.0'})
    module.EXPECTED_OLD_COUNT = 12
    module.EXPECTED_NEW_COUNT = 13
    module.ENV_BACKUP_NAME = 'env-before-niushop-1.5'
    module.ACTOR_PREFIX = 'a0v-niushop-1.5'
    module.SUCCESS_OUTCOME = 'NIUSHOP_1_5_REGISTRY_GREEN'
    module.EXTRA_BUILD_PATHS = ('scripts/build_niushop_product_candidates.py',)
    return module


if __name__ == '__main__':
    load_successor().main()
