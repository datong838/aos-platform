# 2026-10-02 当前库118→134 全库恢复与隔离迁移演练

基线 `m1 13fd55aa` / AOS-001093。依据 `w5cb4-daily20261002-118to134-clone-plan.md` 执行；私有现场 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261002-daily-preflight`，目录0700，备份/脚本/证据文件0600。源 `colima-aos-extension/aos-a0v-recovery-pg` 挂权威卷 `aos-a0v-recovery-pg-data`，库 `aos_current_preview_20260927@a0v_118`；目标 `colima-aos-a0v-test-only/aos-bg00dl-isolated-pg` 的新库 `aos_daily_preflight_20261002`，两者物理卷不同。

| 门 | 可复核命令与结果 |
|---|---|
| 前检 | `colima list`、`docker inspect`、源/目标 `psql SELECT version_num`：源118、目标容器在独立卷，目标集群其他 client backend 0；`ScriptDirectory.get_heads()` 唯一134，118→134 连续16步。 |
| 文件级脚本 | 复用昨日已验证 `rehearse.py`，仅改唯一目标库、head、修订范围和133新增的两类固定元数据计数；`python3 -m py_compile` exit0，脚本 SHA256 `d92ebd132fdd1191b3707fe954fda6eeccff1480f4faaa0c60830dd740f075c3`。初次复制脚本因重复替换锚点未产文件，回读空目录后修正；未触数据库。 |
| 新一致备份 | 脚本源事务 `REPEATABLE READ READ ONLY`，导出 snapshot 并 `pg_dump -Fc --snapshot`；`current.dump` 3,961,457 bytes，SHA256 `3b2a4af10e2e32f79bc049da447990e642dd3a866abc54af3266c13b25fe6275`，TOC 5621 行；`globals-no-password.sql` 同为0600。脚本执行退出0。 |
| 全库恢复 | 新库从 template0 建立并撤销 PUBLIC CONNECT；`pg_restore --exit-on-error` exit0；源/克隆在118时原580张 public 表行数、17张控制表全行摘要、两类元数据逐ID摘要完全一致。 |
| 克隆升级 | 原 Alembic 在目标库逐事务以 `aos_app` 表 owner 迁 `a0v_119`…`a0v_134`，16个 `done-a0v_*.json` 且每步 readback；最终克隆134，新增12表，旧表行数不变（`meta_object_type/meta_action_type` 各按固定迁移新增4行）；旧元数据逐ID摘要、其余固定控制表摘要保持。结果 `FRESH_RESTORE_AND_118_TO_134_CLONE_GREEN`。 |
| 保护回读 | 克隆 `aip_model_eval_request` 与两个 Eval 预算表均 `RLS=true/FORCE=true`，六个 append-only/truncate guard 触发器 `O`；精确9个预算/审批/网络签发消费角色 `count=9, privileged_or_login=0`。脚本源库前后全部计数/摘要相等，`sourceWrites=0,providerCalls=0`；独立源 SQL 仍118、克隆 SQL134。 |

脚本是仓库外一次性现场文件，不提交凭据或业务数据。`backup.json`、`source.json`、`restored.json`、逐迁移 intent/done 与 `verified.json` 留在私有目录；任何后续使用须重读 SHA256 和目标身份。**本波只证明当前118可恢复且现有m1代码可在隔离克隆升级134，尚未迁移当前库、未重启PG/API/Web，也没有自然业务首链。** 当前切换另需停止 API/Web 的零执行窗口、第二份停机一致备份、源/克隆全链对账及当前签名启动器版本合同复审。Host/worker/Provider 继续关闭。
