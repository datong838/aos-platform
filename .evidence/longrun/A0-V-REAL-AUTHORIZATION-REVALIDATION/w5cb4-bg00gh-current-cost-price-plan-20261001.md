# BG00GH 当前费用价格准入缺口修复方案

基线AOS-001048/50dd4f4b，复习231-5、441、GE派生及Model治理/预算reserve与submit源代码。

## 事实与收窄实现点
ModelRuntimeStore.require_model_governance对active development price已调用require_current_development_price；预算reserve和submit共用require_cost_risk，但该函数只读exact历史price revision，未核current head。_price_authority也被历史deferred reconciliation调用，不能在那里无差别加当前门，否则可能损坏历史对账。
因此在aip_budget_cost_runtime.py的require_cost_risk中补tenant+price_id精确head FOR SHARE，要求current_revision等于批准引用。锁保持到当前新hold/submit事务结束，串行化撤回竞争；旧SERIALIZABLE快照遇head变化必须失败，不透明重试。历史查询和对账不调用此门，无修改。

## 文件与测试
- services/aos-api/aos_api/aip_budget_cost_runtime.py：仅上述小点，不新增迁移/高权限/连接；现有非cost budget路径不变。
- tests/aip/test_budget_configuration_runtime_pg.py：用真实TLS签名批准、低权限消费+GE派生的价格/策略，禁止price_for和直接active配置插入。通过现有store风险门验证new_hold True/False；原price撤回使用正式store发布suspended revision2，旧引用拒；旧SERIALIZABLE快照拒；GE历史query仍可读。明确只证明新hold/submit共用风险门，不冒完整Task/Provider联合执行。
- 方案与verification；后续442、D-waves登记Model/Task全链缺口：active model还需Quota/Eval等合法来源，完整Task需当前approved running Plan和ActionApproval，不能造引用绕过。

RED旧引用仍过门→最小实现→新专项+既有cost/config/service/product/权限相邻回归。DB-only无browser。真实库只读不迁移/重启，Host/worker/Provider关闭，不读商城源/旧12Run/手工Run/230L0。收口后继续Model/Task联合路径。

## Joint-path audit
- Active publish_model requires an exact passed Eval and current quota/budget governance. Public active quota publication rejects missing approval; a fabricated model is not a substitute.
- reserve checks Budget, Task, price, ActionApproval and three buckets before the shared cost-risk gate. submit invokes it again before a new Provider request Receipt.
- ecommerce_growth_content_generate requires an executing Task and exactly one approved running TaskRun on the current plan. ActionApproval/Proposal/Draft/impact binding remain separate from cost approval.
- Legacy opt-in reservation/deferred-price tests were not enabled. Existing content review PG fixtures use static price/budget sources; they do not prove GE-derived source integration. BG00GI must build the independent joint proof through existing Task/ActionStore paths and disclose isolated prerequisites.
