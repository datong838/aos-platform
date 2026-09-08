# AR2-7D D1 查询来源测量分支验证

- 基线4463f3f6，AOS-000571；继续同一AR2-7D Task/Lease，不推进整波完成状态。
- 施工卡：231-6；代码data_requirement_quality.py、data_requirement_quality_evidence.py、tests/test_data_requirement_query_measurement.py。
- 新增显式canonical-query测量合同，要求QueryResultRevision和EcommerceObjectRevision来源；保留原水合合同必填的水合及映射引用，不制造水合回执。
- 最终专项与受影响回归：test_data_requirement_query_measurement.py、test_data_requirement_quality.py、test_data_requirement_quality_evidence.py、test_aip_analyst_query_host_transaction.py；54 passed,8 warnings in49.58s。
- 原水合证据摘要固定回归为250a28bed2d96cef073d288d138f346bb4a7b63d062ab45d50c900ffd662adfa，验证结构调整未改变历史证据摘要。覆盖分支混用、缺失/错误引用、序列化与证据回读。
- Prime独立只读审查PASS。合同结构不是来源真实性证明，运行时仍须回读Owner；quality Evidence不计入业务事实覆盖。
- 未执行真实业务写入、付费调用、共享库迁移或外部发布。未变更页面，浏览器可用性不作为新后端链路验收。
- 下一项：固定查询的店铺范围与完整集合统计，再接真实事实Evidence；展示页分页结果不得作为完整人口分母。
