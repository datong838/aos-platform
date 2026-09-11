# D01 正式方法、指标口径与评估输入方案

2026-09-11，m1 a18a606c，AOS-000573。沿用产品07/12、技术15与101 ADR、231-5/231-6。方法已补；本波复用公共指标和评估Owner，不复制指标值。

## 实现目录

- `services/aos-api/aos_api/aip_eval_authority_store.py`：新增精确版本指标定义读取，平台层保持领域中立，核对返回身份/行hash。
- 新 `services/aos-api/aos_api/ecommerce_analyst_portrait_sources.py`：显式同连接读取当前Method、唯一MetricDefinition清册及当前冻结且ready的EvalContract，核对全部引用/租户/版本，重算指标定义和Eval创建内容hash；旧metric修订不可冒充最新口径。
- 新 `services/aos-api/tests/test_ecommerce_analyst_portrait_sources.py`：缺失/跨租户/不匹配/哈希/版本/不可用评估拒绝，完整隔离数据库验证现有Owner读取与方法组合。
- 本目录 `real-business-acceptance-matrix.md`：固化用户询问的真实业务计划与八工作台验收清单。

## 语义与边界

此函数只返回方法、指标定义、评估合同三类正式元数据，不返回指标值、ready页面状态或Insight，不把定义存在当作观察值有效。正式指标观察/QueryResult与原始披露证据绑定在下一段继续实现。读取评估合同复用公共Owner现时publication/release gate可用性；冻结不等于永久可用。方法head持共享锁；指标无head，以当前最大revision做快照判断，后续执行继续重验。所有连接均显式绑定，不使用默认DB。

补充核查：公共EvalContract readiness当前未核对release gate expires_at。D01读取额外接收显式aware now，并核验绑定门的decided_at<=now<expires_at、passed/hash；不能仅凭ready使用过期评估门。保持原公共Owner行为不变。

## 验证与退出

正向重算hash与同连接，缺失/非法类型/重复指标/非当前方法和指标/非冻结或blocked评估/来源hash漂移均拒绝。隔离库用既有公共表及Owner构造合成依赖检查真实读取，不关闭约束或伪造生产ready；关联方法/诊断/方案读取回归、方案一致性、证据和提交。无主库迁移、Provider或业务副作用。下一段D01完整观察/受控来源与固定生成，然后工作者/宿主/实际配置/真实源/首链/八场景观察。不push，230 L0挂起。
