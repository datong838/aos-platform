"""Fresh enable approval only; retained F dispatch expansion is never repeated."""
import argparse
import importlib.util
import json
import a0v_growth19_successor_business as f
from a0v_growth19_product_event_policy_window3 import load_profile as policy_profile


def load_profile():
    spec=importlib.util.spec_from_file_location('f_event_enable_window3',f.ROOT/'scripts/a0v_growth19_product_event_enable.py')
    p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
    p.STATE=f.STATE/'event-enable-v3';p.PREFIX='a0v-qyh-f-event-enable-20260916-v3'
    p.policy_profile=policy_profile
    return p


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['approve-control','enable']);args=parser.parse_args()
    print(json.dumps(load_profile().run(args.phase,f.setup()),ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':main()
