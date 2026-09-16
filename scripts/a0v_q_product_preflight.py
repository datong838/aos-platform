"""Current signed Product preflight pinned to Q and its resume Receipt."""
import argparse
import importlib.util
import json

import a0v_q_successor_business as current
from a0v_event_complete_product_api import BUNDLE_ROOT
import a0v_q_clean_successor as recovery


def load_profile():
    path=current.ROOT/'scripts/a0v_p02_current_preflight.py'
    spec=importlib.util.spec_from_file_location('q_product_preflight_base',path)
    profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)
    profile.BUNDLE_ROOT=BUNDLE_ROOT
    profile.CURRENT_CREATE=recovery.Q_DIR/'create-result.json'
    profile.CUTOVER_RESUME=current.STATE.parent/'cutover/resume-result.json'
    profile.AUTHORITY_WINDOW_MINUTES=90
    original_resume=profile.require_cutover_resume;original_head=profile.require_current_head
    def resume(create,binding,result,row):
        return original_resume(create,binding,result,row,expected_outcome='CURRENT_Q_CUTOVER_RESUME')
    def head(create,observed,binding,cutover_resumed=False):
        if (create.get('installationId')!=current.Q_ID
            or str(binding.get('generation'))!=current.Q_GENERATION
            or observed.get('lock_hash')!=current.LOCK or binding.get('config_ref')!=current.CONFIG
            or binding.get('revision')!=6 or not cutover_resumed):
            raise ValueError('fixed resumed Q required')
        return original_head(create,observed,binding,cutover_resumed)
    profile.require_cutover_resume=resume;profile.require_current_head=head
    return profile


def run(action='preflight'):
    current.setup();return load_profile().run(action)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['graph','preflight']);args=parser.parse_args()
    print(json.dumps(run(args.action),ensure_ascii=False,indent=2,default=str))
