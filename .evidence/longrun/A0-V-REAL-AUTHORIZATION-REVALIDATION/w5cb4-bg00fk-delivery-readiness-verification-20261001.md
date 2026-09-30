# BG00FK verification · 2026-10-01

基线AOS-001025/m1@24670633；Task W5CB4-BG00FK-20261001。

## 只读身份来源核查
- 本仓.env只输出六键非空presence：AOS_NETWORK_CONSUMER_API_CONFIG、AOS_OIDC_ISSUER、AOS_OIDC_ISSUERS、AOS_OIDC_JWKS_URL、AOS_OIDC_JWKS_URLS、AOS_OIDC_AUDIENCE均false。未输出值，未读取外部部署秘密，不能推断全机所有来源缺失。
- configured_api_consumer仅加载私有endpoint/attempt配置；load_consumer_config为独立OS/DB进程配置；auth.py已验JWT sub→Principal，没有本链后台委托/刷新来源。自然投递合法maker身份仍未证明，不能以函数参数代替。
- CLI serve先preflight；旧preflight仅列a0v120/121/122，漏a0v123投递函数。

## RED与GREEN
RED：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_consumer_config.py -k delivery_function --tb=short --show-capture=no`：6failed/4.79s/exit1，均DID NOT RAISE。
最小修复只给既有_function_gate列表增加claim(text,text,text,uuid)/finish(text,text,text,text,uuid)，均volatile，复用owner/SECURITY DEFINER/search_path/EXECUTE ACL检查。
累计：
```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_consumer_config.py services/aos-api/tests/aip/test_network_consumer_startup.py services/aos-api/tests/aip/test_network_consumer_cli.py services/aos-api/tests/aip/test_network_consumer_connection_pg.py services/aos-api/tests/aip/test_network_delivery_driver_pg.py --tb=short --show-capture=no
```
72passed/18.96s/exit0；7个既有warning；git diff --check exit0。

## 复审与证据边界
六用例在独立PG精确rename/SECURITY INVOKER/PUBLIC EXECUTE后验证阻断，finally恢复原函数/ACL。正常read-only预检保持ready=True/businessAuthorized=False，漂移不创建socket、不新增Receipt。OS/URL为隔离fixture，不是正式身份或生产部署验收。
无新migration、UI改动、真实库写/迁移/重启、自然worker/Host/Provider启动；代码仍a0v123，当前最后实测118为历史现场。无商城源/旧12Run/手工Run/230 L0动作，不push。Goal状态未变，保障方案未部署。

## 下一波BG00FL
转预算合法来源与未知结果恢复：现有create_preview/decide/revoke与Receipt同事务；仅get_preview(previewId)，响应丢失时缺按原请求key/hash找回previewId的只读入口。先复习231-5与原Store/HTTP合同，RED/最小原请求查询，不用POST重发或新key当恢复。外部usage authority仍未接、active预算继续禁入；合法正式身份/安全118到123恢复/八配置Owner/Host/自然首链仍待证。
