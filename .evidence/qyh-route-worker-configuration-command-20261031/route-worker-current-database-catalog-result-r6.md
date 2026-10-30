# 后台配置保存通道当前业务库只读目录核验结果 r6

时间：2026-10-31（Asia/Shanghai）  
对应方案：`route-worker-current-database-preparation-plan-r5.md`

## 结果

使用正式 API 同一只读数据库身份，完成了目标库、运行资源、目标回执表、既有租户策略和权限矩阵的无副作用核验。全程 `default_transaction_read_only=on`、`transaction_read_only=on`，没有写数据库、配置文件或凭据。

## 已确认事实

- 当前数据库：`aos_meta_head`，PostgreSQL `16.14`；
- 当前运行资源：Colima `aos-extension` 中的 `qyh-restored-pg-20261011`；
- 当前命名卷：`aos-qyh-history159-prepared-data-20261011`；
- 目标表：`public.bundle_installation_command`；
- 目标表已经启用并强制 RLS；
- 表以 `(org_id, project_id, operation, idempotency_key)` 为主键，不依赖序列；
- 更新、删除和截断均有不可变触发器保护；
- 既有策略 `tenant_scope_bundle_installation_command_ti6` 只面向 `aos_runtime`，租户范围来自 session setting；
- 专用角色 `aos_route_worker_lifecycle_command` 不存在；
- 专用策略 `route_worker_lifecycle_command_scope` 不存在；
- 当前正式 API 登录 `qyh_restored_api_login` 对目标表没有 SELECT、INSERT、UPDATE、DELETE 或 TRUNCATE 权限；
- `PUBLIC` 只有 public schema 的 USAGE，没有目标表权限。

## 关键判断

1. 不需要、也不允许为了本功能切换目标表的表级 RLS；
2. 既有 `aos_runtime` 策略不能替代专用保存通道，因为它依赖 session setting，且该角色在目标表上还有 UPDATE、DELETE 权限；
3. 后续仍需要独立专用登录、只授 SELECT/INSERT 的表权限，以及硬编码 `org-org/dev-project` 的专用策略；
4. 当前只读登录无权读取 `alembic_version`，因此迁移头尚未由本轮证明。迁移头必须通过另一个既有可信只读入口核对，不能给正式 API 登录扩权；
5. 在迁移头、备份恢复门和隔离恢复库演练完成前，不进入当前业务库变更。

## 方案一致性与风险

- 只读现状核验：已完成；
- RLS 兼容性门：目标表已启用并强制 RLS，不需要表级切换；
- 专用角色/策略：确认尚未准备；
- 凭据和 POST：继续关闭；
- 当前业务库写入：未发生；
- 主要剩余风险：迁移头尚未由可信入口核清，专用策略尚未在权威库恢复副本中演练。

本轮闭合的是安全准备事实，不代表当前客户已完成配置，也不计入真实经营首链或八阶段业务验收。
