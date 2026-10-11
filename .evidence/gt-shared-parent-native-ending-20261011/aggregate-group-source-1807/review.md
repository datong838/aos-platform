# 聚合分组阶段1807

按PG16 nodeAgg.c/nodeAgg.h核对perhash.numCols与execTuplesHashPrepare长度；补各分组hash/equality函数与phases排序、分组操作符观察，原身份及三hook不变。严格编译、admin/null负门通过。

完整新Source联验1 passed、8 warnings、155.87秒。aos_test_5b8ce7041195_ti4_test，XID67911 aborted。242函数签名集合与1806一致，没有新增函数；不能由此断言所有分组策略均已执行。九表0、无其他客户端、profile恢复、三恢复正文和权限精确核对、三删除路径核对通过。

后续优先包信任链及固定验证器正式边界，勿将观察列表当允许列表。原生指针、未走分支、包生命周期和实际正向提交仍未完成。无业务权限或组件Delivery。
