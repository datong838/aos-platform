# SC2 当前事件启动证据与真实Run兼容验证

基线a3a9239a，m1串行、父Lease覆盖Host/tests。方案analysis-startup-context-design.md已先登记新增文件与运行格式兼容。

## 实现

AnalysisStartupEvidenceService重新进入ProductEventAnalysisService._phase，复用当前原事件SourceOwner/journal、claim、安装与控制重验；同事务读取Case/Run关联，核对原事件payload hash metadata、触发key和时间顺序。aip_evidence保存启动用途、原事件/Case/Run引用、证明快照hash与L1待取证清单，不复制客户正文，不将AIP run_id虚构为业务Run；稳定tenant+Run identity，冲突只回读、漂移/撤销拒绝。

真实PG暴露旧纯合同测试未覆盖的差异：biw4_006初始Run状态采用PostgreSQL jsonb::text hash且省略可选字段。新增RunStore.get_verified只认可严格固定r1字段集的SQL原hash或既有规范格式，逐列对账，保留旧记录。任务准备改用当前验证读取并对照输入；测试升级为实际数据库Run，不放宽hash校验。

## 验证

- 先排除测试fixture误用weekly Case与Host/DB时钟约60ms偏差，再得到缺模块5失败。
- 初次实现真实路径暴露初始状态hash差异；按原格式验证后通过。
- 启动证据/Task准备/原事件Host/Run合同：20 passed、1严格xfail、7 warnings，10.20秒；该xfail仍是正式Compilation桥未接，不改。
- 增加证据写后撤销当前审批角色的回滚测试：启动证据8 passed，7.44秒。已验证无残留、同键回读、Run ref错误、原批次错误、当前控制撤销、Evidence撤销、状态hash漂移及未知格式拒绝。
- AR2登记新Host调用方后1896扫描/174分类/93迁移，所有错误数组为空。memory validate GREEN/AOS-000573，1100 delivery/1083 task；diff --check通过。

来源/installed与组锁使用具名fixture；真实PG验证的是Case/Run/claim/Evidence等实际表及当前控制检查，不冒充真实商城启动验收。未创建主库业务Run/模型调用/部署/push，230 L0仍挂起。无页面修改。内部服务尚未与正式START编译桥组合；SC3准备当前Eval与Context，SC4接Saga/TaskRun。启动证据不满足经营事实完整性。
