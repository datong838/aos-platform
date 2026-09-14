# CF3-4 Context 本任务证据关联验证

基线41f6a470，m1串行，既有父Lease覆盖Host/tests；无主库写、无模型调用、无push、230 L0挂起。

## 缺陷与修复

freeze_production_context原来只验证四份合同各自有效，允许同租户另一Task的Brief或另一Brief的EvidenceBundle进入Context。方案已追加analysis-start-compilation-bridge-design.md CF3-4。修改公共Store的原同事务读取，增加Brief.task_id及Bundle完整brief_ref匹配，不额外制造业务事实或READY。

## 本次证据

- Red：隔离18432临时PG两个合同fixture交叉拼接，2 failed，均为DID NOT RAISE ProductionContractDependencyBlocked。
- Green：test_w_l11_production_context.py + test_w2d_store.py + test_analysis_task_preparation_pg.py，14 passed（4.16秒）。补无Receipt残留断言后Context 6 passed。
- Context与Receipt均在拒绝后无新增；正常冻结/同键重放、Bundle撤销、ProductionProfile来源拒绝保留。
- AR2 ar2-7：1895扫描/173分类/93迁移，所有错误数组为空。
- memoryctl validate：GREEN，AOS-000573，1099 delivery/1082 task/2697 events。
- 测试合同由隔离fixture提供，不证明真实业务Evidence/Eval质量。没有浏览器变化，无需将页面检查冒充该存储约束证据。

## 一致性与风险

正常dependency snapshot与hash形状未改变，历史同键回执仍为历史结果，不变成当前执行许可；旧不可变Context不回写。新冻结遇错接明确失败，属于预期收紧。真实START尚缺Compilation，继续保留严格xfail；未部署主安装。

下一波CF3-5：确定真实启动证据和评估合同的获取/用途，复核已有只读取数与Preparation协议，在本任务exact绑定下组合Context；不能用任意旧Eval或形式完整证据包提前置绿。
