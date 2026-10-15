"""Prepare an isolated rendering of the unchanged component and committed CSS."""
from pathlib import Path
import hashlib, json, os, subprocess, sys

R = Path.cwd()
E = R/'.evidence/qyh-price-visual-filter-sizing-20261015'
sys.path.insert(0,str(R/'scripts/memory'))
import memoryctl as m
sys.path.insert(0,str(R/'scripts/long-task-watchdog'))
import aos_review as g
assert m.load_authority(m.DEFAULT_PATHS)['project_revision']=='AOS-002033'
lease=next(x for x in m.load_leases(m.DEFAULT_PATHS)['leases'] if x['task_id']==E.name)
assert lease['owner']=='codex-01a13484-f019-7d82-94ce-812396db9124'
req=json.loads((E/'plan-review-request-r2.json').read_text())
env=json.loads((E/'plan-review-result-r2.json').read_text())
transport=json.loads((E/'plan-review-result-r2.transport.json').read_text())
assert g.consumption_record(req,env,transport,env['runner_sha256'])==json.loads((E/'plan-review-consumption-r2.json').read_text())
report=json.loads((E/'baseline-source-r1.json').read_text())
root=Path(report['source'])
for name,sha in report['manifest'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha
web=root/'apps/web'
modules=web/'node_modules'
assert not modules.exists() and not modules.is_symlink()
modules.symlink_to(R/'apps/web/node_modules',target_is_directory=True)
test=(root/'apps/web/src/components/workshop/PriceGovernancePage.test.tsx').read_text()
constants=test.split('const ids =',1)[1].split('const proposalBundle',1)[0]
constants=('const ids ='+constants).replace('"org-org"','"dev-org"').replace('"dev-project"','"fixture-project"')
entry='''import React from 'react';
import {createRoot} from 'react-dom/client';
import type {PriceGovernanceViewResponse,PriceObservation} from './src/api/ecommerceWorkshop';
import {PriceGovernancePage} from './src/components/workshop/PriceGovernancePage';
import './src/styles.css';
'''+constants+'''
const mode=new URLSearchParams(location.search).get('case') ?? 'empty';
if(!['empty','rich'].includes(mode))throw new Error('Unknown isolated scenario');
const reject=async()=>{throw new Error('ISOLATED_ACTION_FORBIDDEN');};
const client={getPriceGovernanceView:async()=>structuredClone(mode==='rich'?rich:blocked)};
const actions={createProposal:reject,createReplacementProposal:reject,withdraw:reject,timeline:reject};
const primary=new URLSearchParams(location.search).get('primary')!=='0';
createRoot(document.getElementById('root')!).render(<div className={'p-app'+(primary?' is-workshop-primary-visual':'')}>
 <div className="p-nav-global" aria-hidden="true">隔离</div>
 <div className="p-main"><header className="topbar"><strong>隔离只读布局夹具 · 非经营证据</strong></header>
 <div className="layout"><aside className="aside">合成租户 dev-org/fixture-project</aside><main className="content">
 <section className="ecommerce-workshop-shell" data-module-id="ecommerce.price-governance"><main id="ecommerce-workshop-main">
 <PriceGovernancePage client={client} actions={actions}/>
 </main></section></main></div></div></div>);
'''
files={'layout-fixture.tsx':entry,'layout-fixture.html':'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>隔离价格布局验证</title><div id="root"></div><script type="module" src="/layout-fixture.tsx"></script></html>'}
for name,body in files.items():
 with (web/name).open('x') as f:f.write(body)
os.chmod(web/'layout-fixture.tsx',0o600)
with (E/'fixture-inputs-r1.json').open('x') as f:json.dump({'head':report['head'],'source':str(root),'fixture':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in files.items()},'originalComponentUnchanged':True,'originalCSSUnchanged':True,'noOriginalApi':True,'actions':'all throw','tenant':'dev-org/fixture-project'},f,indent=2)
print('Isolated original component fixture prepared; no server started')
