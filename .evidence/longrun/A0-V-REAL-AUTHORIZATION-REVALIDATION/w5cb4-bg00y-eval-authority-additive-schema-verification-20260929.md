# W5CB4 BG-00y｜Eval authority 空表迁移隔离验证

文件级方案 `w5cb4-bg00y-eval-authority-additive-schema-plan-20260929.md`。基线 `aos-platform/m1@6f6c9f69`、authority `AOS-000873`。改动仅 `services/aos-api/alembic/versions/a0v_112_eval_execution_authority.py` 与 `services/aos-api/tests/aip/test_aip_eval_authority_schema.py`；当前业务库不迁移。

## RED、迁移和测试

- 新建独立 `colima-aos-a0v-test-only/aos_bg00y_migration_20260929`，`REVOKE CONNECT ... FROM PUBLIC` 退出 0。今日 SHA256 为 `e527a55cbe5fca5b32754ac08257d3d1908a895ac16b68103794d3830e868b3d` 的 `a0v_111` dump 用 `pg_restore --single-transaction --exit-on-error` 完整恢复，退出 0，日志 0 字节；既有 BG-00x 库未覆盖。
- 新专项 RED：克隆 `a0v_111` 而预期 `a0v_112`、`pg_policies` 无新表政策，`2 failed`，退出 1。只在新克隆以 Alembic `upgrade a0v_112`，退出 0，日志明确 `a0v_111 -> a0v_112`。
- 首轮结构测试 `2 passed`。加数据库负例时，Judge 测试构造先触发必填字段 CheckViolation，后追加式断言预期异常类型与 SQLSTATE 55000 不符；两处均修正测试构造/类型。最终专项 `5 passed`；连同 BG-00w 签名验证器和 Eval Runner 相邻回归 `27 passed`，退出 0。
- 测试覆盖四表默认空、`ENABLE/FORCE RLS`、`aos_runtime` 仅 SELECT、栖月汇行对该角色可见而 `dev-org` 只读 canary 不可见、运行角色 INSERT 拒绝、Receipt 自然键重复/Target 身份冒充 Judge 拒绝、Receipt UPDATE 与撤销 DELETE/TRUNCATE 拒绝、同一身份重复撤销拒绝。机制行只在新克隆的事务内，测试后回滚，非正式签发/首链证据。
- `compileall -q` 和 `git diff --check` 退出 0。新克隆 `BEGIN READ ONLY` 回读 `a0v_112`、四新表 `0/0/0/0`；`bundle_installation` 1、`asset_bundle_version` 4、`asset_bundle_artifact` 209、`aip_skill_template_revision` 37 的逐行摘要与 BG-00x 恢复时相同。当前权威库 `aos_current_preview_20260927` 回读仍 `a0v_111`。

## 方案一致性与剩余门

四表分别表达独立 Eval issuer、双 purpose 身份、追加式撤销、逐 case 签名 Receipt；tenant 复合 FK、双唯一键、append-only 和只读运行角色与方案一致。迁移不插入根、身份或 Receipt，不接生产 Runner；当前 API 进程未以高于数据库的迁移头重启。表结构不会自动证明 Owner/批准来源、公钥和签名真实性、撤销竞争的同事务消费或真实 G2 内容/S3。后继需正式签发来源与同事务验证/持久写入；切换当前库另开 BG-00z，先新一致备份和完整克隆演练、零执行窗口，再以 `a0v_112` 重启并回读。缺条件时当前实例保持禁入。
