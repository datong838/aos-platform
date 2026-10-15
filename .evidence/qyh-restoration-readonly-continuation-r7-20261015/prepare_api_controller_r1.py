"""Create fresh control script from inspected prior controller; never execute its API phase."""
from pathlib import Path
R=Path(__file__).resolve().parents[2];E=Path(__file__).resolve().parent
text=(R/'.evidence/qyh-restoration-readonly-continuation-r5-20261015/price_contribution_api_switch.py').read_text()
text=text.replace("HEAD='246d8305332c143bd281cc6aedb013649b81f7d6'", "HEAD='4e038063368cc41fe17aec7b9f6148fa66bd7192'")
text=text.replace('OLD=72678;WEB=76677','OLD=80779;WEB=89803')
text=text.replace('api-source-53d572ba3265d77835a49ee92441c7ce26ea7faa','api-source-246d8305332c143bd281cc6aedb013649b81f7d6')
text=text.replace('price-contribution-api-20261015.json','price-disposition-api-20261015.json')
text=text.replace('price-contribution-before-20261015.json','price-disposition-before-20261015.json')
text=text.replace('price-contribution-live-api-r1.log','price-disposition-live-api-r1.log')
text=text.replace('AOS-002032','AOS-002034')
text=text.replace('1627a39050cc5e8c88f223c56eb870f085091dd9','f036e46c643308651b415179e6e991870dbc26ab')
old=" for name,version in [('qyh-price-contribution-read-admission-20261015','r2'),('qyh-price-contribution-bounded-reader-20261015','r1')]:\n  legal(R/'.evidence'/name,f'code-review-request-{version}.json',f'code-review-result-{version}.json',f'code-review-consumption-{version}.json')"
new=" legal(R/'.evidence/qyh-price-disposition-read-admission-r2-20261015','route-quality-request-r2.json','route-quality-result-r2.json','route-quality-consumption-r2.json')\n legal(R/'.evidence/qyh-price-disposition-bounded-reader-20261015','code-review-request-r2.json','code-review-result-r2.json','code-review-consumption-r2.json')"
assert old in text;text=text.replace(old,new)
text=text.replace('qyh-price-contribution-bounded-reader-20261015/source-verification-r2.json','qyh-price-disposition-bounded-reader-20261015/source-verification-r1.json')
old=" assert listeners(18434)==[WEB] and cwd(WEB)==str(R)"
new=" assert cmd('ps','-p',str(WEB),'-o','command=')==str(Path('/Users/ddt/.workbuddy/binaries/node/versions/22.22.2-2/bin/node'))+' '+str(R/'.evidence/qyh-restoration-readonly-continuation-r6-20261015/price-visual-web-server.mjs')\n assert listeners(18434)==[WEB] and cwd(WEB)==str(R)"
assert old in text;text=text.replace(old,new)
with (E/'price_disposition_api_switch_r1.py').open('x') as stream:stream.write(text)
controller=(R/'.evidence/qyh-restoration-readonly-continuation-r5-20261015/review_controller.py').read_text()
assert 'qyh-restoration-readonly-continuation-r5-20261015' in controller
with (E/'review_controller.py').open('x') as stream:stream.write(controller.replace('qyh-restoration-readonly-continuation-r5-20261015',E.name))
print({'controllerPrepared':True,'apiPhaseExecuted':False})
