# 已消费事件精确原批次回读

基线bfbadae0，父任务Host/tests范围。

修改 services/aos-api/aos_api/ecommerce_product_event_reader.py：保留run_candidates原语义，新增run_event指定64hex事件，在相同SourceOwner/原parent+derived+batch proof下读取。内部_read_candidates可选event_key，仅选择原proof中该事件，并省略未消费条件；不能扩大proof集合。run_event严格唯一，不存在/空原批次拒绝，回调仍同步且在Owner内。

tests/extension_runtime/test_product_event_reader_pg.py 与test_product_event_reader_callback.py：已生成Occurrence事件仅精确回读可见，候选仍排除；不在原proof/错scope/重复/篡改拒绝，不导出payload；回调拒绝空批次和deferred。

此能力只提供来源元数据，不是分析授权；后继还须当前claim/policy/审批与事务复核。无主库写入、部署或push。
