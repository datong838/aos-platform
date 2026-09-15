"""Pause G Policy4 using its actual current receipt and independent intents."""
import argparse
import importlib.util
import json
import a0v_event_complete_successor_business as g
from a0v_g_product_window2 import policy_profile


def load_profile():
    spec=importlib.util.spec_from_file_location('g_window2_pause',g.ROOT/'scripts/a0v_event_complete_g_pause.py')
    p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
    p.policy=policy_profile();p.STATE=g.STATE/'analysis-pause-v2';p.PREFIX='a0v-qyh-g-window2-pause-20260916'
    return p


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['approve','disable']);args=parser.parse_args()
    print(json.dumps(load_profile().run(args.phase),default=str))
