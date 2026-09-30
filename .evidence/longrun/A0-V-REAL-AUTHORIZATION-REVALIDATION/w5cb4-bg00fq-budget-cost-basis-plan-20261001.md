# BG00FQ 首次预算费用来源提议合同

基线AOS-001031/f9a316d6；Task W5CB4-BG00FQ-20261001。复习231-5§5/6/7、231-9§1/2、424/FP，预算合同/Preview/Decision/hash、development授权、network issuer合同。

## 设计
首次来源不依赖active BudgetPolicy。新增纯提议合同，明示尚待正式Producer验证与独立checker批准；本波不把用户输入提升成authority、不改旧预览hash/DB false门，不开启执行。此合同将用于后继持久化Producer，不能直接送入现有precheck当授权。
- 外部类型 external_reconciliation_reference：只收exact BudgetUsageReconciliationRevision引用；不接受自报零费用、usageKnown、externalUsageProven。后继Owner必须从独立签发者读真实账户/币种/期间覆盖、金额/未决、时效/撤销。
- 开发类型 development_risk_proposal：exact Provider+model、每次风险占额、授权期总风险占额、总调用次数上限。实际费用仍未知，不允许传amount=0/approvalRef/已批准状态；必须后继独立checker按当前身份批准整个提议。风险占额不是价格或供应商实际账单上限。
- Envelope：schema1、正租户、下一版active预算target、当前draftRevision/headVersion、canonical maker≠checker和来源；账户采用现有budgetId:daily/budgetId:pilot命名，currency/有效期间取target；hash绑定全部字段。严格整数，UTC归一化；不得把input hash当签名。无预算策略ref，从而避免首次依赖环。
- revalidate后输出payload/hash，拒绝model_copy/update或嵌套mutation绕过构造校验。现有BudgetRevisionCreate与VersionedAssetRef复用，不修改共享合同。

## 文件与验证
新增 services/aos-api/aos_api/aip_budget_cost_basis.py；新增 tests/aip/test_budget_cost_basis.py。先RED模块缺失，再最小实现；覆盖两种来源、真伪字段、wrong tenant/provider/ref、maker=checker、金额/次数/head严格类型、风险边界、目标/来源/角色/版本漂移改变hash、时区等价、mutated模型重验、JSON往返。相邻跑预算activation authority/消费PG及development授权合同。纯合同测试不等于真实Source/签发/业务验收，不新增HTTP/迁移/浏览器。

## 后续完整接线顺序
BG00FR：把本提议绑定既有预算preview/decision的独立版本化持久权威，兼容旧hash、保留不可变记录；先冻结专用source Producer与checker角色/ACL，不能复用network异域授权。真实账单ref尚无Owner时明确拒绝，开发分支需当前exact Provider来源/独立成员/授权期。之后同事务消费者重新核head/来源/撤销/占额并唯一消费批准写active/Receipt，产品持久请求+Inquiry，无手工Run。任何迁移当前实例均另开一致备份/克隆/零窗口波，当前库只读。

复审补充：新提议target在复用共享DTO前拒绝数字字符串/浮点/布尔、身份空白和非literal hardStop；仅新入口收紧，旧共享DTO不变。canonical_payload是含派生账户/期间的hash envelope，不是直接反序列化的请求DTO；后继持久化读者需重建并逐字段核对派生内容，不能丢弃后无校验。
