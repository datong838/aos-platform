"""Private exact Niushop1.5 four-source configuration profile."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT.parent/'.aos-recovery-20260913/state/niushop-1.5-replacement'
INSTALLATION='eda57424-b8cb-401e-a6f7-94220cb4f9ef'


def load_profile():
    path=Path(__file__).with_name('a0v_ecommerce_1_7_configure.py')
    spec=importlib.util.spec_from_file_location('niushop_1_5_configuration_profile',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.BUNDLE_ROOT=ROOT.parent/'.aos-recovery-20260913/state/niushop-1.5-registry/signed-bundles-niushop-1.5'
    def target(recovery=False,*,sleep_recovery=False,niushop_1_4=False):
        if any(flag is not False for flag in (recovery,sleep_recovery,niushop_1_4)):
            raise ValueError('only the exact Niushop1.5 replacement is allowed')
        return INSTALLATION,STATE/'configuration.json','a0v-niushop-1.5-replacement','niushop-1.5'
    module.configuration_target=target
    return module


def run(action):
    if action not in ('preflight','stage','configure','enable'):raise ValueError('unsupported configuration action')
    profile=load_profile()
    if action!='preflight':
        from a0v_niushop_1_5_replacement import freeze_command
        freeze_command(STATE/(action+'-intent.json'),dict(installationId=INSTALLATION,action=action))
    return profile.run(action)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--action',choices=('preflight','stage','configure','enable'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('immutable output already exists')
    result=run(args.action)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as handle:json.dump(result,handle,default=str,indent=2);handle.write('\n')
    print(json.dumps(result,default=str,indent=2))
