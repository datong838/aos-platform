# AM 恢复事务内当前安装权限复用方案

## 1. 现场与问题

- AM `recoverable_store` attempt `7d6cc3aa-881d-4aff-ac30-58978d06e85d` 持续健康续租；主恢复会话在同一数据库事务内推进，未停死。
- `pg_stat_activity` 连续观察到 `bundle_composition`/composition lock 完整读取，查询时间持续更新。恢复权威的嵌套 `run_current()` 每次 `_load()` 都调用 `CurrentConfigurationPermission`，而一次调用会锁 installation、读取 membership/authz，并完整解析、哈希 composition lock。
- 外层恢复权威在同一连接、同一事务中已经通过 `FOR UPDATE`/`FOR SHARE` 锁住 installation、membership、marking 与不可变 composition 依据；嵌套权威再次读取相同权限不会提高并发撤销可见性，却会重复高成本解析。
- 当前 AM 已加载旧代码。本波不得重启、热替换或影响该 attempt；优化只用于后续恢复或自然业务执行。

## 2. 安全不变量

1. 复用范围只限一次最外层 `SnapshotGroupRecoveryAuthority.run_current()` 动态调用链；退出或异常后立即清除。
2. 缓存键至少绑定数据库连接身份、租户、installation、generation 与 actor；不同连接、事务、租户、安装、代次或主体必须重新校验。
3. 只有首次 `CurrentConfigurationPermission` 返回严格 `True` 后才能登记；异常、拒绝或 deferred 结果不得缓存。
4. 首次校验仍取得原 installation `FOR UPDATE`、membership/marking `FOR SHARE` 与 composition 完整性证据，这些锁保持至外层事务结束。
5. 只复用“当前安装控制权限”布尔结果；recovery Receipt、definition、saved facts、12 bindings、schedules、controls、policy、window 以及 consumer 回调后的 `_load()` 仍完整重读并比较。
6. `attempt_target_current()`、renew/transfer、非嵌套调用和任何新事务保持原逐次权限校验；不得把缓存变成执行许可或跨请求全局状态。

## 3. 最小实现清单

### `services/aos-api/aos_api/pipeline_snapshot_group_recovery_authority.py`

- 增加 `ContextVar` 保存当前动态调用链的 permission cache，避免线程或协程之间共享。
- 外层 `run_current()` 创建并在 `finally` 中 reset；嵌套 `run_current()` 复用已有作用域。
- 新增私有 `_permission_current()`，仅缓存原 `_definitions._permission(...) is True` 的 exact key。
- `_load()` 改走该私有入口；`attempt_target_current()` 保持非缓存直接校验。

### `services/aos-api/tests/extension_runtime/test_snapshot_group_recovery_authority_pg.py`

- Red：同一连接、同一外层 `run_current()` 中嵌套一次 recovery 权威消费，原实现产生 4 次完整 permission 调用；目标为 1 次。
- 验证第二次独立顶层调用会再次校验；不同连接不共享。
- 保留现有 membership 撤销、definition 回调中变化、window 到期、tenant 与 member 漂移拒绝测试。

## 4. 验证与退出条件

1. 新调用次数测试在旧实现失败并记录实际次数。
2. 最小实现后新测试转绿；recovery authority、owner、service、completion、AM/AL saved/replacement/successor 回归通过。
3. 代码复审确认 cache 仅活在动态调用链、仅 exact key、异常必 reset，且回调后的非权限事实仍完整重验。
4. AM 继续只读守护；测试通过不能视为当前 AM 提速、成功或浏览器门禁通过。

## 5. 风险与回退

- 若 psycopg 锁范围或嵌套事务语义不能证明首次权限依据在外层事务结束前稳定，则放弃缓存，不以性能为由削弱重验。
- 若并发测试发现 cache 泄漏到第二连接、第二事务或异常后的调用，立即回退实现并保留 Red 证据。
- 回退仅还原 authority 与测试文件；无迁移、数据写入或运行态变更。
