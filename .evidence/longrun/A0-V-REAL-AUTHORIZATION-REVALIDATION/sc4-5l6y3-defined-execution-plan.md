# SC4-5L6Y3 exact配置下的组执行与恢复

## 产品目标与分波

让Y2用户保存并启用的配置真正进入Y1原子领取，再由原Ingress和Completion完成一致快照。仅领取成功不算业务闭环。Y3a先补exact配置绑定领取及不可变证据；Y3b接运行/恢复（input存在只恢复，source claim存在且input不存在标unknown不重读）；Y4接cron/lifespan与停止卸载；Y5/Y6真实配置、克隆升级后主库观察。原J失败Run保持原事实，Z正式恢复合同另办。

## Y3a方案

在既有claim Owner新增可选definition_ref。未传仍走原v1合同且拒绝任何归组成员；传入严格SnapshotScheduleDefinitionRevision exact ref，读取当前定义并按安装→定义head→原current controls→按ID排序schedule锁顺序执行。当前state必须enabled、ref完全一致、执行actor为配置executor、成员与配置逐项一致且全部属于同definition当前revision。配置管理人不必等于执行人；执行依赖原源控制权限，不能将管理员配置身份替代executor。

现有调度claim的request/record v1不可改动或重哈希。新带定义请求使用aos.snapshot-schedule-request/v2与aos.snapshot-schedule-claim/v2，仅新增definitionRef，其余Y1字段和运行回执规则相同。新增a0v_064替换原062检查函数，兼容严格v1，同时对v2验证definitionRef的kind/id/revision/hash与原不可变enabled配置Revision一致、成员/actor/当前head精确一致。旧行不更新；不可变/RLS/原Run与binding FK保持。

同group必须原request完全一致才回放；当前配置已停用或改版后不能借旧回执获得新读取权。只读read仍可读取历史，实际prepare使用时再复验current。首次领取仅服务器当前分钟；原运行幂等、十二源原子性、零source claim维持Y1。数据库约束不是远程读取许可。

## 修改目录与退出条件

修改 services/aos-api/aos_api/pipeline_snapshot_schedule_claim.py；新增 services/aos-api/alembic/versions/a0v_064_defined_snapshot_schedule_claim.py、services/aos-api/tests/extension_runtime/test_defined_snapshot_schedule_claim_pg.py。必要测试fixture调整必须显式记录，不降低生产权限。

先负例：当前enabled exact配置可领取且原回执包含定义；disabled/stale/wrong actor/成员漂移拒绝；停用后回放不能执行；v1未归组兼容；DB直接缺失/错误definition关联拒绝；同key重放零新增，负租户零记录。生产主库仍061，本波只隔离迁移。不push，230L0挂起。

实现细化：原fixture先设ALL IMMEDIATE暴露组header先于12成员插入时立即约束失败；Owner事务内显式延迟两个组完整性约束，完成时主动IMMEDIATE验证，不把半组交给外层。064同时禁止新v1领取关联已有归组成员；历史v1不更新。新增直接SQL重算双哈希后的错误definition关联/旧版绕过负例，避免只测哈希不符。

增加 services/aos-api/tests/extension_runtime/test_defined_snapshot_schedule_recovery_pg.py，实际提交后新Owner/新连接回执恢复，双连接停用↔领取争锁需pg_blocking_pids确证。停用先提交则零Run；领取先提交保留原12Run但停用后无source claim；读取许可仍交Y3b重验。

## Y3a结果（2026-09-16）

新增064兼容v1/v2完整性验证，原claim Owner接受exact definitionRef且绑定当前enabled head、executor及完整成员；安装→head→current controls→schedule顺序，回执v2持久化确切引用，历史v1不更新。只读read支持两版，停用后可看历史但claim不能重放为执行许可。没有远程读或SourceClaim。

Red为Owner不接受definition_ref；首次实现遇外层ALL IMMEDIATE导致header先插检查，修复为本事务延迟并在返回前IMMEDIATE（含重放路径）。新SQL防旧版绕过分支首次使用m别名与PL/pgSQL record变量冲突，隔离PG报错后改唯一member_row别名，未影响主库。

25项新领取/旧v1/恢复/围栏回归通过23.21秒（/tmp/aos-defined-claim-regression-v2.log）；加入实际新连接/new Owner提交恢复、双向停用争锁与配置回归后最终45 passed/44.99秒（/tmp/aos-defined-claim-final.log）。直接SQL重算两种hash后的错误ref kind/hash和v1归组绕过均由数据库拒绝，不只是应用拒绝。双向锁等待通过pg_blocking_pids确证；停用先胜零Run，领取先胜保留12Run且零SourceClaim。git diff --check通过。

Y3a仅运行领取完成；Y3b须将current定义守卫带入每次原SourceClaim读取/Store恢复事务，不能只在外层调度开始检查，否则停用后续副作用有缺口。下一波先补此守卫再接runtime的原Ingress→Completion。Y4生命周期/cron、Y5真实十二源、Y6克隆升级观察、Z原失败Run和经营闭环仍未完成。主库仍061、host未重载；不push，230L0挂起。
