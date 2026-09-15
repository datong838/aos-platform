"""Fresh actual event review after the event-binding deployment; failed history retained."""
import argparse
import importlib.util
import json
import a0v_growth19_successor_business as f
from a0v_growth19_product_authority_window3 import load_profile as authority_profile


def load_profile():
    spec=importlib.util.spec_from_file_location('f_event_policy_window3',f.ROOT/'scripts/a0v_growth19_product_event_policy.py')
    p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
    p.STATE=f.STATE/'product-event-v3';p.PREFIX='a0v-qyh-product-event-f-20260916-v3';p.authority=authority_profile()
    def predecessor():
        state=f.STATE/'product-event-v2'
        for phase in ('prepare','put'):
            path=state/(phase+'-result.json')
            if not path.is_file() or path.stat().st_mode & 0o777!=0o600:
                raise ValueError('private successful Policy predecessor required')
        previous=json.loads((state/'prepare-result.json').read_text())['command']['policy']
        receipt=json.loads((state/'put-result.json').read_text())['receiptRef']
        if (receipt['resourceId']!=p.POLICY or receipt['revision']!=previous['revision']
            or receipt['contentHash']!=previous['contentHash']):
            raise ValueError('Policy predecessor Receipt differs')
        return dict(previous,tenant=dict(orgId='org-org',projectId='dev-project'))
    p.previous_policy_payload=predecessor
    return p


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','approve','put']);args=parser.parse_args()
    print(json.dumps(load_profile().run(args.phase,f.setup()),ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':main()
