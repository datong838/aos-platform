# BG00FP verification · 2026-10-01

基线AOS-001030/m1@b1d501e4；Task W5CB4-BG00FP-20261001。范围为来源审计与现有回归，不是新增代码或正式费用授权。

## 可复核事实与结论

| 来源 | 当前实现 | 可以复用 / 不能证明 |
|---|---|---|
| aip_provider_usage_bridge.py::record | selected Provider、providerReceiptId、lineage与逐条usage envelope入库 | 单次调用用量；无稳定budgetAccount/期间覆盖声明 |
| aip_eval_authority_store.py::append_usage_receipt | 同租户lineage存在、provider+receipt去重及内容一致 | 不可变归档，不自动证明外部账户完整性 |
| routers/aip_telemetry_usage.py::_require_runtime | admin/executor/aip_executor角色门；请求携带quality/sourceHash | 不等于独立账单签发者或完整对账证明，不能提升为预算激活来源 |
| aip_budget_reservation_store.py::_usage_authority / _actual_from_usage | exact Receipt hash、Provider/Invocation/result hash、实测整数token、exact价格换算 | 单次结算证据；不是所有预算账户期间无未知费用的证明 |
| aip_development_cost_authorization.py::require_scope | 正租户、exact Provider、model、approvalRef、时效；要求从active策略Owner读取 | 合法延期对账的值合同，不是自带签名/持久审批authority |
| aip_model_governance_policy_store.py::_publish / _require_budget_revision | active BudgetPolicy仍需独立正式批准；draft亦要求active BudgetRevision | 不能用尚不存在的active策略授权第一次BudgetRevision激活，存在bootstrap依赖 |
| aip_budget_reservation_store.py::complete_cost_pending | exact Price授权+实测usage后execution completed；actual_minor仍None、预留不释放 | 可复用后续延期结算语义，不能把unknown费用写0或宣称已settled |
| aip_budget_activation_store.py::precheck_consumption | approved/exact/current/未撤销/空账本后仍EXTERNAL_USAGE_PROOF_REQUIRED | 已批准不等于激活；a0v_110表CHECK(external_usage_proven=false)不可手改 |

231-9§1授权开发成本不阻断研发，但不能把此授权伪装成外部账单完整证明。正确后继是为首次预算准备独立的精确费用来源/风险批准，再由同事务消费；不能以已有active BudgetPolicy作为首次激活前置来源。历史用量保留不变，外部unknown不允许重发或清零。

## 新鲜验证

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_development_cost_authorization.py services/aos-api/tests/aip/test_aip_development_model_binding.py services/aos-api/tests/aip/test_aip_model_governance_policy_contracts.py services/aos-api/tests/aip/test_aip_model_governance_policy_store.py services/aos-api/tests/aip/test_aip_budget_activation_consumption_precheck_pg.py --tb=short --show-capture=no
```
66 passed / 7 warnings / 4.94s / exit0，原process session98020回读完成，未重复启动。
标准conftest建aos_test_*_ti4_test隔离库。合同/模型binding有纯替身；PG消费测试创建Principal对象，历史active fixture是隔离用例。此次结果不证明正式OIDC、真实批准、供应商调用、正式激活或自然首链。未开启旧独立AOS_EXTENSION_PG_TEST用例，未运行其旧schema克隆路径。
开工memory-validate exit0：AOS001030，1485 Delivery /1483 Task /3941 events；7个strong投影CURRENT，个人eventual投影旧warning未写。
查询过程有两个路径/未匹配glob错误，均只读定位、未触发写入；之后以rg --files精确定位。未新写业务代码，因此RED/浏览器新增验收不适用，沿用既有回归验证审计结论。

## 下一波BG00FQ：首次费用来源及审批合同

文件级设计先落plan，再编码：
1. aip_budget_activation_contracts.py及相邻新来源合同：费用依据采用显式类型，区分external reconciliation与development risk approval；保留旧preview原hash和不可变语义，不把任一来源映射成旧external_usage_proven=true。
2. 来源必须由独立正式Producer签发，绑定scope、budget/account/currency/period、current head与target hash、exact Provider/model、批准风险额度/调用量限制、授权有效期、source digest。development分支保持实际费用unknown，不能要求先active BudgetPolicy形成循环；不得从请求中的approvalRef字符串派生权限。
3. 在选择新增schema前复核已有BudgetPreview/Decision及正式network issuer的签发身份、证据撤销、只读Inquiry和exact消费能复用哪些基础设施；不同域身份/权限不能直接共用。冻结需要的最小迁移和独立签发者/consumer ACL，再按RED/隔离PG实现Producer→独立checker→原子BudgetRevision写/唯一Receipt，最后产品接线。
4. 用例：真实隔离PG/TLS-JWT、两名当前成员；cross-tenant/role/revoked/expired/head drift/unknown重复/并发消费/rollback/来源类型混淆；development保留null费用，完整账单证明不得由普通telemetry升级。权限缺失仅阻断当前实例，不造正式账号。
5. 当前实例部署、118→123或后继版本独立安全恢复另波，不能因测试通过迁当前库。

## 保留风险
当前真实库未连接/未写/未迁移/未全栈重启；旧live118只是此前证据，代码head123。Host/worker/Provider未启动、无商城源读取/旧12Run/手工Run/230L0/no push。首次激活/八配置/独立身份/自然首链均未完成。看护方案尚未实施，Goal未改状态。
