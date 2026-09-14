## SC4-5l6d4c2 完整十二源接线验证与栈深修复（2026-09-15）

Rules：m1串行、先方案、原Owner和单写者锁不削弱、不push、230 L0挂起。完整12个规范管线使用原selection/control/claim/input/Store/object投影/Dataset/Query/Quality/Business Evidence及原Binding行，安装字节/签名许可、源样本、分析起点和Provider依赖为明确named fixtures。不是主环境或真实Provider验收。

首轮完整12业务Evidence通过；就绪消费出现RecursionError（/tmp/sc4-d4c2-full.log，1passed+1failed/69.98s）。原因：Business内部重新进入Source与Quality来源栈，12成员控制回调重复嵌套；两源样本未暴露。修改ecommerce_analysis_snapshot_business_evidence.py新增内部_run_current_context，在原_during当前守卫内共享已核验Source/snapshot/CurrentSnapshotQuality，旧公开接口/保存字节不变；readiness_context移除重复来源栈，保留所有原前后检查/投影/Binding/原QualityStore核验，不提高递归上限。

新文件test_analysis_snapshot_readiness_twelve_pg.py：完整12当前就绪消费与input/run/policy/binding/release/deferred变更回滚共8passed/263.89s（/tmp/sc4-d4c2-fixed.log）；新增control中途变化和旧Business撤销回归串行2passed/38.20s（/tmp/sc4-d4c2-serial.log）。原Business/Brief/Bundle回归首轮26passed+1setup error/144.07s（/tmp/sc4-d4c2-regression.log）：两组测试虽独立schema仍共享同租户投影advisory锁，同时运行触发正确PROJECTION_BUSY拒绝；该唯一setup error已串行复验通过。后续同租户PG执行测试串行，不改锁。最终覆盖9个完整12测试+27个原回归，共36项通过（分三次结果，不声称一次36）。源样本读取始终1次，原12 Dataset回执存在；失败消费探针写入均回滚。

AR2 ar2-7：1946/190/93所有错误列表为空（/tmp/sc4-d4c2-final-closure.log）。7项已有框架警告。主schema/deployment/install/Run/Task/Provider/商城数据无变化，未访问真实源或发外部消息。原20260913进度+42行与Playwright依赖修改保留。

下一波l6d6原SourceReadinessReceiptStore：原评估结果保存、精确回读及当前再验；绑定当前Requirement与完整来源，历史回执不得单独放行。之后仍l6e原状态恢复、l6f Outbox、l6g主升级/真实首链/八场景/连续观察及发布判断。整体任务未完成，自动进入下一波。
