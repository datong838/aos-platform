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
    module = _load(scripts / 'a0v_ecommerce_1_7_registry_successor.py', 'niushop_private_registry_successor')
    profile = _load(scripts / 'build_niushop_snapshot_candidates.py', 'niushop_private_build_profile')
    helper = module.legacy()
    helper._builder = profile.load_builder
    module.legacy = lambda: helper
    recovery = module.RECOVERY
    module.BUILD = recovery / 'state/niushop-1.4-build-v1'
    module.BUILD_RECEIPT = recovery / 'logs/niushop-1.4-build-v1.json'
    module.QUALIFICATION = recovery / 'logs/niushop-1.4-qualification-v1.json'
    module.STATE = recovery / 'state/niushop-1.4-registry'
    module.OLD_ROOT = module.NEW_ROOT
    module.NEW_ROOT = module.STATE / 'signed-bundles-niushop-1.4'
    module.VERSIONS = dict(module.VERSIONS, **{'platform.ecommerce.niushop': '1.4.0'})
    module.EXPECTED_OLD_COUNT = 11
    module.EXPECTED_NEW_COUNT = 12
    module.ENV_BACKUP_NAME = 'env-before-niushop-1.4'
    module.ACTOR_PREFIX = 'a0v-niushop-1.4'
    module.SUCCESS_OUTCOME = 'NIUSHOP_1_4_REGISTRY_GREEN'
    module.EXTRA_BUILD_PATHS = ('scripts/build_niushop_snapshot_candidates.py',)
    return module


if __name__ == '__main__':
    load_successor().main()
