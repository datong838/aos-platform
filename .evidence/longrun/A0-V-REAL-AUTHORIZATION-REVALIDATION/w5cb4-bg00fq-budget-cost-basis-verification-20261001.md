# BG00FQ verification · 2026-10-01

基线AOS-001031/f9a316d6；Task W5CB4-BG00FQ-20261001。

## 代码与方案复核
新增aip_budget_cost_basis.py：BudgetCostBasisProposal及两种严格来源提议。external_reconciliation_reference仅exact独立账单引用，UsageReceipt类型拒绝；development_risk_proposal绑定exact Provider/model、每次风险占额、期内总风险和总调用次数，不依赖active BudgetPolicy。两种均不接受自报approved/externalUsageProven/usageKnown/activationEligible/amountMinor/approvalRef。
Envelope绑定正租户、next active target、draft/head版本、maker≠checker；账户由budgetId:daily/:pilot派生，币种/有效期间取target，UTC canonical新域hash覆盖全部内容。开发风险每次不得大于daily，总额不得大于monthly，maxRequests×每次风险不超过总额；这些是提议风险预留，不是实际价格或供应商账单上限。
重新解析model_dump树后才输出payload/hash，嵌套修改和model_copy不能绕过校验。新入口target/ref/head/risk严格整数与canonicalidentity；共享BudgetRevisionCreate、VersionedAssetRef、旧preview/request/decision hash和DB禁入门没有修改。
合同不读当前head/成员/Provider，不签发、不持久化、不授权；正式Producer仍必须查询authority并独立checker批准。没有HTTP/Store消费者接线，不能把该合同当预算激活完成。完整账单Owner尚未实现；引用字符串不能自证真实。canonical_payload包含派生字段，后继读者必须重建比较，不得直接忽略accounts/period。

## RED与新鲜验证
- 首RED：模块未实现，pytest collection error，exit2，0.41s。
- 首实现：五文件108 passed/4.52s/exit0。
- 复审补新target禁止隐式转换：5 failed/43 deselected/4.23s/exit1；对应revision字符串、金额浮点/字符串、budgetId空白、hardStop整数。
- 最终：113 passed/7既有warnings/4.46s/exit0；其中新合同48项，未扩大到全后端。

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_budget_cost_basis.py services/aos-api/tests/aip/test_aip_budget_activation_authority.py services/aos-api/tests/aip/test_aip_budget_activation_consumption_precheck_pg.py services/aos-api/tests/aip/test_aip_development_cost_authorization.py services/aos-api/tests/aip/test_aip_model_governance_policy_contracts.py --tb=short --show-capture=no
services/aos-api/.venv/bin/python -m compileall -q services/aos-api/aos_api/aip_budget_cost_basis.py
git diff --check
```
均exit0。专项为纯输入/哈希/错误类型测试，相邻消费PG走隔离库且使用测试Principal；不是当前正式身份、真实账单、审批/激活或业务验收。无UI变化，浏览器不适用。

## 风险与下一波
BG00FR先补canonical持久读回的exact重建，冻结预算来源Producer/独立checker及consumer权限，不复用network域授权；把提议纳入版本化不可变preview/decision和原请求Inquiry，正式外部引用缺Owner时拒绝。开发风险批准保持未知费用及占额，不能写external_usage_proven=true。之后原子写active+唯一消费Receipt和产品接线。
当前真实库未连接/未写/未迁移/未重启，代码a0v123；此前live118为旧证据，独立安全恢复另波。Host/worker/Provider未启，无商城源/旧12Run/手工Run/230 L0/no push。首链仍pending，Goal未改状态，看护方案未部署。
