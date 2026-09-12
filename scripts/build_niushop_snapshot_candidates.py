"""Fixed private candidate profile; original builder defaults remain unchanged."""
import importlib.util
from pathlib import Path


def load_builder():
    path=Path(__file__).with_name('build_ecommerce_runtime_candidates.py')
    spec=importlib.util.spec_from_file_location('niushop_snapshot_private_builder',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    old=('platform.ecommerce.niushop/1.3.0','platform.ecommerce.niushop','1.3.0','ecommerce_niushop')
    if module.RUNTIME_CASES.count(old)!=1 or module.ALL_CASES[:len(module.RUNTIME_CASES)]!=module.RUNTIME_CASES:
        raise RuntimeError('base candidate profile drifted')
    new=('platform.ecommerce.niushop/1.4.0','platform.ecommerce.niushop','1.4.0','ecommerce_niushop')
    module.RUNTIME_CASES=tuple(new if item==old else item for item in module.RUNTIME_CASES)
    module.ALL_CASES=tuple(new if item==old else item for item in module.ALL_CASES)
    return module


if __name__=='__main__':
    raise SystemExit(load_builder().main())
