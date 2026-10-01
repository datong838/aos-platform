# BG00GE 费用配置原子派生验证

基线AOS-001045/b145a634。a0v128仅标准pytest独立测试库全迁移，当前真实库未连接/写入/迁移/重启。

## 实现与方案复审
- a0v128新增aip_budget_cost_configuration.sql，沿用预算consumer固定caller/owner。原127历史消费Receipt核验提取为owner-only fact helper，原readonly查询wrapper仍要求READ COMMITTED/READ ONLY。
- 新configure函数仅6个原scope/proposal/decision/actor/hash参数；验证原maker、已消费Receipt完整target/hash，首次同budget-cost-review锁核当前双成员、未撤销有效批准、当前budget/provider head及窗口；写后再次核时效。
- 固定ID由domain-separated canonical digest派生；price无数值价格（null，非零价），price与budget-policy共用原批准的Provider/model/decision/预算有效窗；policy硬停/unknown block/无zero授权。两组head/revision和budget_cost.configure Receipt原子落地，不覆盖历史。
- 原消费created_at以固定UTC字符串用于派生元数据，避免session timezone改变历史核验。price/policy哈希经Python合同重序列化独立校验通过。
- 历史query独立READ ONLY，无Receipt unresolved，原记录不一致conflict；当前原maker身份仍须合法。重复仅原Receipt，不重新激活撤回的price、不新写配置。
- trigger拒绝共享runtime直接INSERT active development price/policy与configure Receipt；非development和非active路径不变。独立caller无表权限，helper无caller EXECUTE；owner对新增5表仅SELECT/INSERT，无任意UPDATE/DELETE。
- schema manifest核对：原15表无变动；新增5表/5个派生函数+1trigger函数，仅旧127查询definition委托变化。现有price表runtime历史DML ACL保持原状，append-only trigger仍在；不声称清理了全部历史ACL技术债。
- 旧FX price_for是明确隔离恶意/历史夹具：同事务暂关新增price guard构造fixture，SET CONSTRAINTS ALL IMMEDIATE完成延迟FK后重新启用再commit。无生产代码绕过；这些fixture不当正式producer证据。

## RED/专项/累计
cwd services/aos-api。
- RED新PG测试UndefinedFunction aip_configure_budget_cost_a0v_128，exit1，/tmp/aos-ge-red.log。
- 初版10passed；增加直接写拒绝/canary/owner-helper门后12passed，manifest候选diff测试预期失败。候选来自本次独立迁移；逐项比对后更新固定manifest。
- 初次累计96passed/6failed：旧fixture恢复trigger遇pending deferred FK events；定位ObjectInUse后仅修fixture SET CONSTRAINTS ALL IMMEDIATE，保留关/开同事务。
- 最终命令：`.venv/bin/python -m pytest -q tests/aip/test_budget_cost_configuration_pg.py tests/aip/test_budget_consumer_connection_pg.py tests/aip/test_budget_consumer_service_pg.py tests/aip/test_budget_consumer_process.py tests/aip/test_budget_consumer_product_pg.py tests/aip/test_budget_cost_consumer_pg.py tests/aip/test_aip_model_governance_policy_store.py --tb=short --show-capture=no`
- 104passed/75.37s，7已有warnings，exit0，/tmp/aos-ge-regression-final.log；原session57814已取回终态。
- 新14测试包括真实独立caller/PG双配置+双合同哈希、回滚不留可见配置、并发一Receipt、成员/Provider/budget/actor/decision/未消费拒绝、撤销历史查询、readonly强制、runtime直接写拒绝、canary/helper拒绝、真实时间过期拒绝、撤回price不被重复派生重新激活。
- compileall新迁移/connection/测试exit0；git diff --check exit0。manifest SHA256 c39aa009040f4715acdfad347362c2880f800ba1ef22f39304f92c9ce40253b9。

## 证据边界与下一波
这里的签名批准/消费/派生在独立真实PG和低权限角色完成，Provider前置记录仍是隔离fixture，不是正式安装或生产授权证明；无真实Provider请求。DB-only无UI改动，browser不适用。当前真实库版本未重测，不能把代码128当成当前运行版本；Host/worker/Provider未启、商城源/旧12Run/手工Run/230L0未动。Watchdog仍方案，Goal未修改，无push。
下一BG00GF把独立configure/inquiry接有限service与严格IPC/产品原请求恢复，复用既有JWT/attempt/peer/once机制；再接Model/Task预算风险真实联合证明，正式迁移/启用须独立备份可恢复、克隆全链、零窗口。首链/八场景/连续观察/发布仍pending。
