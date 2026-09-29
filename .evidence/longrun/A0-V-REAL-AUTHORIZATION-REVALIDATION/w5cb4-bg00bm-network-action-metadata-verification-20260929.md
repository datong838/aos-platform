# W5CB4 BG-00bm｜NetworkPolicy 元数据当前事实与安全增量

1. 当前 `aos-a0v-recovery-pg` 仍在运行；`docker --context colima-aos-extension exec aos-a0v-recovery-pg psql -U aos_app -d aos_current_preview_20260927 -XAtc 'BEGIN READ ONLY; SELECT version_num FROM alembic_version; ... ROLLBACK;'` 退出0，库头 `a0v_114`，`meta_object_type.id='NetworkPolicyRevision'` 0，`meta_action_type.id='aip_activate_network_policy'` 0；未读商城源。代码当前 Alembic head 同为 `a0v_114`。
2. 同一只读事务查 `information_schema.role_table_grants` 退出0：`aos_runtime` 对 `meta_object_type` 和 `meta_action_type` 均有 SELECT/INSERT/UPDATE/DELETE；`aos_app` 对两表有完整所有者权限。`db.py::connect(scope)` 以当前租户 SET ROLE 到 runtime。BG-00bl API/插件保留门能保护正常路径，却不能独自构成数据库级固定 ID 写权限边界；全局元数据本身没有 tenant 键。
3. 2026-09-29 当前库历史备份目录存在，最近查到的 BG00ae dump 名称显示备份时为 `a0v_113`；未找到可据本次查询直接证明为 `a0v_114` 的独立一致备份。因此不能拿旧 dump 冒充下一迁移的当前可恢复点。本波未做新备份/恢复。
4. `aip_action_store.action_type_snapshot` 按固定 ID 读全局元数据并计算 revisionHash；Proposal/Draft 需此当前快照。通用动作表无显式版本列，必须冻结元数据快照并在批准消费时重验。新系统 ID 的正式行须由受控数据库迁移或专用 Owner 生产；通用编辑/插件 seed 保留禁入。

下一波 BG-00bn 的文件级施工顺序：先设计 `a0v_115` additive migration 的精确系统对象/动作元数据与 DB 级保留写门（至少阻止 `aos_runtime` 对五固定 ID 的 INSERT/UPDATE/DELETE；普通行 ACL 不回归），在 test-only 完整克隆演练升级、重复/漂移拒绝、角色负例、兼容读取与恢复。新迁移一旦进入代码，当前库版本会落后；必须在独立 BG-00bo 零执行窗口中先获取 a0v_114 当下独立一致 dump+SHA/TOC、全链克隆恢复/升级/回读通过，再授权范围内切当前卷并重启最新 API/Web。若无法证明恢复能力，继续阻断最新实例启动，不强迁。迁移本身不创建批准、绑定或 active 策略；正式 Producer/预览/原子消费还需后波。

当前 approved 安装 binding0、八候选0、Host/Owner/自然首链 pending。五类 active Store 禁入保持。
