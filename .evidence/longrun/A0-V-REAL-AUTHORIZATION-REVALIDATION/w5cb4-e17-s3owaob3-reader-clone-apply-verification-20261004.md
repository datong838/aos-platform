# E17-s3o-w-ao-b3｜新鲜恢复克隆 Reader 事务 apply/回滚验证

## 目标与来源

- 源/目标和新全备的创建、SHA、完整 `pg_restore`、26/26 表摘要见同前缀 fresh-restore verification。源是原权威卷 `aos_current_preview_20260927@a0v_135`，本波一切 DDL 仅在不同卷的新库 `aos_e17_s3owaob3_restore_20261004`。完整恢复后才编码 apply；先方案、后 RED/最小实现。
- 管理凭据仅从 test-only 容器 inspect 在测试进程内读取；临时0700目录/0600 admin passfile、Reader 原始密码文件及 pgpass，退出后删除。脚本不打印密码，不支持 current/apply-current，额外要求 `AOS_E17_READER_APPLY_TEST_ONLY=1`。

## RED、原链、回归

| 门 | 命令与结果 |
| --- | --- |
| RED | `AOS_DOTENV_DISABLED=1 AOS_E17_READER_APPLY_TEST_ONLY=1 PYTHONPATH=../..:. uv run pytest -q tests/aip/test_e17_s3owaob3_reader_apply_pg.py`（API 目录） | 缺 `FRESH_DATABASE`/apply，收集失败 exit2。 |
| 故障回滚 | 同一真实 PG 测试调用 `apply_fresh_clone(...,fail_after_policy=5)` | 抛 `READER_CLONE_INJECTED_FAILURE`，独立事务整体回滚；Reader role0、同名policy0、Installation1、Receipt6。 |
| 正向与重复 | 同测试用真实 CLI `--target fresh-clone --apply-fresh-clone` | exit0、Reader role1/17条 SELECT policy；原 `ReadinessReaderConnectionFactory` 独立登录全局 CapabilityRevision10、同租户 EvidenceBundle 当前空态0；重复 apply 被 `READER_CLONE_CATALOG_REQUIRED` 拒绝且1/17/1/6不变。test-only 精确清理后角色/策略0/0。测试1 passed/7既有 warning，exit0。 |
| 相邻回归 | b2 只读预检、Reader PG、Capability issuer PG、Binding API 四文件 | 25 passed/8既有 warnings、exit0；新代码及测试 `py_compile` 与目标 diff check exit0。 |
| 收口复审 | b2 预检＋b3 真实 PG 两文件 | 修正脚本顶部说明，并加缺显式 apply／旧 clone 混用拒绝测试；5 passed/7既有 warnings、exit0；`py_compile`、`git diff --check` exit0。 |
| 最终只读对账 | 源与新克隆各查版本/Reader role/同名policy/Installation/RegistryReceipt | 双方 `a0v_135/0/0/1/6`；来源库没有 apply、Host/worker/Provider仍关闭。 |

## 方案/代码复审与边界

- `scripts/a0v_e17_reader_maintenance.py` 先固定独立 Docker context/容器/卷、库135、备份 SHA/完整恢复26表证据、私有凭据，再在 SERIALIZABLE 单事务内检查18表/17租户表 FORCE RLS、角色/策略空态、安装/Receipt计数；仅对新鲜 test-only 库 CREATE NOINHERIT/NOBYPASSRLS非 owner LOGIN、18表 SELECT、17张租户表 FOR SELECT 策略。任一步异常回滚；对已有角色/策略不自动重建。实际 Reader 工厂再核无额外读写、owner/runtime 成员和租户事务只读。
- 本波没有在新鲜克隆插入 test-only 业务行；冻结 exact/错租户/撤销链沿用 s3o-w-an 已实跑的独立恢复克隆证明，不把同租户空态冒充正向经营事实。新鲜克隆 apply 成功仅证明角色/ACL/策略事务与独立连接，不证明当前实例有正式私有凭据、OIDC/API Owner、八类配置、六 Binding 或首链。
- 当前正式 Reader/issuer role仍0。当前库切换必须另取切前新一致备份并全库恢复、正式私有凭据来源、API/Web/Host 零执行窗口和精确安装/Receipt比对；没有这些条件不能复用 test-only 登录或把当前库切到新角色。
