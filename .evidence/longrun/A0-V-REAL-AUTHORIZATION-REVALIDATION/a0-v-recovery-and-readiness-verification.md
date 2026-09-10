# A0-V 恢复基线与真实就绪复验记录

## 1. 结论

本次 A0-V 只能判定为 `A0_V_BLOCKED_WITH_ACTIONABLE_GAPS`，不能据此进入 A1。复验使用的是 2026-08-05 的本机历史备份恢复点及其迁移到当前 Alembic head 的隔离克隆；它证明当前迁移链和只读接口仍存在可复现缺口，但不代表 2026-09-10 原数据库已被完整恢复，也不代表 `org-org/dev-project` 当前真实配置已恢复。

确定性采集器共记录 17 个阻断项和 1 个待验证项。缺失 Bearer 返回 401、非法分页参数返回 400；没有调用 Provider、执行付费能力、写入经营系统或触发外部发布。

## 2. Docker 数据事故与止损

系统重启后同时存在 Docker Desktop 与 `colima-aos-extension` 两个 Docker context。启动 Docker Desktop 后，当前 context 被自动切换为 `desktop-linux`；随后一条原计划清理 Colima 空容器的未限定 context 命令，误删除了 Docker Desktop 中同名 `aos-dev-pg` 容器及其 named volume。该操作错误由本轮执行造成。

发现后立即停止 Docker Desktop，冻结原始 `Docker.raw`，并创建只读恢复副本和工作副本。ext4 journal 中找到了被删卷目录名及旧 inode，但 inode 已被复用、extent 信息不可用；`extundelete` 未恢复目标文件，`ext4magic` 在该镜像上异常退出。本机没有可用 APFS 快照、Time Machine 目的地或 Docker volume 备份计划，因此不能声称原卷已恢复。

保留的恢复介质位于仓库外：

- `/Users/ddt/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw.aos-recovery-20260910`
- `/Users/ddt/work/projects/ai_agent/Docker.raw.aos-recovery-20260910`
- `/Users/ddt/work/projects/ai_agent/Docker.raw.aos-recovery-work-20260910`
- `/Users/ddt/work/projects/ai_agent/aos-docker-ext4-journal-20260910-v1.bin`

在恢复结论最终确认前不得删除这些介质。后续所有 Docker 变更命令必须显式指定 `--context`，并在删除容器或卷前校验 context、对象 label 和预期卷名。

## 3. 可用历史备份与隔离恢复点

本机 `/var/tmp` 中找到 21 份 PostgreSQL custom-format dump。用于本次只读诊断的最新备份已复制到仓库外恢复目录：

| 备份 | 时间/用途 | 字节数 | SHA-256 |
|---|---|---:|---|
| `/Users/ddt/work/projects/ai_agent/.aos-recovery-20260910/backups/aos-meta-20260805T050248.dump` | 2026-08-05 05:02:48 +08；最新可用历史恢复点 | 1,944,971 | `ebdcbe71e0b020465873a7f29fff96e031310e336ee449f22ed53479aa31b3f4` |
| `/Users/ddt/work/projects/ai_agent/.aos-recovery-20260910/backups/aos-meta-20260804T200340.dump` | 2026-08-04；TI-1 E3 文档化备份 | 842,817 | `79f2ac6b824167f3cbb9a334eee2dd85aa485794bab8b4688ce72f4f1d50fb64` |

最新历史恢复点的 `alembic_version` 为 `228ti5a3lineage`，包含 101 张 public 表、共 9,695 行、55 张非空表。按租户聚合，`dev-org/dev-project` 有 9,221 行，`org-org/dev-project` 仅有 2 行，因此该恢复点只适合迁移兼容与失败关闭诊断，不能作为当前正向租户的业务事实。

恢复容器固定为 `aos-a0v-recovery-pg`，映射本机 18435，使用独立卷 `aos-a0v-recovery-pg-data`。原样历史库保留为 `aos_meta`；诊断克隆 `aos_meta_head` 从 `228ti5a3lineage` 完整升级到 `ar2_018`，升级日志位于 `/Users/ddt/work/projects/ai_agent/.aos-recovery-20260910/logs/alembic-upgrade-head.log`，SHA-256 为 `052f5998c3fe63b58d79f8f1e29a78bd50dfab3a89bb2d47d2335749afaf924d`。

## 4. 诊断运行护栏

AOS API 只绑定 `127.0.0.1:18181` 并连接隔离恢复库 `aos_meta_head`。运行期间固定：

- migration mode disabled；
- QYH Cron disabled；
- Logic automation disabled；
- Provider health maintenance disabled；
- extension runtime host inactive；
- 采集器仅允许 loopback HTTP 和 GET；
- 响应体限制为 2 MiB，敏感键、Bearer 和 DSN 密码递归脱敏。

## 5. 初始复验结果

提交 `2b82e884` 固定的初始 `a0-v-readiness-result.json` 于 `2026-09-10T10:56:47.234368+00:00` 采集，结果为 `A0_V_BLOCKED_WITH_ACTIONABLE_GAPS`：

- 17 个阻断项：canonical SourceReadiness 500、Workshop 未安装、AIP 电商目录无效、必要安装/生产契约/责任计划/阶段模板/TaskBrief 为空，以及模型 Provider/Model/Route/Health/Chain/Budget 为空；
- 1 个待验证项：正向租户没有可用于 exact-id 负向租户反查的资源，因此跨租户资源隔离不能在本恢复点上宣称通过；
- 两个负向协议检查通过：缺失 Bearer 为 401，`limit=101` 为 400。

SourceReadiness 的 500 已定位为 `meta_schedule_run` 不存在。该表只在 legacy `init_schema()` 的 `SCHEMA_SQL` 中创建，未进入从历史修订升级到当前 head 的 Alembic 迁移链；canonical SourceReadiness 和多个运行视图会读取它。这是独立的 managed-schema 缺口，须按单独方案修复并在隔离数据库验证。

当前工作树中的同名结果文件已在修复提交 `48c7cc28` 后重新采集；修复后的 16 项阻断及验证结论见 `a0-v-managed-schema-readiness-repair-verification.md`。

## 6. 当前边界

本记录证明的是：历史 managed database 经正式迁移升级到当前 head 后，核心只读就绪接口仍会因迁移清册缺表而失败。它不证明原 Docker 卷已恢复，不证明当前真实正向租户资料完整，也不授予真实 Provider、外部副作用、生产迁移或 230 L0 权限。
