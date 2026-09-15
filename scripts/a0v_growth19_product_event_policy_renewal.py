"""Fresh actual event review after the event-binding deployment; failed history retained."""
import argparse
import importlib.util
import json
import a0v_growth19_successor_business as f
from a0v_growth19_product_authority_renewal import load_profile as authority_profile


def load_profile():
    spec=importlib.util.spec_from_file_location('f_event_policy_window2',f.ROOT/'scripts/a0v_growth19_product_event_policy.py')
    p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
    p.STATE=f.STATE/'product-event-v2';p.PREFIX='a0v-qyh-product-event-f-20260916-v2';p.authority=authority_profile()
    return p


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','approve','put']);args=parser.parse_args()
    print(json.dumps(load_profile().run(args.phase,f.setup()),ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':main()
