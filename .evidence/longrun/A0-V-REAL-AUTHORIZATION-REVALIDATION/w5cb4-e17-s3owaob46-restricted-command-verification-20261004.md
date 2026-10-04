# E17-s3o-w-ao-b46｜隔离受限 evaluate 命令原子负门

## 方案/代码复审

- 方案先行，复习 231-3/BIND-1、b41 安装锁、b44 伪 evaluate 与 b45 同事务 Reader。仅新增 disposable full-schema PG 测试；当前生产代码、Alembic 和权威卷仍135，均未改。
- 随机 NOINHERIT/NOBYPASSRLS LOGIN 调用者对 `aip_capability_binding` UPDATE、`aip_agent_registry_receipt` INSERT 均无权；随机 NOLOGIN/NOBYPASSRLS 函数 owner 只获两表精确读写及租户 RLS。测试函数 `SECURITY DEFINER` 固定 `search_path=pg_catalog`、检查 `session_user` 和精确 org/project GUC，PUBLIC EXECUTE 撤销，只授调用者 EXECUTE。函数不接受任意 readiness/hash/有效期，唯一输出是 `blocked`、`TRUSTED_EVALUATOR_PENDING`、空 snapshot/expiry；不会产生 active/runnable。
- 函数在同一事务以 org/project/binding/version CAS 更新 Binding 并插入唯一 evaluate Receipt；同 key 重放只读返回原 revision，同 key 改版拒绝。故意制造 Receipt 主键冲突时，已发生的 Binding UPDATE 随事务整体回滚。错租户、无 GUC、无 EXECUTE、错误版本、直接 Binding/Receipt DML 均拒；角色/函数/策略精确清理，角色残留0。测试业务行留在可销毁测试库，未触真实库。
- **边界**：这是原子失败关闭的命令形状证明，不是可信完整 evaluate。尚未把 b37/b41 当前签名来源锁或 b45 当期依赖计算合入函数，故 b34/b37/b44 strict xfail 和首链禁入保持。不能将本波 test-only 函数迁往当前库或宣称正式身份已齐。

## 可复核命令

| 命令 | 结果 |
| --- | --- |
| `AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings tests/aip/test_e17_s3owaob46_restricted_evaluate_command_pg.py` (`services/aos-api`) | 初次 RED exit1：函数不存在，`UndefinedFunction`；设定 test-only 受限函数及负门后 exit0，1 passed/7 warnings。 |
| 同目录追加 b45 事务 Reader、b22 operation/Receipt、BIND readiness 四文件相邻回归，`-k 'not downgrade'` | exit0，23 passed、4 xfailed、7 warnings。 |
| `python3 -m compileall -q services/aos-api/tests/aip/test_e17_s3owaob46_restricted_evaluate_command_pg.py`；`git diff --check` | 均 exit0。 |

## 下一门

在新的 disposable 完整签名安装克隆上，把 b37 当前 signed source 选择、b41 安装/Registry 撤销锁与本波原子命令按固定顺序组合，并用两连接证 revoke/replace 竞争；随后接 b45 事务内真实依赖重算与不可伪造来源证明。正式唯一136和当前卷切换需新备份、全恢复、零执行窗口、正式 issuer/Reader/OIDC/Owner。当前库只读、Host/worker/Provider关，不读商城源/旧12Run/230 L0、不手工 Run、不 push。
