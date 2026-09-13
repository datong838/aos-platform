"""Fixed growth 1.8 / niushop 1.5 qualification profile, no installation effects."""
import hashlib
import importlib.util
import json
from pathlib import Path

FIXTURE = Path(__file__).with_name('fixtures') / 'analyst-workspace-read-probe.json'
FIXTURE_HASH = '88d2e10d98ececd832bf6f4e07cbde53b1c5eae31be8ccb34dfe05cd77a3bdd9'
METHOD = 'analyst_workspace_view_v1'


def _hash(value):
    return 'sha256:' + hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def load_builder():
    path = Path(__file__).with_name('build_ecommerce_runtime_candidates.py')
    spec = importlib.util.spec_from_file_location('ecommerce_ui_private_builder', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    replacements = {
        ('platform.ecommerce.niushop/1.3.0','platform.ecommerce.niushop','1.3.0','ecommerce_niushop'):
        ('platform.ecommerce.niushop/1.5.0','platform.ecommerce.niushop','1.5.0','ecommerce_niushop'),
        ('solution.ecommerce.growth/1.7.0','solution.ecommerce.growth','1.7.0','ecommerce_growth'):
        ('solution.ecommerce.growth/1.8.0','solution.ecommerce.growth','1.8.0','ecommerce_growth'),
    }
    if (any(module.RUNTIME_CASES.count(old) != 1 for old in replacements)
        or module.ALL_CASES[:len(module.RUNTIME_CASES)] != module.RUNTIME_CASES
        or module.EXPECTED_RUNTIME_OPERATION_COUNT != 12):
        raise RuntimeError('base candidate profile drifted')
    module.RUNTIME_CASES = tuple(replacements.get(item,item) for item in module.RUNTIME_CASES)
    module.ALL_CASES = tuple(replacements.get(item,item) for item in module.ALL_CASES)
    module.EXPECTED_RUNTIME_OPERATION_COUNT = 13
    raw = FIXTURE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FIXTURE_HASH:
        raise RuntimeError('reviewed read fixture drifted')
    fixture = json.loads(raw)
    expected_hash = _hash(fixture['expected'])

    async def probe(session):
        result = await session.invoke(METHOD, fixture['payload'])
        if _hash(result) != expected_hash:
            raise RuntimeError('OCI analyst projection differs from reviewed fixture')
        return dict(method=METHOD, fixtureHash='sha256:' + FIXTURE_HASH,
            payloadHash=_hash(fixture['payload']), resultHash=expected_hash,
            caseCount=1, runCount=1, executionAllowed=False, evidence='qualification-fixture-only')

    original = module._qualify_session
    def qualify_session(**kwargs):
        claims = kwargs['contributions']
        methods = [item.get('operationId') if isinstance(item,dict) else getattr(item,'operation_id',None) for item in claims]
        if METHOD in methods:
            return original(**kwargs, probe=probe)
        return original(**kwargs)
    module._qualify_session = qualify_session
    return module


if __name__ == '__main__':
    raise SystemExit(load_builder().main())
