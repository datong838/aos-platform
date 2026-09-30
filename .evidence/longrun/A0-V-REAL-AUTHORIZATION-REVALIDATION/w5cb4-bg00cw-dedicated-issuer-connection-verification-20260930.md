# W5CB4 BG00cw｜专用 issuer DB 连接验证

- 基线：m1 `345878fc`、AOS-000952；任务 Receipt `W5CB4-BG00CW-20260930`；文件级方案 `w5cb4-bg00cw-dedicated-issuer-connection-plan-20260930.md`。
- RED：新 connection 测试缺模块 `2 failed/1 skipped`；隔离克隆的 commit 后角色/tenant 测试明确 RED：`current_user` 掉回 `aos_network_approval_issuer`、tenant GUC 为空。最小 wrapper 在 commit/rollback 后重新 `apply_transaction_scope` 并复核身份；该项转 GREEN。
- GREEN/邻接：带显式 BG00cm/BG00cq test-only clone 运行 connection/ipc/service/attempt/auth/reconcile/contracts/network producer 八文件，退出0，`63 passed, 2 skipped`；compileall 和 `git diff --check` 退出0。
- 真实隔离克隆证据：127.0.0.1:18437、`aos_current_preview_20260927`、私有0600 passfile；`session_user=aos_network_approval_issuer`、`current_user=aos_runtime`、`org-org/dev-project`，只读 Event0/UNRESOLVED。测试将 `AOS_DATABASE_URL` 指向错误 owner DSN，连接仍使用显式 issuer 参数。决定连接的 commit/rollback 后角色与 tenant 精确回读，未写 Event。
- 方案/代码复审：只接受 loopback、精确库名和本 UID 私有凭据；拒绝 PGPASSWORD/PGSERVICE 等环境回退；连接前后检查 issuer LOGIN 非 super/BYPASSRLS/INHERIT/owner member、事务角色和租户。决策连接使用 SERIALIZABLE，查询只读 REPEATABLE READ。`AipActionStore.decide` 提交后再读 bundle 的角色掉落风险通过 wrapper 处理。
- 未完成：`scripts/a0v_network_issuer_server.py` 未建立。当前 issuer 不能读 `pg_hba_file_rules`（实际 `InsufficientPrivilege`），现网无独立 OS issuer 用户、正式外部 IdP 或当前第二 checker；不能把不受信的 HBA JSON/flag 当启动许可。正式进程与 HBA 证明源须下一独立波设计；当前库只读，API/Host/worker/Provider 不切换，首链 pending。
