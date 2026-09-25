# W5c8n｜有界历史源组只读分页报告计划

## 上位与安全边界

承接 W5c8m `m1@5c552c33`/AOS-000675。精确单组分类仅输出候选/冻结原因，不能作为回填、ACK、Host 或真实 closure 授权。真实库未迁 a0v_096/097、真实 profile 停止；本波只在隔离 PG 做**同一 REPEATABLE READ READ ONLY 快照**中的有界 keyset 页，绝不触碰真实历史数据或商城源。

## 文件级清单

- 复习 `pipeline_snapshot_group_witness_classifier.py`、`a0v_045/097` 的主键与 created_at、W5c8m 正例/拒绝覆盖；固定 `created_at,group_id` 稳定顺序、每页上限 12、额外 1 行判是否还有后页。
- 新增 `services/aos-api/aos_api/pipeline_snapshot_group_witness_report.py`：输入已开启的精确租户 `aos_runtime` 只读 RR 事务、可选 cursor、页大小 1–12；只查询原 claim 键，再在**同一连接/事务**调用单组分类器。只返回各状态计数、处理组数、opaque typed cursor，不返回组 JSON、成员/源或 sidecar 内容；拒绝错误租户、可写连接、越界页和跨快照游标。
- 新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c8n_bounded_group_report_pg.py`：先 RED 后隔离 PG 原保存组正例；错租户/可写/页界、游标篡改和跨快照拒绝；对“第二页/并发插入”若 fixture 只有一组，单列未覆盖缺口，不用 mock 冒充真实 PG 多组证明。
- 不新增迁移、sidecar SELECT/INSERT、Worker、ACK；不运行真实批量扫描。若无法可靠绑定游标到快照，STOP，改成一次事务内无续页的限量报告。

## 九步

1. 复习上位/产品约束、W5c8m、m1/AOS-000675/专用测试 profile。
2. 先提交本方案。
3. 先 RED：模块缺失和边界负例。
4. 最小实现，只读事务、12+1 限界、单组分类复用。
5. 专项/累计、测试库 0、静态检查。
6. 浏览器只读；无业务 UI 或目录不可用则标不可验收。
7. 方案/代码一致性复审，尤其跨事务 cursor 与多组未测缺口。
8. verification/m1 提交，D-waves/AOS CAS/Prime 回读。
9. 自动下一波 W5c8o：补**真实隔离 PG 多组+跨事务/并发**负例后，才考虑受控回填 writer 设计；真实扫描另门。

230 L0 挂起、商城源不读、dev-org 仅零 canary、unknown 不重发/不手工 `run_definition`；m1 单写不 push、不动其他分支。
