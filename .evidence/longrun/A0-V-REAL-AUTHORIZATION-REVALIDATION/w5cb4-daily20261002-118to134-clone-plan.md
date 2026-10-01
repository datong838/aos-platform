# 2026-10-02 最新 m1 全栈重启前置：当前 118→134 独立恢复演练

2026-10-02 约 05:00 CST。依据用户每日最新版本重启门、231-4/231-6、2026-10-01 BG00GU 全库恢复方案与验证。m1 `13fd55aa`、权威卷 `colima-aos-extension/aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927@a0v_118`；Alembic 唯一 head `a0v_134`，118→134 连续16步。API/Web仍为9月30日进程，Host/worker/Provider关闭。本波只准备安全迁移证据，**不在此脚本中切换当前库或重启服务**。

## 文件和执行方案

1. 复用 2026-10-01 BG00GU 的只读源备份/全库恢复/逐步 Alembic 骨架，复制为仓库外 `aos-recovery/.aos-current-backup-20261002-daily-preflight/rehearse.py`；新建0700目录和0600文件，目标新库 `aos_daily_preflight_20261002`，复用独立 `colima-aos-a0v-test-only/aos-bg00dl-isolated-pg`，不覆盖 BG00GU 库或备份。脚本目标/代码头/卷/版本均精确核验，发现任一目标已存在即拒绝；源连接只能 REPEATABLE READ READ ONLY。
2. 原源事务导出 snapshot → `pg_dump -Fc --snapshot` → fsync、SHA256、`pg_restore --list`，另存无密码 globals；在隔离 PG 创建唯一新库、`REVOKE PUBLIC CONNECT`、`pg_restore --exit-on-error`。源/克隆118所有旧 public 表数量、行数和固定控制面全行摘要精确相同。失败保留现场，只读诊断，不重跑覆盖。
3. 仅克隆上以 `aos_app` 表 owner 逐步迁 119…134，每步实际回读 `alembic_version`。131/132/134只增表/约束/策略，133固定新增 `ModelEvalRequest` ObjectType 与 `aip_request_model_eval` ActionType；旧两元数据表原行摘要保持、计数各在119…130已有+3基础上再+1，其余旧表行数及控制面摘要不变。绝不 stamp、关闭保护或在源库执行 Alembic。
4. 只读核迁后关键 RLS/触发器、签发/消费角色 NOLOGIN、源仍118及安装/Host/绑定摘要不变；生成哈希/版本/行数/角色状态 verification。复审后 m1 精确提交、D-waves/01/06/Prime 更新。此演练不等于今日完整重启；后续单独零执行窗口还需新停机一致备份、当前迁移及 PG/API/Web 最新签名启动与八工作台复验。

## 禁止项和止损

不读取商城源、不动旧12 Run、不手工 run_definition、不碰230 L0、不写 dev-org、不删库卷或备份、不启 Host/worker/Provider、不 push。克隆出现版本/摘要不符即停在隔离目标；不因脚本或迁移失败动当前实例。非脚本业务正向不得在克隆中伪造。
