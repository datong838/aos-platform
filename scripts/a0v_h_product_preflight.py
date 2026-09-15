"""Current signed Product preflight pinned to F and its real resume receipt."""
import argparse
import importlib.util
import json
import a0v_diagnostic_successor_business as f
from a0v_event_complete_product_api import BUNDLE_ROOT
from a0v_ecommerce_diagnostic_reinstall import STATE as INSTALL_STATE


def load_profile():
    path=f.ROOT/'scripts/a0v_p02_current_preflight.py'
    spec=importlib.util.spec_from_file_location('growth19_product_preflight_base',path)
    p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
    p.BUNDLE_ROOT=BUNDLE_ROOT;p.CURRENT_CREATE=INSTALL_STATE/'h/create-result.json'
    p.CUTOVER_RESUME=f.STATE/'cutover/resume-result.json'
    original_resume=p.require_cutover_resume;original_head=p.require_current_head
    def resume(create,binding,result,row):
        return original_resume(create,binding,result,row,expected_outcome='CURRENT_H_CUTOVER_RESUME')
    def head(create,current,binding,cutover_resumed=False):
        if (create.get('installationId')!=f.G_ID or str(binding.get('generation'))!=f.G_GENERATION
            or current.get('lock_hash')!=f.LOCK or binding.get('config_ref')!=f.CONFIG
            or binding.get('revision')!=6 or not cutover_resumed):
            raise ValueError('fixed resumed H required')
        return original_head(create,current,binding,cutover_resumed)
    p.require_cutover_resume=resume;p.require_current_head=head
    return p


def run(action='preflight'):
    f.setup()
    return load_profile().run(action)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['graph','preflight']);args=parser.parse_args()
    print(json.dumps(run(args.action),ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':main()
