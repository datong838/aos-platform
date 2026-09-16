"""Current signed Product preflight pinned to reinstalled L and its resume Receipt."""
import argparse
import importlib.util
import json

import a0v_l_successor_business as current
from a0v_event_complete_product_api import BUNDLE_ROOT
import a0v_j_uninstall_reinstall_recovery as recovery


def load_profile():
    path = current.ROOT / 'scripts/a0v_p02_current_preflight.py'
    spec = importlib.util.spec_from_file_location('l_product_preflight_base', path)
    profile = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profile)
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.CURRENT_CREATE = recovery.L_DIR / 'create-result.json'
    profile.CUTOVER_RESUME = current.STATE / 'cutover/resume-result.json'
    profile.AUTHORITY_WINDOW_MINUTES = 90
    original_resume = profile.require_cutover_resume
    original_head = profile.require_current_head

    def resume(create, binding, result, row):
        return original_resume(create, binding, result, row,
                               expected_outcome='CURRENT_L_CUTOVER_RESUME')

    def head(create, observed, binding, cutover_resumed=False):
        if (create.get('installationId') != current.L_ID
            or str(binding.get('generation')) != current.L_GENERATION
            or observed.get('lock_hash') != current.LOCK
            or binding.get('config_ref') != current.CONFIG
            or binding.get('revision') != 6 or not cutover_resumed):
            raise ValueError('fixed resumed L required')
        return original_head(create, observed, binding, cutover_resumed)

    profile.require_cutover_resume = resume
    profile.require_current_head = head
    return profile


def run(action='preflight'):
    current.setup()
    return load_profile().run(action)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['graph', 'preflight'])
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
