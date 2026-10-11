"""Read-only exact signing-input validation; never creates a publisher identity."""
import argparse
import importlib.util
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSIONS={'domain.ecommerce.core':'1.4.4','platform.ecommerce.niushop':'1.23.3','solution.ecommerce.growth':'1.13.1','solution.ecommerce.operations-base':'1.2.2'}

def _qualification_profile():
    spec=importlib.util.spec_from_file_location('qyh_successor_qualified_inputs',ROOT/'scripts/sign_ecommerce_growth_1_13_candidates.py')
    profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile);profile.VERSIONS=dict(VERSIONS)
    return profile

def load_signer():
    signer=_qualification_profile().load_signer()
    signer.PROFILE=ROOT/'scripts/build_ecommerce_qyh_successor_candidates.py'
    return signer

def validate_inputs(*,build:Path,build_receipt:Path,qualification_receipt:Path,state:Path):
    _qualification_profile().validate_qualification(build=build,build_receipt=build_receipt,qualification_receipt=qualification_receipt)
    _,receipt=load_signer().validate_build(build=build,receipt_path=build_receipt,state=state)
    return {'outcome':'QYH_SUCCESSOR_SIGNING_INPUTS_VALID_NO_SIGN','versions':dict(VERSIONS),'sourceGitHead':receipt['gitHead'],'outputTreeHash':receipt['outputTreeHash'],'publisherIdentityConnected':False,'formalRuntimeReady':False,'effects':receipt['effects']}

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--build-dir',type=Path,required=True);parser.add_argument('--build-receipt',type=Path,required=True)
    parser.add_argument('--qualification-receipt',type=Path,required=True);parser.add_argument('--state-dir',type=Path,required=True)
    args=parser.parse_args(argv)
    result=validate_inputs(build=args.build_dir,build_receipt=args.build_receipt,qualification_receipt=args.qualification_receipt,state=args.state_dir)
    print(json.dumps(result,sort_keys=True));return 0

if __name__=='__main__':
    raise SystemExit(main())
