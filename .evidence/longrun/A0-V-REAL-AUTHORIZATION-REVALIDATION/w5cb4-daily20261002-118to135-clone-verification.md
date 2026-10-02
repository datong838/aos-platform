# 2026-10-02 当前库118→135 独立全库恢复演练

基线 `aos-platform/m1 4c26d350` / `AOS-001113`。方案 `w5cb4-daily20261002-118to135-clone-plan.md`。源 `colima-aos-extension/aos-a0v-recovery-pg` 挂当前权威卷 `aos-a0v-recovery-pg-data`，库 `aos_current_preview_20260927@a0v_118`；目标 `colima-aos-a0v-test-only/aos-bg00dl-isolated-pg` 为独立物理卷、新库 `aos_daily_preflight_20261002_135`。私有现场 `aos-recovery/.aos-current-backup-20261002-daily135-preflight`，0700/0600。

复用先前已验证的只读源备份/恢复脚本，仅替换新目标库、唯一 Alembic head 135 与17步范围，并新增迁后 ACL 回读；脚本 SHA256 `9595910e3b691da02e3df0099ed7b4423a55c44efbb3f949caced461a35f1342`，py_compile 退出0。执行前断言新库不存在、目标卷独立、目标集群没有其他 client backend、m1、源118。源事务 `REPEATABLE READ READ ONLY` 导出 snapshot，`pg_dump -Fc --snapshot` 生成 3,961,457 字节新备份，SHA256 `301e4e1ee9d3aa3deae1b31d531c3ee5ad833820437a132d1518a2c95400e3e8`，TOC 5621 行；globals 无密码副本 SHA256 `8a435761df748d194633228427185a691b5d1cd416e8815d2535ff69f1cc318a`。备份与脚本均留仓外，没有删除旧现场。

`pg_restore --exit-on-error` 退出0；恢复时源/目标原580张 public 表行数、17控制表摘要与两类元数据逐ID摘要一致。目标按原 Alembic 每步独立事务迁 `a0v_119`…`a0v_135`，17个 `done-a0v_*.json`；最终目标 `a0v_135`、新增12表，旧表行数和控制摘要不变，旧元数据行保持，新固定元数据按既有迁移增加。`has_table_privilege('aos_runtime','public.extension_schema_installation','SELECT'/'INSERT')` 在目标为 `t|f`；源只读回读仍 `a0v_118`。`verified.json` 为 `FRESH_RESTORE_AND_118_TO_135_CLONE_GREEN`、`sourceUnchanged=true`、`sourceWrites=0`、`providerCalls=0`，脚本退出0。独立备份 SHA256 与记录一致。

此结果证明当日新鲜一致备份可恢复且当前代码头135在隔离克隆可迁，不代表当前实例迁移、PG/API/Web最新栈重启或自然经营首链。正式当前切换仍需独立零执行窗口、第二份停机一致备份、签名启动器/角色/数据全链复核及迁后八工作台复验；Host/worker/Provider 保持关闭。旧 9月30日 API/Web 当前仍在运行。
