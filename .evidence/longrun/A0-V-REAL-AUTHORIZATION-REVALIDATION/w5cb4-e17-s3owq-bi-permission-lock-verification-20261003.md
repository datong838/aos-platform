# s3o-w-q｜受限 BI 权限只锁验证

- 基线：`m1@8598adc5`、Authority `AOS-001229`、代码/当前库 `a0v_135`。上位方案 231-3 与本波 `w5cb4-e17-s3owq-bi-permission-lock-plan-20261003.md`；当前真实库只读，Host/worker/Provider 关闭。
- RED：原签名 Growth1.13 全 schema 一次性库中，受限 `aos_bi_plan_issuer` 原 prepare 在 `meta_membership FOR SHARE` 触发 SQLSTATE42501，测试 exit1。
- 最小接线：`CurrentControlPermission` 只在真实 PG 连接且 `current_user` 精确为该发行者时调用两个受控函数，读取原 membership/marking 并保持 `FOR SHARE` 到原事务结束；其它角色走原 SQL。测试函数只在一次性库中建，`SECURITY DEFINER` 固定 `pg_catalog` search_path，限定 `session_user`、租户 GUC、原表过滤；撤销 PUBLIC，仅给发行者 EXECUTE。无 membership 或 marking 仍由原权限规则失败关闭。
- 本波 GREEN 范围：原签名全 schema 测试 `1 passed` exit0。测试主体 admin membership 命中、缺主体返回空、错租户拒绝；测试 marking 命中、错租户拒绝。并发更新 membership、删除 marking 均被持锁事务阻断（150ms `LockNotAvailable`）。原 prepare 越过当前权限后在六 Agent 的 `aip_agent_instance FOR SHARE` 再触发 SQLSTATE42501；Plan/BI Receipt 0，未声称正向发行。
- 相邻回归：BI、安装 Store/Service、发行身份、安装锁、当前权限 PG 共 `97 passed` exit0。当前权限 PG 旧测试中六个 `owner` 拒绝预期与现行 `control_policy.py` 的 `owner→admin` 映射不符，本波只修正测试断言。`py_compile` 与 `git diff --check` exit0。
- 真实当前库只读对账：测试发行角色0，三个 test-only 函数0，一次性数据库0，org-org/dev-project BI Plan0、BI prepare Receipt0。无当前库 migration/Grant、无商城源读、无 Run/Provider/Host 副作用。
- 复审与剩余风险：两个函数由表 owner 执行，依赖精确 `session_user`、显式租户过滤及 OIDC 服务的 actor 边界；测试函数不可视作正式权限。下一波 s3o-w-r 只处理六 Agent 的当前版本行锁和后续逐项拒绝，仍不直接授 BI issuer 表 UPDATE；正式函数迁移、凭据和当前卷切换须独立新备份、全链克隆、零执行窗口。八类正式配置、Host assignment/identity、正式六 Agent 与业务首链仍未通过。
