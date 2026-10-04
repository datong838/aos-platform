# b61｜正式命令身份来源与唯一136依赖只读核验

## 当前实证

| 核验 | 命令/范围 | 结果 |
| --- | --- | --- |
| 当前库与角色 | 当前 PG `BEGIN READ ONLY` 查询 `alembic_version`、`pg_roles`、`has_function_privilege`，末尾 ROLLBACK | exit0；库 `aos_current_preview_20260927@a0v_135`；`aos_app` LOGIN/SUPERUSER/BYPASSRLS，`aos_runtime` NOLOGIN/无 `ar2_018` 卸载函数 EXECUTE；未见 `aos_installation%` 角色。 |
| 迁移文件 | `rg --files services/aos-api/alembic/versions | rg 'a0v_13[456]'` | exit0，只见 134/135，无 136。`ar2_018` 将函数 EXECUTE 给 `aos_app`，函数显式拒绝高权 session_user，故当前预览 app 不能当正式卸载身份。 |
| 当前配置 | `.env` 仅查专用变量名是否存在、LaunchAgent API plist | 专用 `AOS_INSTALLATION_UNINSTALL_COMMAND_CREDENTIAL_FILE` 未设置；b60 代码 opt-in 未在当前实例启用。 |
| 已知仓外文件 | 精确 `find` 当前 build/recovery 的身份文件名；对 test-only 文件只读 mode/JSON 键，不打印 DSN/密码 | 已见 `.aos-testonly-bg00cf-3r_lw6yp/api-service-identity.json`，0600，键 `dbname/host/pgpassFile/port/user`；路径明示 test-only，且非 b60 `schemaVersion/role/dsn`，不能接当前命令。此盘点不证明全机器绝对没有其他凭证，只证明已知启动路径无正式来源。 |

## 唯一136前置矩阵

| 子合同 | 已有 isolated 证据 | 正式缺口 |
| --- | --- | --- |
| Capability operation/Receipt | b46 test-only definer blocked/Receipt 原子负门，b45 同连接 Reader | 可信 evaluator 对当前签名字节、信任根、八依赖的 DB 可验证证明与 available 正向仍缺，不能提前生产授权。 |
| 安装/Registry 来源锁 | b49/b50 两种撤销竞争；b51 旧 rollback 禁入 | `FOR SHARE` 所需列级 UPDATE 的 test-only definer 权限不能直接照搬；正式最小锁入口/安装换代并发仍待联合证明。 |
| 卸载命令角色 | b56～b60 isolated 低权、同事务双 Receipt、signed 两代次、保护文件预检 | 当前库无正式专用角色/ACL，当前凭证文件和签发/轮换来源未证；`ar2_018` 仅 app EXECUTE，而预览 app 高权被函数拒绝。 |
| 当前卷切换 | b25 独立全备/全恢复既有证明；b59 最新栈重启 | 唯一136冻结并在 disposable 全链演练后，须新一致备份、全库恢复和零执行窗口；本波不执行当前卷 DDL。 |

## 结论与继续项

- 当前正式实例的卸载/重装、Growth1.13 发布与首链未通过。缺正式身份仅阻断当前实例；继续可独立的可信 evaluator、来源锁和产品配置/绑定研发。
- 下一波 b62 应先选唯一136中不依赖正式凭证的最小 RED：可信 evaluator 结果不能由可写 GUC/普通 issuer 假冒，或安装换代竞争；以隔离 PG/签名制品证明，保留当前库只读。Goal active，不设 blocked，不 push。
