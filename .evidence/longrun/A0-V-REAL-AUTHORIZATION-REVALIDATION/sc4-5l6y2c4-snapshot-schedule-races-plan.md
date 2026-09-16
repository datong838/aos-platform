# SC4-5L6Y2c-4 调度归属竞争专项

承接Y2配置与产品入口，验证产品目标中的单写者与可恢复边界。m1串行、不push、230 L0挂起；主库061不迁移、不重载、不执行真实源。

## 方案与边界

在完整063一次性隔离库，复用正式安装配置权限、runtime角色、真实Owner与原单路schedule_claim_connection。源资产仍为具名夹具，不作为真实商城接入。两条独立数据库连接必须用pg_blocking_pids观察确实发生锁等待，不能把串行调用或sleep当竞争证据。阻塞检测上限5秒，语句超时10秒，线程退出有界。

1. 组配置已写但未提交持有schedule锁，单路领取阻塞；组提交后单路必须看到当前成员归属并拒绝，零新Run。
2. 单路先持有schedule锁并插入原Run，组配置阻塞；单路提交后组必须因running或未确认停止而拒绝，配置revision/head/member全部回滚，原Run和单路enabled不变。
3. 新连接回读与历史回执沿已有service实测复用。跨generation最新绑定负例须通过原Owner产生真实后继，不能编辑不可变行；如需要独立生命周期夹具，在后续子波记录未完成，不扩大结论。

新增 services/aos-api/tests/extension_runtime/test_pipeline_snapshot_schedule_races_pg.py。仅在专项暴露生产缺陷时补修对应Owner并先更新本方案。验证日志、退出条件、限制写回本文件，然后提交并接Y3 exact definition组执行与恢复；跨代次专项若未完成必须保留清单。

## 跨代次专项范围细化

补充隔离查询回归：第二代runtime行沿现有fixture明示构造（disabled/fenced），源选项与runtime control、schedule binding后继均由原Owner追加，绝不改旧不可变行。该项仅证明“先取每schedule最新，再过滤代次”不会回落旧绑定，不能作为真实卸载重装生命周期验收。真实生命周期产生第二代后端到端验证仍留Y4/Y6。

## 结果

新增真实双连接竞争3例：pg_blocking_pids确证等待；组先提交拒绝single，single先提交running/failed且未确认停止则组配置全回滚。原runtime角色/当前权限/Owner锁逻辑保留，仅替换连接工厂到一次性数据库。独立3 passed/14.29秒（/tmp/aos-group-races-first.log）。跨代次查询回归1 passed/6.74秒（/tmp/aos-group-generation.log），第二runtime为明确disabled/fenced夹具，selection/control/binding均原Owner追加；原绑定history保留2条且零Run。不是生命周期实装证据。

最终competition+service+definition+fence回归40 passed/84.67秒（/tmp/aos-group-races-final.log），git diff --check通过。未发现需生产修复问题，无主库/host/真实源修改。下一波Y3a按sc4-5l6y3-defined-execution-plan.md实现exact定义v2领取，不改旧v1回执；真实重装生命周期专项继续留Y4/Y6。
