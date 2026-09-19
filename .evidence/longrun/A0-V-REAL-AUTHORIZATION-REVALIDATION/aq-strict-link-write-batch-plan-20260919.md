# AQ strict link 远端写入批量化方案

## 实时原点

AQ 唯一自然 attempt `16ca3c76-4dbe-48c3-9ff3-4f06eb9fbc82` 在 300 秒上限后失败，终态为
`RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict`。关系评估与包含 1168 条关系的精确
Link Command 已落盘；Retirement、Store Receipt、`ecom_link`、link outbox 和 projection 均为零，证明
Store 事务没有跨越提交边界。

前一轮已经把 strict-link 的端点与已有 link 读取/锁定改为常数级查询，但写入仍逐 link 执行：每条关系
一次 link INSERT/UPDATE、一次 sequence nextval、一次 outbox INSERT。隔离本地 PostgreSQL 的 7.61 秒不能
代表 SSH 远端数据库；真实链路的数千次数据库往返仍超过 300 秒。

## 文件级清单

1. `services/aos-api/aos_api/ecom_consistency_store.py`
   - 仅在 strict-link 已持有完整端点/link 锁定快照时，在内存中完成同版本、载荷、墓碑和 dangling 判定；
   - 对新增 link 使用一个批量 INSERT，对更新 link 使用 executemany；
   - retirement 的原载荷前置条件直接复用同一锁定快照，删除逐 link 重读；
   - 一次取得本批所需 projection revisions，并以一个批量 INSERT 写出相同 event_key、payload、payload_hash
     与 authority transaction；
   - Receipt、checkpoint CAS 与事务内 `_reconcile_base_events` 仍在同一事务内，任一失败整体回滚；
   - 普通 batch 与无预加载直调路径保持逐行实现。
2. `services/aos-api/tests/test_ecom_consistency_store.py`
   - 锁定 strict 多 link 的批量写语义、冲突与重放。
3. `services/aos-api/tests/extension_runtime/test_strict_link_batch_performance_pg.py`
   - 在隔离 PostgreSQL 对 1168 条关系验证 link、Receipt、outbox、重放和远低于 300 秒的终态。

## 风险与停止规则

批量路径不得改变稳定排序、复合身份、同版本冲突、墓碑回归规则或事件内容；无法证明相同语义时停止，
不得以跳过校验换取性能。AQ 已失败且 qcursor 已停止，本修改期间不得重发 AQ；修复提交并重新加载 Host
后，只能经正式 pause/retire/direct-successor 产生下一任自然 attempt。

完成条件：专项、完整 Store、group link/retirement PostgreSQL 与 attempt guard 回归通过；代码/方案一致性
复审通过；AQ 单 attempt 和零提交边界证据固化后暂停并退休，再进入 AR 继者。
