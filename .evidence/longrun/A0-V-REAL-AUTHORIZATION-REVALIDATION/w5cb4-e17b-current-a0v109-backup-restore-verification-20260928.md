# W5CB4 E17-b｜当前 a0v_109 备份与隔离恢复验证（2026-09-28）

计划：`w5cb4-e17b-current-backup-restore-plan-20260928.md`。此前 00:49 备份恢复后发现为 `a0v_106`，证据见 `w5cb4-e17b-stale-backup-restore-verification-20260928.md`；旧文件/克隆均保留。

## 当前源和新备份

1. 源容器 `aos-extension/aos-a0v-recovery-pg` 为 Up，挂载 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；容器本地 `psql -U aos_app -d aos_current_preview_20260927 -Atc 'SELECT version_num FROM alembic_version'` 返回 `a0v_109`，退出 0。
2. `aos-a0v-recovery-pg` 内 `pg_dump 16.14` 对该库执行 `-Fc`，输出到 VM 的唯一临时文件，退出 0。VM SHA-256 与跨 VM 复制后的宿主文件 SHA-256 同为 `084dae1f5b7e07100fb6ecd9cfbd58161de243ecb2ae39035bc6ae9586666ff0`，文件 3,893,668 字节；临时宿主文件在哈希相同后才重命名。
3. 新备份路径 `/Users/ddt/work/projects/ai_agent/.aos-current-backup-20260928-e17b/aos_current_preview_20260927.dump`；目录 0700、文件 0600。未覆盖旧备份；`pg_restore -l` 可读完整 TOC。

## 隔离恢复与同 SQL 对账

1. `aos-a0v-test-only/aos-a0v-test-pg` 目标 `aos_restore_20260928_e17b_109` 创建前计数 0；`CREATE DATABASE ... TEMPLATE template0` 退出 0。新 dump 以 `pg_restore -U aos_app -d aos_restore_20260928_e17b_109 --no-owner --no-acl --exit-on-error --single-transaction` 完整恢复，退出 0、无错误输出。
2. 同一只读 SQL 对当前库与克隆库逐项比较返回 `same=true`：均 `a0v_109`、public 表 571；唯一安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` 为 approved/revision 3；四个 published bundle 的 id、版本、状态和 content hash 逐项相等；runtime operation/binding/assignment 均为 0；责任计划、运行策略、运行 guard、网络、模型治理、预算六类 head 均为 0。当前八类有效配置候选另用 `read_candidates(TenantScope('org-org','dev-project'))` 回读均 0。
3. `8080/v1/health` 和 `8434/apollo/assets` 在演练前均 200；当前库未执行写入、迁移、业务命令，Host/worker/Provider 未启用，18181 未作为运行入口。

## 判定和边界

**当前 a0v_109 的逻辑 schema/data 备份可完整恢复到隔离库**，修正了 00:49 备份属于旧版本的错误假设。`--no-owner --no-acl` 表示原角色权限原样恢复尚未证明；此演练也不是“克隆全链迁移演练”，不授权对当前实例迁移、切换或启 Host。真实首链仍无 operation/binding/assignment、Owner 和八类配置来源。

下一波：按 E17 主线复核正式三身份及配置生产者。若启动当前实例的迁移/切换，另立波次验证角色/ACL、克隆全链和零执行窗口；保留两份备份与两座隔离库，不在本波清理。
