# Guard issuer 专用连接检查点 r1

时间：2026-10-31 23:10 +08:00

- 新增固定 `aos_guard_approval_issuer` 的回环 PostgreSQL 连接配置与连接工厂。
- inquiry 固定 `REPEATABLE READ READ ONLY`，decision 固定 `SERIALIZABLE`；每次事务绑定 `aos_runtime` 与精确 tenant GUC。
- 每次连接重核数据库、login/current role、租户、超时、危险权限、owner 成员、额外角色、隔离级别与 read-only。
- 新增固定字段私有配置加载与只读 preflight；返回 `businessAuthorized=false`。
- 8 项后端定向测试通过（连接 4 + 产品 issuer 4），compileall 与 diff-check 通过。
- 未创建角色/凭据/socket，未连接当前业务数据库，未启动 issuer，未产生审批、消费或激活。

下一步：为独立 issuer 登记一次性隔离 PG/Unix socket native 矩阵；通过前 current stack 保持未配置、默认关闭。工程2/8、真实0/8不变。
