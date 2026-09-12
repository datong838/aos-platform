# 商品源事件只读合同验证

2026-09-12，基线700b5e3a。新核心包文件 product_source_event.py 与对应 test_product_source_event.py 实现按方案的只读完整性校验。没有修改__init__操作注册、候选版本、主库或已运行容器；尚未接入持续消费，不是业务触发完成。

先执行测试因目标模块缺失收集失败；实现后23 passed；联合既有EcomConsistencyStore和projector回归70 passed。正向使用正式Owner在隔离SQLite事务产生的Outbox，而非自行编造“真实来源”。覆盖Product/ProductSku写入与tombstone、稳定重放、无输入修改、只返回元数据；13种索引/权威字段异常和6种重新hash后的语义异常拒绝。数据正文不返回，错误固定码，不带源内容。该证据不等于真实商城或PostgreSQL验收。

AR2-7：1790模块、158分类、93迁移，hash/前向/反向/跨层/动态引用五类错误全空。diff check通过。当前实现只提供输入合同；独立消费Receipt、持久化游标、生产装配和自然链路仍需实现，不复用projected标记或认为SHA是身份认证。

下一波核对源事件持续消费与Occurrence之间的事务/游标合同，避免多事务提交乱序导致漏事件，明确最小权限及现有Owner接入点。主库调度登记权限与SSH连接信息仍待答复。
