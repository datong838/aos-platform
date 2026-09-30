# BG00FL verification · 2026-10-01

基线AOS-001026/m1@e9035cd1，Task W5CB4-BG00FL-20261001。只读找回原预算预览，不激活预算。

## 命令与新鲜结果
- RED：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_budget_preview_inquiry_pg.py --tb=short --show-capture=no`，5failed/4.49s/exit1（无inquire_preview）。最小实现后5passed/4.32s/exit0。
- 补HTTP真实TLS/JWT、原PG、过期/隔离/只读工厂及503负例后首次累计42passed/1failed/26.87s/exit1。失败是测试错期望dev403；auth.py原行为在AOS_AUTH_ALLOW_DEV=0提前401 AUTH_DEV_DISABLED，核查后仅修测试及方案说明。
- 最终累计：
```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_budget_preview_inquiry_pg.py services/aos-api/tests/aip/test_aip_budget_activation_store_pg.py services/aos-api/tests/aip/test_aip_budget_activation_consumption_precheck_pg.py services/aos-api/tests/aip/test_aip_budget_activation_authority.py services/aos-api/tests/aip/test_aip_budget_activation_exposure_pg.py services/aos-api/tests/aip/test_aip_budget_api.py --tb=short --show-capture=no
```
43passed/26.84s/exit0；新专项10项纳入；7既有warning。git diff --check exit0。

## 方案/代码复审
1. 原preview写路径仅把原四项canonical request hash抽到纯helper，原输入、事务、Receipt与幂等合同不变；新inquire共用helper，不调用create/_replay/写事务/advisory lock。
2. 只读连接必须aos_runtime/双scope/READ ONLY/repeatable-read。当前maker成员门沿已有get_preview权限，不放宽历史读取。Receipt按operation=preview+原key+actor+scope查，再验preview哈希/target/hash/原checker/head/actor绑定。
3. missing为unresolved；同key输入漂移或权威不一致为conflict；observed仅返回previewId/hash，activationEligible=false。过期不抹历史且不获得新权限。读失败503，不当未提交；错误不泄露底层连接细节。
4. HTTP沿已有网络inquiry的POST JSON只读查询语义，独立路径/完整原请求体避免URL业务参数；响应202/200/409均no-store。外部模式dev401，缺成员403，PG不可用503。不是重发原创建POST。
5. 实際TLS/JWT/隔离PG验证HTTP；未替换Store或Principal依赖。五张预算表计数前后不变，非maker与dev-org隔离；故障注入只验证查询异常，不能算正式身份/业务成功。
6. 外部usage权威仍未接，原预算active拒绝累计通过；新查询不调用Provider/当前真实库、不创建批准、Receipt或新预算。

## 未完成与下一波BG00FM
decision/revoke响应丢失仍缺原请求只读Receipt恢复；下一波复习原哈希/角色/历史引用，补精确查询，不重发、不换key。产品表单/正式身份/外部usage/原子激活/八配置Owner/Host/自然首链继续pending。
无新migration/生产重启/UI变更/浏览器通过声明。当前真库只读，代码a0v123，最后实测118为旧现场；118到123安全恢复另波。Host/worker/Provider未启，无商城源/旧12Run/手工Run/230 L0动作，不push。Goal状态未改，保障方案未部署。
