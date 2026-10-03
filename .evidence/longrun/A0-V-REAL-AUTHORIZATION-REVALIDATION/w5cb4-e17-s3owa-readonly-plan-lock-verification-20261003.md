# W5CB4 E17-s3o-w-a｜职责 Plan 只读锁冲突调查

日期：2026-10-03。沿 `w5cb4-e17-s3ow-readonly-source-version-plan-20261003.md` 的第1步，使用无业务卷的隔离 `aos-ar1c-pg:18432/postgres`，临时 schema/非 owner 无写权角色，结束时只移除本试验创建的临时 schema/角色。当前权威数据库只读、不启 Host。

| 隔离 SQL 操作 | 只授 `SELECT` 的实际结果 |
|---|---|
| 普通 `SELECT` | OK |
| `SELECT ... FOR SHARE`、`FOR KEY SHARE`、`FOR NO KEY UPDATE`、`FOR UPDATE` | 均 SQLSTATE `42501`，`InsufficientPrivilege` |
| `LOCK TABLE ... IN SHARE MODE` | `42501` |
| `LOCK TABLE ... IN ACCESS SHARE MODE` | OK，但该锁与写者 `ROW EXCLUSIVE` 兼容，不能充当版本稳定门 |

在原 `test_current_configuration_sources_pg.py` 新增严格 xfail，要求只读运行角色仍能通过原职责 Plan 当前版读者；实测 `psycopg.errors.InsufficientPrivilege`，`21 passed/1 xfailed`、exit0。xfail 只记录未闭合的正向合同，不是 GREEN。`git diff --check` exit0。

复核原 `AipProductionContractStore` create/revise/freeze 与 `w2_002_eval_responsibility`：原 migration 把 Plan head 的 SELECT/INSERT/UPDATE 和 revision 的 SELECT/INSERT 都授 `aos_runtime`；冻结版、head 推进和生产合同 Receipt 在原 Store 同事务。仅在 Host 加 ACL 门会阻止冒用，也会阻止原行锁读取；仅撤销 ACL 或移除行锁均不足以证明并发稳定。候选方向是由正式独立 issuer 写、数据库层约束所有 head 变更与消费读者共享短事务协调协议；先定义失败模式、锁顺序与最小授权，再做隔离 RED/实现，不直接迁当前库。

本波是有新 SQL 反证的调查门，未关闭 s3o-w 整体；正式独立登录、Receipt 防伪造、版本稳定协议、ACL 切换、配置正向、首链均待办。旧 RETURN/ToolBinding 发行可独立推进。浏览器不适用于 DB 锁权限调查。
