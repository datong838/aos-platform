# 商品源事件只读合同

基线700b5e3a。承接自然经营首链方案第1项，不新增事件存储、不写projection_outbox.projected、不触发Case，不动已签名1.3/1.7候选包或当前容器。

代码：bundles/domains/ecommerce-core/backend/ecommerce_core/product_source_event.py。纯函数只接收可信Owner读取的单条权威Outbox记录；SHA校验是完整性检查而非来源认证。调用者仍必须通过受治理读入口取得记录，不能接收浏览器自报的行来授权。

验证租户org/project/workspace、authoritative_store、事件键/事务键/载荷SHA256、正整数revision/outbox ID、Product/ProductSku对象与objects_written/objects_tombstoned类型、载荷schema/entity/change、三处对象与身份一致、删除语义。返回冻结的最小事件引用，不返回properties、业务原文或数据库凭据。拒绝未知/legacy/跨租户/哈希漂移；错误为固定码，不含输入内容。读取不等于SourceReadiness通过，也不等于有权创建Occurrence。

测试：services/aos-api/tests/extension_runtime/test_product_source_event.py。先红，再用既有EcomConsistencyStore在隔离SQLite实际提交的Outbox验证正向及tombstone，证明与真实Owner合同一致；测试篡改、重新计算hash后的身份漂移、未知类型、bool revision、非JSON数值、隐私不外泄、重放引用稳定。SQLite仅验证Owner合同，非真实栖月汇或PG运行验收。阶段验证器核对依赖；下一波再设计独立消费Receipt与持续执行装配，不越过待批权限。
