"""Private Product API profile; original diagnostic launcher remains unchanged."""
from pathlib import Path
import importlib.util


def load_launcher():
    path=Path(__file__).with_name('a0v_controlled_api.py')
    spec=importlib.util.spec_from_file_location('product_controlled_api',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.BUNDLE_ROOT=module.ROOT.parent/'.aos-recovery-20260913/state/niushop-1.5-registry/signed-bundles-niushop-1.5'
    return module


if __name__=='__main__':
    load_launcher().main()
