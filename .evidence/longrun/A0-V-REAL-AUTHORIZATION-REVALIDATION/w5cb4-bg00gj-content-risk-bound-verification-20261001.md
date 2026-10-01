# BG00GJ verification

2026-10-01；基线AOS-001050/m1 daf01691，代码a0v128不变。开工七强一致CURRENT，validate GREEN 1505 Delivery/1503 Task/4001 events。

## 实现与方案复审

ContentBudgetCommandOwner._build_command仅风险价读取resolved model，核exact model hash/provider/price，传递原HostTransaction、scope、精确Budget/Price/Provider及provider_model_id。_approved_bound要求正整数token和金额、完整上下文，调用现有require_cost_risk；必须返回已验证持久price且等于原读取price，并匹配resolved provider model。未知价格仍None，不计算为0，不猜账单。

require_cost_risk只在全部当前门成功后return price；旧非cost预算仍None，reserve/submit原调用忽略返回值，历史对账未改。_minimum_bound_fen原数字价格算法不变；_approved_action、Host revalidate、真正reserve与submit仍在各自阶段再次校验。新preflight不占预算，不新增重试。claim/execute预检与后续capability commit分开，不将预检当持久授权。

## 测试及命令

在services/aos-api运行：

```sh
.venv/bin/python -m pytest -q tests/aip/test_content_budget_risk_bound_pg.py --tb=short --show-capture=no
```

RED `/tmp/aos-gj-red.log`：12 failed/12.86s，exit1。失败为旧_approved_bound缺transaction/scope上下文参数，不冒充原实现成功放过撤销；原源码同时明确_minimum_bound_fen拒绝风险价格。

最小实现后加旧Owner测试：`/tmp/aos-gj-focused.log` 24 passed/13.28s，exit0。补_build_command风险参数接线测试后累计：

```sh
.venv/bin/python -m pytest -q \
 tests/aip/test_content_budget_risk_bound_pg.py \
 tests/extension_runtime/test_ecommerce_content_budget_command_owner.py \
 tests/aip/test_budget_configuration_runtime_pg.py \
 tests/aip/test_content_first_action_budget_pg.py \
 tests/aip/test_budget_cost_configuration_pg.py \
 tests/aip/test_budget_cost_consumer_pg.py \
 tests/aip/test_aip_development_model_binding.py \
 tests/aip/test_aip_model_governance_policy_store.py --tb=short --show-capture=no
```

`/tmp/aos-gj-regression.log`：80 passed/45.32s、7已有warnings，exit0。四个Python文件compileall和精确git diff --check exit0。

## 证据范围

- 新12项真PG测试使用标准完整迁移临时库、GE真实签名issuer批准/低权限consume/派生price，直接调用真实Owner金额门和真实共享权威函数。Provider/身份仍为隔离测试前置，不是正式实例来源。
- 合法风险额度保持已批准金额，数字价格仍None，reservation数量不增加；金额、Provider、model、price对象、未消费budget、零/布尔token、缺事务均拒绝；撤回价格/撤销批准及旧SERIALIZABLE快照拒绝。
- _build_command参数与model hash漂移测试是显式替身接线证明；数字计价与原流程相邻测试保留。未以替身证明完整合法Model/Action/Host链。
- 无迁移、UI变动；browser不适用。真实库未连接/重启/修改，Host/worker/Provider未启，无商城源、旧12Run、手工run_definition或230L0动作。既有browser/lockfile改动未纳入提交。

## 下一波 BG00GK

从GI已证明的真正reserve缺Action binding进入：沿Task准备阶段创建当前frozen ImpactPreview→正式ActionStore maker/checker→GE预算/价格→held联合路径。先审现有生产合同与合法Brief/Method/Eval/Responsibility/Capability来源；禁止固定binding hash、直接INSERT批准或用费用批准替代业务批准。原执行中RETURN不能复用首生Preview，继续禁入。Model Quota/Eval及正式实例身份/备份恢复/克隆全链/零窗口仍独立门；自然首链、八场景、观察发布未完成。
