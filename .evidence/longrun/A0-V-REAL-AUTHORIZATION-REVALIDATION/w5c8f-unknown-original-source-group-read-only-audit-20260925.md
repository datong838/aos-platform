# W5c8f unknown 原源组只读路径停止审计

## 结论

本波未实现新证据层：现有 `AnalysisDataRequirementRouteReader.read_unknown` **不能**直接包装为 PostgreSQL 只读事务的历史源组解析器。它在 `_read` 中调用 `AnalysisAdvanceHostService._accepted_occurrence_reference`；后者对 `automation_occurrence` 和 `automation_occurrence_dispatch_attempt` 执行 `SELECT ... FOR SHARE OF o,a`。该查询本身不修改行，但在 PostgreSQL `transaction_read_only=on` 下会抛 `ReadOnlySqlTransaction`，因此不满足 W5c8f 的“强制只读”约束。若改用可写连接绕过会损害本波安全边界；按方案停在审计，不包装旧路径。

## 证据和范围

- 静态调用链：`AnalysisDataRequirementRouteReader.read_unknown` → `_read` → `_accepted_occurrence_reference` → `FOR SHARE OF o,a`。该函数还会做持久 Receipt 回读；不能因为返回 route 就把它视作纯 SELECT。
- 无业务行读取的本地 PostgreSQL 复现：在 `aos_meta` 将事务设为 read-only，针对 `public.meta_org WHERE FALSE` 执行 `SELECT 1 ... FOR SHARE`，即使匹配 0 行仍收到 `psycopg.errors.ReadOnlySqlTransaction: cannot execute SELECT FOR SHARE in a read-only transaction`。第一次误选尚无 `automation_occurrence` 的轻量 DB 得 `UndefinedTable`，第二次用 TEMP TABLE 得成功（PG 允许只读事务锁临时表）；两者均不作为正式判据，正式判据是既有永久表的零行查询。未触商城源数据。
- `PipelineSnapshotGroupLocator` 自身能核组绑定/manifest，但要从原 Analysis Receipt 的 Occurrence 找 ProductEventOrigin 的 source run，须另外设计不加行锁的历史路径；不能只把业务 `RunRef` 当源 Run ID。
- W5c8d 双 Receipt 诊断仍有效，W5c8e Host/Store authority 缺口仍在；本波没有状态写入、Worker 接线、真实服务重启或真实 DB 迁移。

## 后继

W5c8g 先做独立纯只读历史源组解析方案：原 Outbox/Requirement → 精确 PREPARING Receipt → accepted Occurrence 的历史 Receipt/Origin → 唯一保存源组，避开 `FOR SHARE`，对所有替代查询做只读事务 PG 正/负例。仍不接 `reconcile_completed`。Host-fenced 单事务 `unknown` 对账和过期 `claimed` 状态迁移继续分开。
