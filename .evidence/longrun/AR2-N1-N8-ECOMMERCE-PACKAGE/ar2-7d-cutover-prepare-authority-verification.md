# AR2-7D D5A 整组切换 prepare 权威验证

日期：2026-09-09
基线：`m1@f213aa9f`
结论：`AR2_7D_CUTOVER_PREPARE_AUTHORITY_GREEN`

## Rules 与验证结论

- 以 closure manifest、动态阶段验证器、231-3/231-6 和本切片方案为权威；m1 单人串行、先方案后实现、隔离 PostgreSQL、证据后提交；不 push，230 L0 挂起。
- 新权威只执行 prepare：冻结固定九项 operation、旧/新 dispatch snapshot、目标 installation/generation/epoch/runtime revision、policy/approval、checkpoint、occurrence watermark 与 pending target Receipt refs；不修改 dispatch/runtime binding，也不暂停或领取 occurrence。
- prepare 在 dedicated、非特权 `aos_extension_maintainer` 和 serializable 事务内执行；普通 `aos_runtime` 没有三张 cutover 表的写权限。租户、组、installation、generation、当前 runtime、当前审批与完整 Proposal draft 逐项重验，任一漂移失败关闭。
- ActionApprovalEvent 对应 Proposal 在受限 SECURITY DEFINER 函数中 `FOR SHARE` 锁定，锁后才读取数据库时钟判断 expiry；函数固定 `pg_catalog,public,pg_temp`，TEMP 同名表不能遮蔽权威。
- operation 可演进字段仅开放 `status/updated_at`；event 与 Receipt 不可变。首次和重放都重算 Receipt 内容哈希，并核对 authority 正文与 operation/receipt 拆列及数据库时间。

## 实现与方案一致性

- `services/aos-api/alembic/versions/ar2_013_ecommerce_growth_cutover.py`：在线性 `ar2_012` 后新增 tenant-scoped operation/event/receipt、RLS、最小授权、审批锁函数、历史不可变触发器和非空 downgrade 阻断。
- `services/aos-api/aos_api/ecommerce_growth_cutover.py`：新增严格 DTO 与 `EcommerceGrowthCutoverStore.prepare_activation`；固定锁序、九项整组快照、runtime/approval exact 校验、同事务写入与回读。
- `services/aos-api/tests/extension_runtime/test_ecommerce_growth_cutover_pg.py`：真实隔离 PostgreSQL 覆盖成功、重放、租户 canary、idempotency 漂移、缺项、runtime 未 ready、approval 漂移、权限/隔离级别、TEMP shadow、bool/int、Receipt 拆列篡改、审批锁与锁等待跨 expiry、不可变历史、外层回滚及非空 downgrade。
- `closure-manifest.md` 登记新的 platform host control port；实现不导入领域 bundle，没有改变固定九项服务的既有行为。

## 测试证据

- 重启后专用 Colima `aos-extension` 内 `aos-ar2-validation-20260909` 正常，回环 `127.0.0.1:18434` 连接成功；旧 18432 保持停止。
- D5A PostgreSQL 专项：`13 passed, 7 warnings in 5.51s`。
- 完整 `tests/extension_runtime`（未开启 PostgreSQL opt-in）：`741 passed, 484 skipped, 7 warnings in 20.86s`。
- Alembic：单一 head `ar2_013`。
- Python compile、`git diff --check`：通过。
- Closure：`1708 scanned / 92 classified / 57 migrated`；`hashErrors`、正反向未分类依赖、跨层 import、动态引用错误均为空。
- Memory validate：`AOS-000571 / GREEN / 865 Delivery Receipts / 2226 events / 846 Task Receipts`。
- 单人静态复核对照方案逐项检查权限、锁序、审批截止时间、稳定 JSON、Receipt 拆列回读、严格数值与 no-effect 边界，未发现剩余 blocker/major。

## Red/修复轨迹

- 首次专项遗漏通用 fixture 的 `AOS_DATABASE_URL`，setup 误连默认 5433 并拒绝，零业务逻辑执行；补齐既定 18434 DSN 后继续。
- 初版直接锁 dispatch 行触发 maintainer 权限失败；改为组/installation/generation advisory lock，并保持 dispatch 对 maintainer 只读。
- 初版 INSERT placeholder 数量不一致，修正参数绑定后专项进入合同验证。
- 静态复核依次发现普通 runtime 更新面过宽、未限定 SQL 可受 TEMP shadow、Receipt 回读不足、approval stable 重组不足、bool/int 混同、事务隔离与审批并发截止不闭合；均以最小权限、显式 schema、严格重组/拆列、serializable 和 Proposal 锁修复，并增加反例。
- 最后一轮把 `checked_at` 移到 Proposal 锁之后，增加锁等待跨 expiry 反例；重启后专项与全量均保持绿色。

## 内容摘要与保留边界

- `ecommerce_growth_cutover.py` SHA-256：`213209a8a3f000b69e22ecbc5d12933fa84ed969e50de06c2356dd9d331dc5c0`
- checkpoint、watermark 与 pending target Receipt refs 仅是 prepare 请求及 Receipt 冻结值，不代表已经枚举运行中的 occurrence/attempt/Receipt；D5B commit 必须重新读取当前事实。
- 本切片没有执行九项 CAS、没有生成 `CUTOVER_COMMITTED`，不证明切换或回滚可用；D5B/D5C 仍需实现 claim pause、旧 epoch drain/UNKNOWN 门、唯一提交点、9/9→0/9 失败回滚与读回验证。
- 未读取真实源、未调用 Provider、未写真实租户、未执行生产/共享迁移、未发布、未 push；AR2-7D 整体仍未封板。
