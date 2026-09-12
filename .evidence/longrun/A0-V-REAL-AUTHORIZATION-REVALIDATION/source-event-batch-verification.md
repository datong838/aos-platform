# 源事件批次原子登记验证

2026-09-12，基线7421f843。新增record_event_batch复用原确定性ID、_lock_binding和_insert_occurrence；列表1至100条，先验证全部输入并拒绝重复事件身份，同租户/绑定事务一次提交。不推进watermark，单事件和schedule接口未改。

先红7 failed；实现后18 passed，包括原周期/Occurrence回归及专用18432 PostgreSQL实际事务。新PG测试证明两个并发批次产生同一组2条Occurrence，只有一批非重放；第二条deadline漂移时新第一条及Outbox全部回滚，原2条不变；wrong tenant和disabled拒绝；空、101项、重复ID、空身份、无时区和非字符串均不写入。schema由既有fixture创建/回收，主库无迁移、授权或业务事件注入。

AR2-7检查1790模块、158分类、93迁移，五类错误空；memory-validate GREEN。06:15:13Z真实宿主已运行1902秒、31续租、3容器running、ready/enabled/unfenced@4、canaryInstallationCount=0，见source-event-batch-continuity.json。

限制：新批次接口尚无生产源消费者；调用者必须可信、验证当前来源和冻结deadline。当前绑定的业务执行许可仍由Admission/claim验证，登记不等于执行。未修改当前签名包和容器，未完成首链或八场景。

下一波：设计并验证晚提交事件不会遗漏的有界源读取；以Occurrence事件存在性去重而非最大序号游标。优先复用现有权威Outbox读Owner与查询能力，避免新增全局扫描、第二套事件状态和权限捷径。
