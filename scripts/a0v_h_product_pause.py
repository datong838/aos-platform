"""Exact H Policy5 pause; no mutation of G history or unknown attempts."""
import argparse
import importlib.util
import json
import a0v_diagnostic_successor_business as h
from a0v_h_product_window import policy_profile


def load_profile():
    spec=importlib.util.spec_from_file_location('h_product_pause',h.ROOT/'scripts/a0v_event_complete_g_pause.py')
    p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
    p.g=h;p.policy=policy_profile();p.STATE=h.STATE/'analysis-pause';p.PREFIX='a0v-qyh-h-analysis-pause-20260916'
    return p


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['approve','disable']);args=parser.parse_args()
    print(json.dumps(load_profile().run(args.phase),default=str))
