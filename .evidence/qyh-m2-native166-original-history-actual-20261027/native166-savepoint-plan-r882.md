# M2 canonical a0v_166 原生 savepoint 方案 r882

时间：2026-10-31（Asia/Shanghai）

## 目的与归属

在已恢复的 canonical 隔离 PostgreSQL 上，使用当前产品仓中的原 `a0v_166_dispatch_refresh_activation_chain.py` 与原 `NativeMigrationBinding`，执行一次真实 Alembic `upgrade()` 的 savepoint 诊断并回滚，证明原历史、权限封印、writer 和旧 key 能在真实 PG16 上完成“升级后核验、回滚后完全恢复”。该结果只是 M2 原生迁移前置，不是 M2、安装生命周期或真实经营验收。

主动作继续归属活动 Task `qyh-m2-native166-original-history-actual-20261027-h1029-h1031`。连接通道不借用仍由 `qyh-skill-producer-native163-20261028-h1029-h1031` 持有的 `18455`；另登记短生命周期 companion Task，仅持有新 `127.0.0.1:18458` 转发、本线程 SSH 进程及独立连接证据目录。两个 Task 的产品/资源职责不互相扩张。

## 已复核方案军规

- 产品/技术依据：`native-canonical-binding-correction-plan-r21.md`、`native-schema-provisioning-plan-r16.md` 与 `2026-10-23-M2测试夹具资源归属施工清单.md`。
- canonical 资源固定为容器 `8ad56b817e7c81db6ebf57ddfd4d064bb583ba79f80fbec4a9e78164eec5095f`、数据库 `aos_refresh_activation_native`、OID `16384`、cluster `qyh-canonical166-8af8248e67b4128101100eda`、当前 Alembic `a0v_165`。
- 只允许部署身份 `aos_app` 执行迁移诊断；不得把 restricted Owner 身份用于 DDL，也不得把部署管理员用于业务 Owner 调用。
- 不修改 `a0v_166`、`test_dispatch_refresh_activation_chain_pg.py` 或产品服务源码；直接消费当前冻结字节及 SHA。
- 不接当前业务库、不读商城源、不启动 Host/worker/Provider/Schedule、不使用旧 journal、不重放 unknown、不代真人审批、不 push。

## 文件与 RED/GREEN

新增证据代码：

1. `run_native166_savepoint_r882.py`：只接受环境变量中的无密码本地 DSN；建立真实 SQLAlchemy+psycopg 非 autocommit 事务，设置精确租户 GUC，构造 `NativeMigrationBinding`，调用原 fixture 身份门与原 savepoint 测试；外层事务最终始终 rollback，只输出无凭据 JSON。
2. `test_run_native166_savepoint_r882.py`：先以 fake engine/connection 验证缺 DSN、非 loopback、错误端口/数据库/用户、错误 OID/cluster/hash、非事务和结果泄密均 fail-closed；不连接网络或 PostgreSQL。
3. `native166-savepoint-result-r882.json`：保存 source hash、连接身份摘要、升级/回滚已知结果、执行前后 key/history/seal/writer 摘要，不保存 DSN、密码、SQL 行正文或敏感凭据。

RED 必须先证明 runner 在缺失精确 admission 时拒绝；GREEN 后才允许实际连接。runner 不复制迁移或权限逻辑，只注入原 `NativeMigrationBinding` 并调用原测试。

## 实际执行顺序

1. 复核 handoff、HEAD、dirty、Task/Lease、容器 ID/IP、卷/网络、端口 `18458` 空闲、当前 SSH 配置与产品/测试 SHA。
2. 登记唯一 companion Task：只包含独立证据目录、`18458 -> 172.24.0.2:5432` 与本线程 `native166-savepoint-ssh` 进程，排除 DB/产品/业务权限。
3. 写 RED 测试并确认失败；最小实现 runner 后跑离线测试、现有 native admission/role separation 专项与静态编译。
4. 使用当前 Colima SSH 配置启动一个前台 `-N` 本地转发；核 PID、argv、listener 和远端固定 IP。
5. 先以 `aos_app` 做只读身份核验；仅当 DB/OID/cluster/PG16/owner/superuser/tenant/Alembic165/至少2条历史全部精确匹配时，执行 runner 一次。
6. runner 内由原测试执行 `begin_nested()`、真实 `migration.upgrade()`、升级后断言和 savepoint rollback；外层事务再 rollback。随后另起只读连接核对 Alembic仍165、旧 key/history/seal/writer摘要完全恢复。
7. 关闭且只关闭本轮精确 SSH PID，确认 `18458` 无监听；完成 companion Task。unknown 时只读对账，不重发。

## 完成标准与停止条件

- 原测试真实运行且返回 known success；升级中 key 变为含 `activation_operation_id`，历史/封印/writer符合原断言；savepoint 和外层事务回滚后旧状态逐项恢复。
- 执行前后持久状态一致，容器/卷/网络/角色不改；无产品文件修改和业务副作用。
- 任何身份、SHA、权限、历史数量、锁等待、连接或 rollback 断言不匹配，立即停止；不修库、不放宽测试、不自动重试迁移。
- 即使 GREEN，工程仍为 2/8、真实业务仍为 0/8；下一步仍需 restricted Owner 独立诊断、双安装真实刷新及完整安装/配置/禁入/恢复/卸载重装联合验收。

## 回滚

数据库回滚由原测试 savepoint 加 runner 外层事务双层保证；连接回滚为关闭精确 SSH PID。无资源删除、无容器停止、无卷重建。若进程状态 unknown，仅按 PID/start/argv/listener 只读对账，不使用宽泛 kill。
