# 开发授权接入策略合同验证

基线 3faec756；沿用 A0-V m1 Lease。BudgetPolicyRevisionCreate/Revision 增加可选 developmentCostAuthorization，由原 materialize_policy 和 Store payload 路径承载；授权非空时参与策略 hash。批准依据、有效期和正式 Revision 租户一致性均验证，禁止与 zero-price 混用。

新增测试先红于未知字段，实施后预算策略及开发授权测试合计 43 passed。另从 git 3faec756 加载真实旧合同，对同一 budget_body 比较 JSON 和 canonical_hash，完全一致。默认字段未进入旧 payload，新授权内容进入新 hash。旧 non-deferred unknownPriceBehavior=block 保持不变。

无 DB 写入，无 Provider 调用，无页面修改。本轮只完成策略合同承载与本地序列化验证；尚未执行数据库发布/回读、Resolver 放行或结算状态迁移，不宣称这些路径通过。

既有 schema/deprecation 警告和 JDBC 测试退出日志问题仍存在；旧模块比较过程间接导入 main 并加载 dotenv，未输出凭据，但后续独立验证脚本必须在导入前禁用 dotenv，避免凭据进入进程环境。

下一项：明确未核价模型快照及策略联合验证，贯通调用前 exact 检查和费用待核算结算状态；继续真实首链，不等待报价、不 push。
