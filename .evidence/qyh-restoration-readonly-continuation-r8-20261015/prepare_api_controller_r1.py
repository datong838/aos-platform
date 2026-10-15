from pathlib import Path
E=Path(__file__).resolve().parent;R=E.parents[1]
text=(R/'.evidence/qyh-restoration-readonly-continuation-r7-20261015/price_disposition_api_switch_r4.py').read_text()
text=text.replace("HEAD='4e038063368cc41fe17aec7b9f6148fa66bd7192'", "HEAD='04092c82f9dcaccf7b23ff6e61d536a9f650aa38'")
text=text.replace('OLD=80779;WEB=89803','OLD=95375;WEB=89803')
text=text.replace('api-source-246d8305332c143bd281cc6aedb013649b81f7d6','api-source-4e038063368cc41fe17aec7b9f6148fa66bd7192')
text=text.replace('price-disposition-api-20261015.json','price-closure-api-20261015.json')
text=text.replace('price-disposition-before-20261015.json','price-closure-before-20261015.json')
text=text.replace('price-disposition-live-api-r1.log','price-closure-live-api-r1.log')
text=text.replace('AOS-002034','AOS-002035')
text=text.replace("legal(R/'.evidence/qyh-price-disposition-read-admission-r2-20261015','route-quality-request-r2.json','route-quality-result-r2.json','route-quality-consumption-r2.json')", "legal(R/'.evidence/qyh-price-closure-read-admission-20261015','route-quality-request-r1.json','route-quality-result-r1.json','route-quality-consumption-r1.json')")
text=text.replace('qyh-price-disposition-bounded-reader-20261015','qyh-price-closure-bounded-reader-20261015')
for stem in ['api-controller-review-request','api-controller-review-result','api-controller-review-consumption','api-controller-review-package']:
    text=text.replace(stem+'-r4',stem+'-r1')
text=text.replace('api-preflight-r3.json','api-preflight-r1.json')
with (E/'price_closure_api_switch_r1.py').open('x') as stream:stream.write(text)
controller=(R/'.evidence/qyh-restoration-readonly-continuation-r7-20261015/review_controller.py').read_text().replace('qyh-restoration-readonly-continuation-r7-20261015',E.name)
with (E/'review_controller.py').open('x') as stream:stream.write(controller)
print({'controllerPrepared':True,'apiPhaseExecuted':False})
