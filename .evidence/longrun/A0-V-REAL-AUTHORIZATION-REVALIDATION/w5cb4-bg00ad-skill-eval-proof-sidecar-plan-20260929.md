# W5CB4 BG-00ad｜Skill Eval 双 Receipt 与 Report 关联 sidecar 隔离方案

## 上位与范围

228 G2.2/231 要求真实 G2 内容/首链；BG-00ac 证明普通 Eval runner 的多次 commit 和 Report case 无 Receipt 回链，故生产 Skill guard 继续。BG-00y/z/ab 提供默认空签发/identity/双 Receipt 表和只读验证器。当前签名 G2 包仍占位、当前 `a0v_113` 四表空。本波只做**test-only clone 的增量 schema 与隔离拒绝测试**，不在当前库迁移、不开 Host、不解除 Skill guard。后继独立波再实现同事务写入和消费。

## 文件级设计

1. 新增 `services/aos-api/alembic/versions/a0v_114_skill_eval_case_proof_sidecar.py`。一张 append-only、租户 RLS/FORCE 的 `aip_eval_case_execution_proof`，以 `(org_id,project_id,run_id,case_id)` 主键；精确固定 Report id/revision、Target/Judge Receipt id 与各自 claim hash、verified_at。给现有 Report 新增包含 run 的唯一索引，给 Receipt 新增包含 run/case/purpose/id/**claim hash** 的唯一索引，以 sidecar 复合外键保证同 tenant/run/case、目的为 target/judge 且 claim hash 完全一致，避免 Receipt/Report 错配或 sidecar 自报 hash。无全局 default ACL 更改；显式 `REVOKE ALL FROM PUBLIC,aos_runtime`，仅授 `SELECT,INSERT` 给 runtime；禁止 UPDATE/DELETE/TRUNCATE。
2. 新增 `services/aos-api/tests/aip/test_aip_skill_eval_case_proof_schema.py`：只接受全新 test-only clone URL；先 RED，验证迁移前表不存在；升级后核 FK/唯一性、RLS/FORCE、ACL、append-only、空表。正向 test-only row 必须先有匹配 Run/Report/两 Receipt；负向跨 run/case/purpose、重复 case 和旧 Receipt 都拒绝。测试插入限定 `org-org/dev-project` 回滚事务，`dev-org` 仅 RLS canary。
3. 从 `aos_bg00z_acl_20260929@a0v_113` 在 test-only PG 做 ACL 保真新库 `aos_bg00ad_schema_20260929`，源库仍保留。先用迁移/测试 RED 再最小代码，专测新 clone；若 schema 评审发现新约束，另建全新 clone 复跑最终迁移，不删历史库。累计复跑相邻 Eval 双签/reader 测试。若升级当前库，必须另开备份+全库恢复演练+零执行窗口波。

本波 sidecar 只是可表达并约束“同 case 的持久证据关系”；数据库 FK 不证明签名或 Report JSON case 内容，后继同事务服务须调用 BG-00ab reader 并在 Report/Gate 端核每个 case 一一对应。不得把 test-only row、正式空表或页面 200 当业务首链。
