## SC4-5l6e4 快照续跑事务上下文（2026-09-15）

基线dacd295c，m1/AOS-000573。新增services/aos-api/aos_api/ecommerce_analysis_snapshot_resume_context.py与services/aos-api/tests/extension_runtime/test_analysis_snapshot_resume_context_pg.py；原snapshot-resume-design.md已先细化两阶段及下一波重试分支。阶段A完成原Fulfillment/Business/Bundle/Brief/Readiness与paused检查，通过原a0v_049锁当前需求Head并持有到外层事务结束。阶段B重新进入原完整Projection与QueryBinding当前守卫；原GroupInput和projection必须与阶段A一致，重读原策略、固定Query/Quality、证据撤销、冻结Brief Head、Bundle/Readiness/Fulfillment和完整Requirement，前后检查同backend/txid/双租户/命令hash/原最早期限。退出后stage失效；不再进入要求旧paused/WAITING_DATA的守卫。

本段只交付内部事务上下文，不向TaskStore注册执行许可，不执行Task/Run转换、不触发Provider。Red为新增模块缺失（/tmp/sc4-e4-red.log）；本轮18432隔离PG 10 passed /758.25s，7项既有warnings（/tmp/sc4-e4-green.log）。完整十二源沿原Owner实际保存，原分析初始化/当前来源与Provider依赖仍有named fixture；不得声称真实经营端到端。正常用例证明阶段B后不重入旧Pending、只一次fixture源读取、实际Task仍paused、阶段结束后上下文拒绝复用；异常用例在回调写入实际探针后分别改变命令、租户、Binding、Quality撤销、Business撤销、策略、Origin、返回延迟生成器、换数据库连接，检查探针整体回滚。

AR2验证1950扫描/191分类/93迁移，五类错误列表空（/tmp/sc4-e4-closure.log），未修改旧preHash或验证器。主库仍最后核得a0v_038，a0v_049只用于18432隔离schema；无主升级/安装/商城读取/真实任务/Provider变化，未push，230 L0挂起。用户原文档、package.json和package-lock.json改动保留。

下一波l6e5：按已登记方案串行实现快照专属内部Session、原Task/Run单次恢复和统一Receipt、已提交只读回查及未知结果路径。原旧resume_data继续独立验证。已有成功不能再次通过Pending准备或再次恢复；查不到确定结果不盲目重发。之后e6原真实初始化起点+完整十二源组合、Outbox自然自动消费、主升级安装、真实首链与八场景/观察/发布判断。总业务目标未完成，自动接续。
