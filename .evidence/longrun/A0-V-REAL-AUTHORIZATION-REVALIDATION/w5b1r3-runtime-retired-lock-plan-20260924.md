# W5b1R3 退休判定的最小特权行锁（2026-09-24）

## 现场与军规

W5b1R2 `663851c1` 唯一 disable 请求在同事务因 `aos_runtime` 对 cutover operation 只有 SELECT、无 `FOR UPDATE` 所需 UPDATE 权限而回滚。独立核验新 Command Receipt=0、旧 enable accepted/未消费、binding rev11/epoch6 disabled/fenced、12 schedules off、active attempts=0。18434 独立测试容器已恢复且复现同样权限失败。W5b1R2 私有 intent/键永不重用。

不扩大 `aos_runtime` 基表 UPDATE 权限，不削弱完整退休谓词，不读商城源，不触发定义/调度/业务 run。沿用 SQL SECURITY DEFINER 的精确授权、租户作用域、固定 search_path 模式。

## 方案与文件

1. 新增 `services/aos-api/alembic/versions/a0v_092_retired_dispatch_read_lock.py`：为一个同事务中 `running/fencing` 的精确 runtime disable operation 提供窄权限 `extension_dispatch_retired_read_lock_a0v_092`。仅允许 `aos_runtime` 成员的非特权 session、有效租户上下文；验证 runtime operation 与目标 installation/generation、activation/group 的一致性；行锁 activation 和该 group 当前 dispatch 行，其他输入拒绝。函数只获取锁、无表写、无业务效果，默认 EXECUTE 收回，仅授 aos_runtime。
2. 修改 `services/aos-api/aos_api/ecommerce_growth_lifecycle.py`：退休谓词先调用锁函数，之后仅 SELECT 完整退休证据；Python 不自行对无 UPDATE 权限的基表 `FOR UPDATE`。绑定行已由原 disable Owner 同事务 fence/锁住，锁函数锁历史 activation/group 行；不存在 gate/新 dispatch 的并发变化需受该 group 9 行锁与原 cutover 路径约束。
3. 更新独立 PG fixture 与 `test_ecommerce_growth_retired_dispatch_gate.py`，回归退役/未退役/多 activation、权限隔离、已有 cutover/disable。若新迁移不能在专用测试库通过，不部署主库。
4. 主库迁移前只读确认当前 head/角色/旧 enable 状态；在完整测试通过后迁移到新 head，8080 重启并读回。用新脚本 `scripts/a0v_w5b1r3_enable_retirement.py` 的新私有 intent/新键一次 formal disable；任何未知边界先冻结，绝不重发。
5. 独立 audit、verification、m1 commit，不 push。下一波再设计新的 live successor/PreparedJob 与 12 条 selection。

## 停止条件

锁函数的权限或并发证明不成立、现行 cutover 路径不受行锁约束、测试库/主库迁移异常、旧 enable 已 claim 或状态变化、任一正式请求提交边界未知时停止本波写操作，保留 disabled/fenced 安全状态。
