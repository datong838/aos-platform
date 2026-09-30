# BG00FM verification · 2026-10-01

基线 AOS-001027 / m1@2ca78ed1；Task W5CB4-BG00FM-20261001。

## 命令与结果
- 原专项 RED：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_budget_review_inquiry_pg.py --tb=short --show-capture=no`，11failed/5.02s，缺inquire_decision/inquire_revocation；实现后同命令11passed/4.88s/exit0。
- 首次累计误写 test_budget_consumption_precheck_pg.py，pytest exit4、无测试执行；按实际路径更正，未更改业务逻辑规避失败。
- 最终累计：
```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_budget_review_inquiry_pg.py services/aos-api/tests/aip/test_budget_preview_inquiry_pg.py services/aos-api/tests/aip/test_aip_budget_activation_store_pg.py services/aos-api/tests/aip/test_aip_budget_activation_consumption_precheck_pg.py services/aos-api/tests/aip/test_aip_budget_activation_exposure_pg.py services/aos-api/tests/aip/test_aip_budget_active_db_gate_pg.py services/aos-api/tests/aip/test_aip_budget_api.py --tb=short --show-capture=no
```
44passed/29.34s/exit0，7既有warning；本波18项新专项。git diff --check exit0。

## 方案与代码复审
- 决定/撤销写路径仅共用等价原request hash helper；原输入、角色、事务、Receipt和重放门不变。
- 新查询仅connect_read_only、SELECT；共用上一波同条件身份检查：aos_runtime、双scope、READ ONLY、repeatable read。原actor当前owner/admin门，Receipt按scope/operation/key/actor过滤，再核对原请求hash及最小result_ref。
- 决定绑定preview、decision、checker；撤销绑定decision、reason、actor且来源必须approved。关联preview/target hash、maker/checker独立性及同租户引用回读。不可变历史查询不重新创造当前授权；已撤销批准仍可观察历史，activationEligible始终false。
- HTTP独立inquiry路径沿原认证/原body/key；200/202/409均no-store；缺行unresolved不构成重发许可；DB故障503，不冒充missing，不回传连接细节。响应只含最小ID及false，无reason/actor等详情。
- 新18项在真实隔离PG验证原批准/拒绝/撤销Receipt、原输入漂移、未知key、非原actor、跨scope、成员撤销、只读身份/可写连接拒绝及已撤销批准历史。HTTP使用真实TLS/JWT+独立FastAPI，不替换Store/Principal；五表计数查询前后不变。故障注入只证明异常合同，不作为正式身份/业务完成证据。
- 无新migration、UI修改、生产重启或浏览器通过声明；当前真实库未写，Host/worker/Provider未启，不读商城源、不回放旧12Run、不手工Run、230 L0挂起、不push。代码a0v123，最后live118为旧现场，正式118→123恢复仍需独立安全波。

## 未完成/下一波
BG00FN复习预算配置产品入口与服务端原请求保留，推进原身份/原key对账的产品链；不得localStorage权威、离线写队列或刷新换key重发。外部usage、原子激活、正式身份、八配置Owner、Host与自然首链仍pending。Goal状态未改；看护方案尚未实施。
