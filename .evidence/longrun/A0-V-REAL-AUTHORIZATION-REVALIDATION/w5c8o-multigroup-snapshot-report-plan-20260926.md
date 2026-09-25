# W5c8o｜隔离 PG 多组快照报告验证计划

## 上位边界与当前事实

承接 W5c8n `m1@722d4050`/AOS-000676。现有报告只在一个真实隔离 PG 保存组上 GREEN；第二页、同事务并发插入/新事务可见性仍未证明。真实库未迁 a0v_096/097，真实 profile 停止；本波仅对一次性 `aos_test_*` 数据库构造测试数据，不读微商城源，不扫描真实历史组，不回填 sidecar，不建 ACK，不启动 Worker。

## 文件级清单

- 复习 `a0v_024/045`、`pipeline_snapshot_group_claim_owner.py`、`test_analysis_snapshot_resume_chain_pg.py` 与 W5c8n 测试，确定生成第二个**满足数据库约束**的同租户保存组的最窄路径。不得绕过不可变 trigger、RLS 或伪造“真实原始组”的闭环授权。
- 仅修改 `services/aos-api/tests/extension_runtime/test_a0v_w5c8n_bounded_group_report_pg.py`：RED/GREEN 验证同一只读 RR 快照内第一页和第二页恰好一次、并发新组不进入旧快照、新事务独立看见新组且旧 cursor 拒绝。测试数据可以是明示 synthetic 的缺输入分类，但必须满足 a0v_045 数据库约束；若无法安全构造，保留缺口并 STOP，不降低测试断言。
- 生产报告代码原则上不改；若测试暴露真实缺陷，先增订本方案再作最小修复。只执行专项与相关累计测试，不运行真实库迁移。

## 九步与退出条件

1. 上位方案/产品和仓库/测试 profile 对账。
2. 本方案落盘并提交。
3. RED：隔离 PG 多组/并发/跨事务反例。
4. GREEN：仅必要的测试 fixture 或最小生产修复。
5. 专项/累计、静态与测试库 0 回读。
6. 浏览器只读验收；无业务 UI/目录不可用明确不可验收。
7. 方案/代码一致性和风险复审。
8. verification、m1 精确提交、D-waves/AOS CAS/Prime 回读。
9. 自动下一波 W5c8p：依据本波证据设计受控回填 writer 的身份/不可变输入绑定/零权限缺口；未有独立真实门禁前不写真实数据、不 ACK。

任一步遇未知边界即冻结，不重发、不手工 `run_definition`。230 L0 挂起，`dev-org/dev-project` 仅零 canary。m1 单写者，不 push、不动其他分支。
