# b55｜正式安装命令连接身份只读与隔离验证

## 现场命令与结果

| 检查 | 可复核命令 | 退出码与结果 |
| --- | --- | --- |
| 当前栈 | `colima list`、`docker --context colima-aos-extension ps`、`lsof -nP -iTCP:18435 -iTCP:8080 -iTCP:8434 -iTCP:18181 -sTCP:LISTEN` | PG/API/Web 在，18181 无监听；合并 lsof 因无18181 返回1，不代表前三者失败 |
| 健康 | `curl http://127.0.0.1:8080/v1/health`、`/v1/ready`、`http://127.0.0.1:8434/aip/skill-publish` | 均 HTTP 200；最初误查 `/health`、`/ready` 得404，已改正确路径 |
| 当前角色，只读 | `docker --context colima-aos-extension exec aos-a0v-recovery-pg psql -U aos_app -d aos_current_preview_20260927 -X -A -F '|' -c 'BEGIN READ ONLY; SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolbypassrls FROM pg_roles WHERE rolname IN (...); ROLLBACK;'` | exit0：aos_app LOGIN/SUPERUSER/BYPASSRLS，aos_runtime NOLOGIN/NOSUPERUSER/NOBYPASSRLS；当前角色成员表无直接成员 |
| 函数 ACL，只读 | 同库 `BEGIN READ ONLY; SELECT has_function_privilege('aos_runtime','extension_runtime_uninstall_commit_ar2_018(uuid,bigint,text)','EXECUTE'), has_function_privilege('aos_app',...,'EXECUTE'); ROLLBACK;` | exit0：runtime=false，app=true；`ar2_018` 仍拒绝 superuser session_user，故当前预览 app 登录不能作为正式卸载命令 |
| PG16 低权成员机制 | 无卷 `aos-b54-acl-pg` 内 `BEGIN; CREATE ROLE aos_b55_probe NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT; GRANT aos_app TO aos_b55_probe WITH INHERIT FALSE, SET FALSE; SELECT pg_has_role(...,'MEMBER'/'USAGE'/'SET'); ROLLBACK;` | exit0：MEMBER=true、USAGE=false、SET=false；无持久角色改动。这仅证明数据库可表示窄成员，不证明完整表 ACL/函数/Receipt 正向 |

## 代码与方案对账

- `control_wiring.py` 两个正式组合根均用默认 `PostgresInstallationStore()`；`installation_store.execute_idempotent` 在同一连接中绑定租户、取幂等锁、执行 handler、写 CommandReceipt。`db.connect` + TI6 `apply_asset_transaction_scope` 可切 aos_runtime。`ar2_018` 只给 aos_app 函数 EXECUTE，另核验 session_user 必为非高权 aos_app 成员。
- 因当前 `aos_app` 是超管且 runtime 无 EXECUTE，不能通过改当前 API DSN、给 runtime GRANT、或用当前预览 superuser 完成正式安装命令。b55 没有生产代码、schema、真实库写或凭证变更；这项实例阻塞保持失败关闭。
- 下一 b56 在 signed disposable PG 证明专用非高权登录的 `MEMBER=true/USAGE=false/SET=false`、显式最小函数及表授权、同事务 Installation CommandReceipt/终态和租户/重复负门；然后才设计正式连接模块及唯一136迁移协调。当前正式 OIDC/Issuer/Reader/Owner、八配置/六 Binding、首链仍未齐，Host/worker/Provider继续关闭。
