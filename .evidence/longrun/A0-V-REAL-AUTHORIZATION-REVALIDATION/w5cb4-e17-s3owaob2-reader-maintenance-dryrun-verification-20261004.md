# E17-s3o-w-ao-b2｜恢复克隆 Reader 维护默认只读预检

## 范围

- 按 231-4、D-wave 2026-10-04 与同前缀文件级计划，只为现存 `colima-aos-a0v-test-only/aos-a0v-test-pg`、库 `aos_e17_s3owan_restore_20261004` 实现 `scripts/a0v_e17_reader_maintenance.py --target clone`。没有 current/apply 模式；不建角色、不改 ACL/策略/表、不碰当前真实库或 Host。
- 管理凭据来自 test-only 容器已有环境，仅在命令进程内读取，放入0700临时目录/0600 passfile，执行后删除；脚本只打印非秘密 gate 结果。脚本读取固定旧全备 SHA `be40a303…bbcc` 和完整 `pg_restore` 证据，不把当天仅 SHA/TOC 的新备份冒充恢复证明。

## RED 与验证

| 检查 | 命令或只读事实 | 结果 |
| --- | --- | --- |
| RED | `AOS_DOTENV_DISABLED=1 PYTHONPATH=../..:. uv run pytest -q tests/aip/test_e17_s3owaob2_reader_maintenance.py`（API 目录） | 缺 `scripts.a0v_e17_reader_maintenance`，收集失败 exit2。 |
| 纯边界测试 | 同命令在最小实现后 | 4 passed，exit0；缺表、RLS非FORCE、旧 head、角色/策略冲突、当前卷/容器、宽权限或 symlink passfile、无 target/current/apply 均拒绝。 |
| 首次克隆实跑 | 从 test-only 容器凭据创建临时私有 passfile，再运行 `services/aos-api/.venv/bin/python scripts/a0v_e17_reader_maintenance.py --target clone --admin-passfile <private>` | 失败关闭 `READER_CLONE_CATALOG_REQUIRED`，子进程 exit2。原因是 runner 先沿用旧恢复文档“public 11序列”；源和克隆现时只读 `pg_sequences` 均12、`pg_class relkind='S'` 双方12名称逐项相同。旧恢复文档已补更正；门值改成12，没有重做备份或迁移。 |
| 修正后克隆实跑 | 同一命令，真实独立卷/库，repeatable-read read-only 管理连接 | `READER_CLONE_DRY_RUN_GREEN`、version135、18表、`current_database_write=false`，exit0。 |
| 相邻回归 | 新测试、原 Reader PG、Capability issuer PG、Binding API 四文件 | 25 passed/8既有 warnings，exit0。两文件 `py_compile` 与目标 `git diff --check` exit0。 |
| 前后快照 | 克隆 `psql BEGIN READ ONLY` 查询版本/表/序列/角色/同名策略/Installation/RegistryReceipt | 前后 `a0v_135/592/12/0/0/1/6` 不变，exit0；源库序列同为12，无当前库写入。 |

## 方案/代码一致性与剩余风险

- 默认 CLI 强制显式 `--target clone` 与私有 passfile；Docker context、容器、唯一独立卷、端口、库、登录、旧备份 SHA、恢复证据、18表/FORCE RLS、角色及策略空态必须同时满足。SQL 全在独立 repeatable-read read-only 事务内；无 current/apply 参数，直接传入返回 argparse exit2。符合本切片计划的只读门。
- 固定旧备份与已有克隆仅证明预检可读，且该克隆在前波 test-only 正反链中留有3对 test-only bundle/revoke 行；它不是即将写入当前库的全新恢复演练。现有正式 Reader/issuer role 仍缺、OIDC/Owner/八配置/六 Binding/首链 pending；当前角色切换仍需新一致备份、独立完整恢复、正式私有身份及零执行窗口。Host/worker/Provider 继续关闭。
