# A0-V Managed Schema SourceReadiness 缺口修复方案

## 1. 触发与根因

在隔离恢复库中，从真实历史修订 `228ti5a3lineage` 运行完整 Alembic 链到当前 head `ar2_018` 后，`GET /v1/data/source-readiness` 返回 500。数据库错误为 `UndefinedTable: relation "meta_schedule_run" does not exist`。

`meta_schedule_run` 的表和索引当前只由 `aos_api/db.py::SCHEMA_SQL` 的 legacy bootstrap 创建。Alembic managed-schema 链没有对应迁移，但以下当前运行代码直接读取该表：

- `aos_api/source_readiness.py`；
- `aos_api/routers/wave_ext.py` 的运行历史、最近运行和按日统计查询；
- QYH Cron 调度执行记录写入链。

因此，在明确禁用 legacy bootstrap 的 managed database 上，应用代码与正式迁移清册不一致。A0-V 必须修复这个确定性产品缺口，不能通过重新启用启动期建表来掩盖。

## 2. 最小修改

计划新增以下文件：

- `services/aos-api/alembic/versions/a0v_001_meta_schedule_run_managed_schema.py`
- `services/aos-api/tests/test_a0v_001_meta_schedule_run_managed_schema.py`

不修改 SourceReadiness 业务判断，不修改 Cron 行为，不向恢复点写入业务数据，不更改现有表和历史迁移。

新增迁移以 `ar2_018` 为 `down_revision`，只补齐与现有 `SCHEMA_SQL` 等价的 `meta_schedule_run` 表、唯一约束和历史索引，并补齐 managed runtime 所需的安全边界：

1. `org_id/project_id` 双租户键保持非空；
2. 启用并强制 RLS；
3. `aos_runtime` 的 policy 同时约束 `USING` 与 `WITH CHECK` 到当前事务 GUC；
4. 撤销 PUBLIC 权限，向 `aos_runtime` 仅授予当前读写链所需的 `SELECT/INSERT/UPDATE`，不授予 DELETE/TRUNCATE；
5. 升级使用 `CREATE TABLE IF NOT EXISTS` 后必须核验已存在表的列、主键、唯一约束均符合契约；若结构漂移则失败关闭，不能静默当作成功；
6. downgrade 仅在表为空时允许删除，存在运行历史则明确阻断，避免回滚丢数据。

## 3. 验证矩阵

专用测试必须覆盖：

- revision/down_revision 唯一且 Alembic 只有一个 head；
- 从 `ar2_018` 升级后表、列、主键、唯一约束、索引、RLS/FORCE RLS、policy 和 grants 精确存在；
- `aos_runtime` 在两个租户 GUC 下只能读写本租户记录，不能读取或更新另一租户；
- 重复 upgrade 不改变已合格结构；预置漂移结构必须失败关闭；
- 空表 downgrade 成功，非空表 downgrade 被阻断；
- 隔离恢复库克隆升级到新 head 后，canonical SourceReadiness 不再因缺表返回 500，而是返回结构化的真实阻断状态；
- A0-V 采集器重跑、验证器通过，原 17 个 blocker 只允许按新事实变化，不能人工改绿。

## 4. 执行边界与退出条件

迁移目录不在当前 A0-V 主租约中。编码前必须登记一个由 `m1` 独占、只覆盖上述 migration 文件的子任务租约；测试和证据仍落在现有 A0-V 租约范围内。

仅允许对隔离恢复数据库克隆执行 migration apply/downgrade 验证。禁止对共享、生产或来源不明数据库执行迁移；禁止 Provider、外部发布、经营写入和 230 L0。

退出条件为：专项测试、迁移链、RLS、downgrade 护栏和恢复库接口复验全部通过，并形成新证据提交。若出现第二张 legacy-only 缺表，则停止扩张本迁移，重新做 managed-schema 消费者清册和下一份最小修复方案。
