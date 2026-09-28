# W5CB4 E17-b｜当前备份隔离全库恢复演练计划（2026-09-28）

## 上位边界与现场

- 承接 231-3/231-4、240/241/242 与 E17 清单。当前业务库 `aos_current_preview_20260927`、命名卷 `aos-a0v-recovery-pg-data` 必须保持只读；迁移、切换、Host/worker 和业务命令均不在本演练内。
- 00:49 独立备份 `/Users/ddt/work/projects/ai_agent/.aos-current-backup-20260928-cIitev/aos_current_preview_20260927.dump` 为 3,842,950 字节，SHA-256 `cb2f1b63bee108ade2d20d4fa3b5583471332345111a02229db50ca43816533d`；此前只列过 TOC，未完成全库恢复。此处的“当前”仅为待验证假设，必须以恢复后版本和元数据判定。
- 当前 m1 `f6eeeafb`，代码和权威库同为 `a0v_109`。另一项浏览器插件的并发工作树修改、P2g 测试改动和两份测试现场文件均属他项，本波不触碰。

## 文件级与执行计划

1. **证据文件**：只写本文件及随后同目录 verification；更新外部 AOS 01/06、续接 243 与 D-waves 清单；m1 仅精确暂存本波证据文件。无产品代码修改。
2. **前检**：复核备份 SHA、当前库版本和隔离 `aos-a0v-test-only/aos-a0v-test-pg`；目标库固定 `aos_restore_20260928_e17b`，先确认不存在。不得覆盖或删除任何已有库、卷、备份。
3. **RED/恢复**：先在隔离 PG 只读确认目标库不存在；仅在该 PG 新建目标库；以 `pg_restore --exit-on-error --single-transaction --no-owner --no-acl` 从原 dump 完整恢复 schema/data。失败留现场，不换源、不在当前库重试。
4. **GREEN/对账**：在克隆库 `BEGIN READ ONLY` 读取 `alembic_version`、安装 ID/状态、四个包版本/摘要、运行 operation/binding/assignment 及八类配置候选；与当前权威库同一组只读查询对比。记录 `pg_restore` 退出码和关键计数，不记录业务行或秘密。
5. **限制**：`--no-owner --no-acl` 仅证明逻辑 schema/data 可恢复，不能证明原权限/角色可原样恢复，也不授权当前实例迁移或 Host 启动。若对账不一致，标明备份截面差异并停止正向结论。

## 验收与回滚

- 验收：原备份 SHA 未变；隔离目标由不存在变为存在，恢复退出 0；克隆库为 `a0v_109` 且关键元数据与备份截面一致；当前库/命名卷/8080/8434 不因演练改变，18181 与 Host/worker 继续关闭。
- 回滚：本波不修改当前库；隔离目标库若失败或完成均留存供审计，不在本波执行删除。任何未知结果先只读查询目标库与恢复日志，不重建覆盖。

## 首次恢复后修订（12:06）

隔离 `aos_restore_20260928_e17b` 恢复退出 0，但只读对账显示该备份为 `a0v_106`、566 张 public 表；当前库为 `a0v_109`、571 张表。安装、四包摘要及零 operation/binding/assignment 一致，但此备份不具备当前 `a0v_109` 恢复资格。旧备份和克隆库均保留，不覆盖。

后续独立动作须从当前权威容器对 `aos_current_preview_20260927` 执行只读 `pg_dump -Fc`，保存到新的受限目录；验证 SHA/TOC，另建唯一隔离库恢复，再比较 `a0v_109`、表数及关键元数据。全程不得把当前库作为 restore 目标，不启动 Host/worker；新备份未经克隆验证前不得称“可恢复”。

### 当前版重做的精确目标

- 源容器：`aos-extension/aos-a0v-recovery-pg`，已回读挂载卷 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`，源库版本 `a0v_109`；使用容器本地 `aos_app` 的 `pg_dump -Fc`，不经应用超级账号 DSN，不在命令或环境传密码。
- 新备份目录：`/Users/ddt/work/projects/ai_agent/.aos-current-backup-20260928-e17b/`，模式 0700；先写唯一 `.partial`，dump 退出 0 后重命名为 `.dump`，不覆盖 00:49 旧文件。
- 新克隆：`aos-a0v-test-only/aos-a0v-test-pg` 中 `aos_restore_20260928_e17b_109`，先确认不存在，恢复参数与首次相同。若 dump/restore 失败，保留文件/库并冻结判定。
- 对账使用同一只读 SQL 比较当前与新克隆的迁移版本、public 表数、安装状态、四包精确摘要、operation/binding/assignment 及六类配置 head；八类候选另用正式 `read_candidates` 读当前。不得从恢复成功推导 Host 或业务首链已通过。
