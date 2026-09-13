"""Prepare permanent signed growth UI bytes; no Registry or environment mutation."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_successor():
    scripts = Path(__file__).resolve().parent
    module = _load(scripts/'a0v_ecommerce_1_7_registry_successor.py','growth_ui_signed_successor')
    profile = _load(scripts/'build_ecommerce_ui_candidates.py','growth_ui_build_profile')
    helper = module.legacy()
    helper._builder = profile.load_builder
    module.legacy = lambda: helper
    recovery = module.ROOT.parent / '.aos-recovery-20260913'
    module.BUILD = recovery / 'state/growth-ui-1.8-build/candidates'
    module.BUILD_RECEIPT = module.BUILD.parent / 'build-receipt.json'
    module.QUALIFICATION = module.BUILD.parent / 'qualification-receipt.json'
    module.STATE = recovery / 'state/growth-ui-1.8-registry'
    module.OLD_ROOT = recovery / 'state/niushop-1.5-registry/signed-bundles-niushop-1.5'
    module.NEW_ROOT = module.STATE / 'signed-bundles-growth-ui-1.8'
    module.VERSIONS = dict(module.VERSIONS, **{'platform.ecommerce.niushop':'1.5.0','solution.ecommerce.growth':'1.8.0'})
    module.EXPECTED_OLD_COUNT, module.EXPECTED_NEW_COUNT = 13,14
    module.EXTRA_BUILD_PATHS = ('scripts/build_ecommerce_ui_candidates.py','scripts/fixtures/analyst-workspace-read-probe.json')
    fixture = json.loads(profile.FIXTURE.read_bytes())
    expected_probe = dict(method=profile.METHOD,fixtureHash='sha256:'+profile.FIXTURE_HASH,
        payloadHash=profile._hash(fixture['payload']),resultHash=profile._hash(fixture['expected']),
        caseCount=1,runCount=1,executionAllowed=False,evidence='qualification-fixture-only')

    def require_sessions(document):
        counts = {'domain.ecommerce.core':1,'platform.ecommerce.niushop':2,'solution.ecommerce.growth':24}
        sessions = document.get('runtimeSessions') or {}
        if set(sessions) != set(counts):
            raise ValueError('three actual runtime sessions required')
        for key,count in counts.items():
            item = sessions[key]
            expected = dict(registration='exact',heartbeat='alive',cleanup='released',contributionCount=count,heartbeatChecks=2048)
            if any(item.get(k) != v for k,v in expected.items()):
                raise ValueError('runtime qualification incomplete')
        if profile._hash(sessions['solution.ecommerce.growth'].get('readProbe')) != profile._hash(expected_probe):
            raise ValueError('exact OCI read probe required')
    module.require_sessions = require_sessions
    return module


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    module=load_successor()
    sys.path.insert(0,str(module.API))
    helper=module.legacy()
    build=module.verify_inputs(helper)
    result=dict(outcome='PREFLIGHT_GREEN',buildReceiptHash=helper._sha256(module.BUILD_RECEIPT.read_bytes()),
        qualificationReceiptHash=helper._sha256(module.QUALIFICATION.read_bytes()),
        registryPublishCount=0,installationMutationCount=0,environmentMutationCount=0)
    if args.prepare:
        _,hashes=module.signed_tree(helper,build)
        result.update(outcome='GROWTH_UI_1_8_SIGNED_PREPARATION_GREEN',signedRoot=str(module.NEW_ROOT),
                      signedContent=hashes,versionCount=len(hashes))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))


if __name__=='__main__':
    main()
