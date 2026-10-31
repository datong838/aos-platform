# Guard issuer 专用连接增量方案 r1

上游方案：`../qyh-m2-guard-policy-human-approval-entry-20261031/plan-r1.md`。

本增量只补独立 issuer 的部署连接边界，不启动服务、不改数据库：

1. 仅允许回环地址、精确数据库名、0600 passfile、0700 父目录。
2. 登录角色固定 `aos_guard_approval_issuer`，事务内 `SET LOCAL ROLE aos_runtime` 并绑定精确 tenant scope。
3. inquiry 使用 `REPEATABLE READ READ ONLY`；decision 使用 `SERIALIZABLE READ WRITE`。
4. 每次连接重核 database/login/current role/tenant/超时/RLS 危险权限、成员关系和 read-only 状态。
5. 配置文件只接受固定字段；不返回或记录 passfile 内容，不接受环境 `PGPASSWORD/PGOPTIONS` 覆盖。
6. 只做离线 Fake 正负测试和编译。真实角色、凭据、socket、current stack preflight 后续在独立资源 Task 执行。

完成条件：错误角色、owner/superuser/bypassrls/inherit、跨租户、错误隔离级别、宽权限、非私有文件、环境覆盖全部 fail-closed；合法 inquiry/decision 连接能作为 `GuardPolicyIssuer` 的统一 `connect_factory(scope, read_only)` 使用。
