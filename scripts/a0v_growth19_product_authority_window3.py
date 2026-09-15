"""Third F authority window, anchored to the retained second exact references."""
import argparse
import importlib.util
import json
import a0v_growth19_successor_business as f


def load_profile():
    spec=importlib.util.spec_from_file_location('f_authority_window3',f.ROOT/'scripts/a0v_growth19_product_authority.py')
    p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
    old_state=f.STATE/'product-authority-v2'
    def predecessor(phase):
        path=old_state/(phase+'-result.json')
        if not path.is_file() or path.stat().st_mode & 0o777!=0o600:raise ValueError('private v1 predecessor required')
        return json.loads(path.read_text())['ref']
    p.previous_reference=predecessor;p.STATE=f.STATE/'product-authority-v3';p.PREFIX='a0v-p02-f-authority-20260916-v3'
    return p


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','selection','control','binding']);args=parser.parse_args()
    print(json.dumps(load_profile().run(args.phase,f.setup()),ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':main()
