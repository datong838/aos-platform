# 调度审批精确内容绑定验证

基线0ae2ac80。先RED4 failed/1 passed：缺policyHash、错hash、审批后enabled变化、bool冒充expectedCaseVersion均曾错误通过。服务端增加完整规范化策略policyHash和严格payload字段类型后，adapter/Host/旧周期调度联合54 passed；AR2五类错误空。

仅8行服务端最小增量；原Case/版本/审批有效期/hash/ActionBinding校验保留。缺少精确内容绑定的旧审批拒绝，需要按完整策略重新走审批，不替换持久记录。测试为隔离Owner组合负例，不声称真实审批、数据库或业务链验收。本片未重载API/Host；运行API仍6201ea5b，Host仍aa3010c4，新增修复需在后续受控装配时生效。

下一步回到事件策略存储：现有biw8_001表/函数明确限制旧policyKind与cadence，新事件schema不得强塞；先设计新迁移兼容约束/同表复用/Case引用及独立受限写入函数，再补Owner和原子事件登记。230 L0不动，不push。

可追溯补记：A0V-BG02-EVENT-POLICY-20260913交付Receipt中的HEAD在创建时指向0ae2ac80，后续以该固定提交核验；不把移动HEAD当持续基线。
