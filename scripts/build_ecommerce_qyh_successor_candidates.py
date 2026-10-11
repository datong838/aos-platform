"""Exact independent unsigned successor profile; original source remains immutable."""
import argparse
import importlib.util
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE_PROFILE=ROOT/'.evidence/qyh-four-bundle-successor-20261012/build_profile.py'
DEFAULT_OUTPUT=ROOT.parent/'aos-recovery/qyh-four-bundle-qualified-20261012-r1'

def load_builder(output: Path = DEFAULT_OUTPUT):
    spec=importlib.util.spec_from_file_location('frozen_qyh_successor_source',SOURCE_PROFILE)
    profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)
    profile.OUTPUT=output.resolve()
    builder=profile.load_builder()
    builder.STRIP_INHERITED_SIGNATURES=True
    augment = builder._augment_sbom
    def augment_sbom(bundle, *, sdk_hash, base_config_digest):
        augment(bundle, sdk_hash=sdk_hash, base_config_digest=base_config_digest)
        path = bundle / 'evidence/sbom.json'
        document = json.loads(path.read_text())
        # The original manifest loader requires this field in addition to bomFormat.
        document['format'] = 'CycloneDX'
        path.write_text(json.dumps(document, sort_keys=True, separators=(',', ':')) + '\n')
    builder._augment_sbom = augment_sbom
    return builder


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--context',default='colima-aos-extension');parser.add_argument('--port',type=int,default=18439)
    parser.add_argument('--retain-artifacts',action='store_true');args=parser.parse_args(argv)
    result=load_builder(args.output).build(context=args.context,port=args.port,output=args.output,retain_artifacts=args.retain_artifacts)
    print(json.dumps(result,sort_keys=True,indent=2));return 0

if __name__=='__main__':
    raise SystemExit(main())
