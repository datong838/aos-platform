# W5CB4 E17-s3｜正式 Skill Eval 来源与 Owner 只读核验

## 现场与代码对账

| 证据 | 结果 |
|---|---|
| `aos_current_preview_20260927` 只读事务 `select current_database(),version_num from alembic_version` | `aos_current_preview_20260927`,`a0v_135`，exit0；PG 在 `colima-aos-extension`，命名卷 `aos-a0v-recovery-pg-data`。先前默认 Docker context 是 test-only，改指定 extension 后查到正确容器；没有把 test-only 容器冒充当前卷。 |
| 正租户 `org-org/dev-project` 六表 `count(*)` | `aip_eval_run`、`aip_eval_report_revision`、`aip_eval_issuer_root`、`aip_eval_executor_identity`、`aip_eval_execution_receipt`、`aip_eval_case_execution_proof` 各0，exit0。`pg_roles` 中 `aos_aip_eval_writer` 数0；全局 published Skill 0。当前库未写。 |
| 配置引用 | 本执行 shell 的 `AOS_AIP_EVAL_WRITER_CREDENTIAL_FILE` 未配置；仓库 `.env` 也没有该键。仅检查键名/是否存在，未读取凭据值；不能据此断言其他未检查进程环境。 |
| 代码原路径 | `aip_eval_runner.py` 的 `run_by_contract` 与 `run` 对 SkillTemplate 分别硬拒 `formal Skill Eval executor authority unavailable`，尚无正式 Skill EvalRun Owner。`aip_eval_writer_connection.py` 默认关闭且拒 runtime/superuser 回退；`aip_eval_writer_authority_preflight.py` 要求当前 root/identity、succeeded Run、独立 writer role 与同一 serializable 租户事务；`aip_eval_writer_atomic.py` 只在合法 connector 后写双 Receipt/Report/sidecar。 |
| 现有失败关闭测试 | `test_aip_eval_writer_connection.py::test_missing_configuration_fails_closed` 与 `test_aip_eval_runner.py` 中 Skill 相关测试共3 passed、13 deselected，exit0。无生产代码修改。 |

## 判定与下一波

- 当前实例不能创建正式成功 Skill EvalRun，也不能用 test-only issuer/身份或 `aos_app` 超级身份替代。E17-s2c 隔离发布正向不等于当前实例已发布。Host/worker/Provider仍关闭，首链 pending；这是实例局部 authority 缺口，非整个 Goal blocked。
- E17-s3a 先从原 Run 创建与签发职责方案写文件级合同/RED，在隔离数据库证明独立 Owner 能否创建 exact Skill Run、writer 只消费其授权 Run；不得删除 Runner 硬拒后继续用 callback。另 E17-s3b 查 Logic/Route/Policy 原生产者可独立推进。真实库迁移/角色/凭据配置须独立安全波满足备份、克隆及零执行窗口。
