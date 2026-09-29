# W5CB4 BG-00bn｜系统策略动作数据库写门隔离验证

方案：`w5cb4-bg00bn-system-action-migration-plan-20260929.md`（编码前修订为仅建保留门，不提前插入不可用元数据）。本波当前权威库始终只读，Host/worker/Provider 不启用。

1. RED：`test_aip_policy_action_proposal_gate.py` 初次因 pytest 保留参数名 `request` 集合退出2，修正测试本身；正式 RED 3 failed，通用 create_proposal/create_draft/revise_draft 会先触发 schema seed。GREEN 在生产者入口前拒绝五系统 ID，`3 passed`。此拒绝不产生批准或执行权。
2. 当前源 `aos_current_preview_20260927` 在命名卷 `aos-a0v-recovery-pg-data`。`pg_dump -Fc -U aos_app` 以一致快照生成 `/Users/ddt/work/projects/ai_agent/.aos-current-backup-20260929-bg00bn-fB5c6i/aos_current_preview_20260927_a0v114.dump`，3,950,274 bytes、0600，SHA256 `a77c6092820306b46a8b2477fa78bc21e71f352b43bb09f37541dd5ec2d4703d`；`pg_restore -l` 退出0、TOC 5607 行。首次备份命令在完成 dump 后因 zsh 保留变量 `status` 退出1；随后独立 stat/SHA/TOC 均退出0，未重做或覆盖该档。
3. 新建并保留 test-only `aos_bg00bn_testonly_20260929`，`pg_restore --exit-on-error` 退出0。恢复前后只读回读源/克隆 `a0v_114`、580 public 表、1 安装、元数据两表0；未读取商城源行。程序化 Alembic 对精确 clone 从 `a0v_114` 升 `a0v_115` 退出0。随后源仍 `a0v_114`，clone `a0v_115`、580表/1安装/ActionType0/保留触发器1。
4. 在 test-only clone 的事务内以 `aos_runtime` 检查五固定 ID INSERT 均 SQLSTATE `42501`；固定 ID UPDATE/DELETE 均 `42501`；普通 ID INSERT 成功1行，整个测试事务 rollback 后 ActionType 仍0。数据库触发器保护正常运行角色写路径，表 Owner `aos_app` 仍可绕过，是已知需要更独立数据库身份的边界。
5. `pytest tests/aip/test_aip_policy_action_proposal_gate.py tests/aip/test_aip_policy_action_type_reservation.py tests/aip/test_aip3_action_control.py tests/test_actions.py tests/test_action_plugins_99.py -q --tb=short --disable-warnings` 退出0，25 passed / 7 warnings；`compileall -q`、`git diff --check` 退出0。方案一致性复审：migration 只增函数/触发器；未插入对象/动作行、未接批准/Store active、未改当前库。浏览器不适用本波 DB/服务端禁入切片。

**下一波 BG-00bo**：当前代码迁移头已为 `a0v_115`，真实库为 `a0v_114`。先验证当下备份仍与当前源一致或重取新的独立一致备份，SHA/TOC、另一个全链克隆恢复/升级/角色负例及安装状态回读；固定零执行窗口、Host/worker/Provider 关闭后才可迁移当前卷和按最新 m1 完整重启 PG/API/Web。不能用本波 test-only clone或页面200冒充当前实例。后续正式元数据 Producer/预览/审批原子消费与首链仍待做，五类 active Store 门不变。
