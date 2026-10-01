# BG00GH 当前费用价格准入 verification

基线AOS-001048/50dd4f4b/a0v128。本波通过代码审计发现并真实隔离PG复现：Model current-price门存在，但新hold/submit共用require_cost_risk缺current price head核验，历史active revision在撤回后仍可过门。

## RED和最小修复
- 新tests/aip/test_budget_configuration_runtime_pg.py全部使用真实HTTPS JWT批准、受限caller预算消费与GE派生配置；不使用price_for、不直接插active price。
- 两个RED分别new_hold=True/False，正式store发布suspended revision2后，旧引用DID NOT RAISE BudgetReservationBlocked，exit1，/tmp/aos-gh-red.log。
- aip_budget_cost_runtime.py仅新增7行：tenant+price id的head FOR SHARE及current_revision精确核对。锁至新hold/submit事务结束；旧SERIALIZABLE快照见更新必须中止；不透明重试。
- 未改_price_authority：它也服务历史deferred reconciliation，不能因当前撤回拒绝合法历史对账。非cost预算仍走原路径。

## 验证
专项命令（repo根）使用services/aos-api/.venv/bin/python -m pytest -q新runtime测试、test_budget_cost_consumer_pg.py、test_budget_cost_configuration_pg.py：35 passed/35.95s，exit0，/tmp/aos-gh-focused.log。
新增5项证明：当前派生价格正向、撤回后hold/submit共用门拒绝、旧快照拒绝、持锁期间head更新lock timeout且事务结束后正常撤回、GE READ ONLY历史仍可查询。风险门正向不冒完整Task或Provider执行。
最终累计（cwd services/aos-api）：
`.venv/bin/python -m pytest -q tests/aip/test_budget_configuration_runtime_pg.py tests/aip/test_budget_cost_consumer_pg.py tests/aip/test_budget_cost_configuration_pg.py tests/aip/test_budget_configuration_product_pg.py tests/aip/test_budget_consumer_service_pg.py tests/aip/test_aip_development_model_binding.py tests/aip/test_aip_model_governance_policy_store.py --tb=short --show-capture=no`
84 passed/68.94s，7已有warnings，exit0，/tmp/aos-gh-regression.log；session62222已取终态。模型绑定纯值替身测试与真实PG分别声明，均不作正式业务验收。
compileall源文件/新测试、精确diff check exit0。方案补充首次shell Python读中文脚本报编码错误，未写文件；改用明确venv Python/UTF-8后成功补审计，不修改运行逻辑。

## Model/Task联合审计与下波
Model active还需合法Quota/Eval及治理依赖；预算reserve还需当前executing Task、当前approved plan上唯一running TaskRun、exact ActionApproval/Proposal/Draft及影响绑定，费用批准不能替代业务动作批准。
旧legacy opt-in reservation/deferred price测试未启用；已有content review PG静态预算价格不是GE来源联合证明。下一BG00GI沿现有Task/ActionStore入口构建独立联合验证，用真实派生budget/price引用，保留所有合法业务审批门，不手工run_definition、不把fixture当生产。

## 边界
代码a0v128无新迁移。真实当前库未连接/写入/重启，当前版本未重测。Host/worker/Provider未启，商城源/旧12Run/手工Run/230L0未动；无UI改动，browser不适用。正式首链、八场景、观察、发布仍pending。Watchdog未部署，Goal未改，无push。
