# AP 执行前 strict link Store 批量化方案

## 问题与实时边界

AO ordinal-2 在固定 300 秒执行上限后以
`RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict` 终结。这个 error type 是
`RecoverableStoreAttempt` 对 deadline 的外层分类，不是某条 ingress journal 内容冲突。

实时持久事实表明：十二个 Dataset Receipt、relationship assessment 与包含 1168 条 link 的原始 command
均已存在；retirement preparation、link Store Receipt、`ecom_link` 与 link outbox 均为零。因此卡点位于
`ControlledSnapshotGroupLinkExecutor` 调用的 `EcomConsistencyStore.apply_strict_link_batch()` 内，且事务在
deadline 后回滚，没有跨越未知提交边界。

当前 strict link 实现对每个端点和每条 link 逐条锁定，随后又逐条检查两个端点、再次读取 link、写 link、
取 projection sequence 并写 outbox。1168 条 command 会形成数千次数据库往返；attempt 的 cancel event
只能在 Store 调用返回后被检查，不能中断同步事务内部循环。

## 修改范围

1. `services/aos-api/aos_api/ecom_consistency_store.py`
   - strict link 进入事务后，按完整复合主键批量、确定顺序锁定精确端点与现有 link；
   - 返回锁定快照供本事务后续复用，删除逐 link 重复端点查询和重复 link 查询；
   - 保持单事务、相同 idempotency request hash、checkpoint CAS、Receipt、outbox 与 replay 校验；
   - 普通 object/link batch、retirement 前置条件、RLS 和租户范围不改变。
2. `services/aos-api/tests/test_ecom_consistency_store.py`
   - 新增多 link 严格批次，断言端点/link 锁定使用有界批量查询；
   - 保留 dangling endpoint、同版本异载荷、重放、删除端点与 retirement 负例。
3. `services/aos-api/tests/extension_runtime/test_snapshot_group_link_executor_pg.py`
   - 在隔离 PostgreSQL 构造大批量关系，验证原子提交、Receipt、outbox、replay 与投影完成；
   - 记录耗时，但正确性断言不依赖机器绝对速度；真实 1168 command 在恢复前另做只读边界核验。

## 停止规则与完成条件

若批量查询不能保持精确复合身份、锁顺序或 strict replay 校验，停止实现，不以放松一致性换性能。若专项
PostgreSQL 仍接近 300 秒，继续批量化写入/outbox，禁止启动 qcursor 试错。

完成条件：专项与累计测试通过；大批量 strict link 在隔离 PostgreSQL 明显低于 300 秒；方案与实现复审
确认单写者、租户隔离、幂等 Receipt、未知结果和失败恢复边界不变。随后提交，再恢复 AP 唯一自然 attempt。
