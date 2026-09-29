# W5CB4 BG-00ad｜Skill Eval proof sidecar 隔离迁移验证

## 事实与执行

- 当前代码迁移头升为唯一 `a0v_114`，新增 `aip_eval_case_execution_proof`：tenant/run/case 主键、Report 精确 FK、Target/Judge Receipt 复合 FK 含 purpose/id/**claim hash**、RLS/FORCE、append-only、运行角色 `SELECT,INSERT` 且无 UPDATE/DELETE。未更改普通 Eval runner 或 Skill 禁入 guard。
- test-only `aos_bg00z_acl_20260929@a0v_113` 用 `pg_dump -Fc` 生成隔离快照，TOC 5594；`pg_restore --no-owner --single-transaction --exit-on-error` 保留 ACL 恢复新库 `aos_bg00ad_schema_20260929`，退出 0。升级 `a0v_113→a0v_114` 退出 0。
- 结构测试在升级前 RED：`1 failed`（预期 `a0v_114`，实为 `a0v_113`）；初版升级后 `2 passed`。复审发现初版 FK 只绑定 Receipt ID，sidecar 可自报错误 claim hash；新增负例后 `1 passed, 1 failed`，精确失败为 `DID NOT RAISE ForeignKeyViolation`。
- 修复迁移脚本，将 `claim_hash` 纳入 Receipt 唯一索引及 Target/Judge 两条复合 FK。保留初版历史库不删，从同一 a0v113 快照 ACL 保真恢复新库 `aos_bg00ad_schema_v2_20260929`，用最终脚本升级 a0v114 退出 0。专项+相邻签名/reader/ACL `25 passed, 2 skipped`，退出 0；错 run/case/purpose/hash、重复 case、UPDATE、dev-org RLS canary 均拒绝。两套 test-only clone 的 Eval authority 表测试后为 0，v2 sidecar 也为 0。`compileall -q`、`git diff --check` 退出 0。

## 界限与下波

这张表只约束持久关联，不证明签名、Report JSON 每 case 完整性或 Gate 可消费；同事务写入/读回服务尚未实现，正式 G2 issuer/Owner/内容与真实 S3 均无。当前权威库仍 `aos_current_preview_20260927@a0v_113`，API/Web 正在运行旧启动基线；代码头已到 a0v114，**不可直接以新代码重启**。下一波 BG-00ae 先独立可恢复当前卷切换：最新一致备份、全新 ACL 保真完整克隆和迁移/回读、零执行窗口、当前迁移、API/Web 重新启动与版本/安装/页面复核。Host/worker/Provider 继续禁入，旧 12 Run/商城源/dev-org 写入/230 L0 不触碰。随后 BG-00af 才实现 sidecar 与 Report 同事务消费。
