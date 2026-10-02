# 2026-10-02 当前118→135 最新代码独立恢复演练

08:54 CST 基线 `aos-platform/m1 4c26d350`，当前权威卷 `colima-aos-extension/aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927@a0v_118` 只读；代码新增单目的 `a0v_135` 修正 `extension_schema_installation` 运行角色写 ACL。此前 04:54 的当日一致备份与完整恢复到 `a0v_134` 已 GREEN，但不能证明新头135。

复用已验证的 118→134 `rehearse.py` 骨架，复制到仓库外新 0700 目录 `aos-recovery/.aos-current-backup-20261002-daily135-preflight`，精确替换新目标库名为 `aos_daily_preflight_20261002_135`、唯一 head 与升级范围 119…135；目标不存在才执行，源连接仍 `REPEATABLE READ READ ONLY`，备份0600且写入前独立检查源容器/卷、目标独立物理卷、m1 HEAD 和无其他 client backend。脚本旧逻辑读源/克隆全表计数、17 控制表摘要、元数据旧行摘要；新增迁后 `aos_runtime` 对 `extension_schema_installation` 仅 SELECT 且 INSERT=false 的 SQL 回读，不把 ACL 修复扩大到其他表。失败保留现场与错误，绝不覆盖已有备份/库或写当前源。

成功只证明新鲜备份可恢复并在独立克隆从118逐步升级135、ACL与旧数据保持；不是当前实例迁移、PG/API/Web完整重启或业务首链。当前切换仍需独立零执行窗口、新停机一致备份、当前签名启动器与正式身份、源/克隆全链对账及复验；不启 Host/worker/Provider。
