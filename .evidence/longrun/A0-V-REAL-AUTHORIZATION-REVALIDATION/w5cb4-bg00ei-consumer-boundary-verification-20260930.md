# BG00EI｜consumer身份与activation回执来源验证

本波按plan新增a0v119与隔离PG测试；未改旧migration、HTTP/页面或a0v116 active gate。code head=a0v119；当前真实库仍a0v118，不得声称最新迁移已部署。

| 验证命令（相对services/aos-api） | 退出码/结果 |
|---|---|
| 旧代码 `.venv/bin/python -m pytest -q tests/aip/test_network_consumer_boundary_pg.py --tb=short --show-capture=no` | 1：6 failed/2 passed。role缺失4项；runtime与issuer均可插入activation Receipt，未抛InsufficientPrivilege，2项真实RED。普通publish Receipt和active禁入原本通过。 |
| 实现后同文件 + test_network_approval_precheck_expiry_pg.py + test_aip_network_policy_action_producer.py | 初轮0：23 passed。补4项role漂移验证后0：27 passed，22.09s，7条既有框架告警。 |
| `python -m py_compile` 新migration与测试；`git diff --check` | 0。 |
| 当前卷只读 `docker --context colima-aos-extension exec aos-a0v-recovery-pg psql -X -v ON_ERROR_STOP=1 -U aos_app -d aos_current_preview_20260927 -Atc "BEGIN READ ONLY; SELECT ...; COMMIT;"` | 0：database=aos_current_preview_20260927，migration=a0v118，consumer_roles=0，new_receipt_trigger=0。未升级当前库。 |

只读复核SELECT可复现为：
```sql
SELECT json_build_object('database',current_database(),
 'migration',(SELECT version_num FROM alembic_version),
 'consumer_roles',(SELECT count(*) FROM pg_roles WHERE rolname IN ('aos_network_consumer_call','aos_network_consumer_owner')),
 'new_receipt_trigger',(SELECT count(*) FROM pg_trigger WHERE tgname='aip_network_activation_receipt_guard_a0v_119'));
```

测试使用标准pytest一次性aos_test_*_ti4_test库；真实执行migration、RLS/role/trigger/INSERT/锁等待，没有用mock替换这些行为。新role为集群对象，因此仅出现在test-only PG集群，不代表真实凭据创建。role漂移测试在事务内模拟LOGIN、正反membership和显式SELECT授权，拒绝后rollback恢复。普通Receipt与active反例均rollback；测试库由原fixture清理。未读商城源、调用Provider、创建Run或写当前真实库。

复审：两consumer角色均NOLOGIN/NOINHERIT且非特权，无membership、对象所有权和表ACL；不授任何DML或EXECUTE。已有同名role漂移直接失败，不自动覆盖部署配置。Receipt trigger为SECURITY INVOKER、固定pg_catalog，仅network_policy.activate需session_user=consumer_call且current_user=consumer_owner。正常caller不能SET owner，现无受控函数，故没有生产消费正向。DBA能改变角色/DDL属于可信部署边界，本门不宣称防御超级管理员。

缺口：尚未安装原子consumer函数、owner最小表/列权限和独立RLS；active gate仍关闭。正式caller凭据、issuer/checker身份、当前迁移、Host和首链均pending。下一波BG00EJ按本波plan的固定参数/锁序/hash/时效/Receipt合同实现受控原子函数；必须证明并发唯一、回滚、跨租户、撤销到期、普通DML不能旁路。当前库升级仍独立备份/克隆/零执行窗口，不能随API重启自动迁移。
