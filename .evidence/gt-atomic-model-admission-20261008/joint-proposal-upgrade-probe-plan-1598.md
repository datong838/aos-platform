# 联合原调用 proposal 升级原生 RED 调查

已登记 newJudge Source 联合桥的前置顺序审计。使用原159隔离库、原批准 Model 两申请、原新 Judge 批准申请及原预算方法。不改生产代码/正式数据库，不新建库，不重放旧Run，无Provider。新UUID原批准fixture由原测试创建。
精确文件：本目录 joint-proposal-upgrade-native-red-r1.py / probe片段 / proof / log / result。原测试源码hash冻结；collection阶段仅对原 test_exact_signed_rule_new_original_suite 插入并发调查，其他原方法不换实现。
A先走原 _prepare_dual_purpose_bucket_fences；B同原入口进入并真实等待费用fence；A再走原Target hold。独立admin只读观察B实际Lock，双方终止/回滚，读回Target新增hold零且原Judgehold保留。预期合同是都正常回滚；如真实40P01则RED证明该组合需先修入口锁升级，不证明已经部署的Source入口或生产死锁。
所有异常保留，join确保无活跃线程；无结果或超时先对账原handle，不重发未知效果。原 Source 原事实桥实现需先消除该前置风险，不能加自动重试遮掩。

R1实际失败于观察器指定费用query，未产生锁升级结论；双方已正常回滚、handle exit1。R2改为观察所有真实Lock并记录query+blockingPID，以实际阻塞位置决定是否进入Target hold；不得把观察器假设当根因。原生新UUID试验不重放旧审批/Source/未知效果。
