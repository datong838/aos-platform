# SC3-2 当前原事件下的本任务Context组合

基线f9fdc8e1，m1串行；父Lease A0-V-REAL-AUTHORIZATION-REVALIDATION。实现AnalysisContextPreparation：同一来源Owner和事务内自动准备兼容StageTemplate、真实Task/frozen Brief、当前原事件Evidence、Bundle、首技能发布Eval和ProductionContext。入口和回调后重验原事件/当前控制/发布依赖；任一失败回滚，不建立虚假的AIP运行记录。

验证：隔离PG的test_analysis_context_preparation_pg.py、test_analysis_startup_eval_pg.py、test_analysis_startup_evidence_pg.py、test_analysis_task_preparation_pg.py与tests/aip/test_aip_skill_publication_service.py累计29 passed（6.22s）。包括相同Context幂等、完整跨表引用、外层回滚、Bundle实际撤销拒绝、发布撤销/重复Eval拒绝。累计测试发现fixture复用全局Logic身份冲突，给fixture分配独立身份，产品唯一约束未改变。

AR2 ar2-7扫描1898模块、176分类、93迁移；hash/import/dynamic错误全部为空。memoryctl validate GREEN，AOS-000573，1100 Delivery/1083 Task/2699 Events。git diff --check通过。

边界：当前配置职责/安装与外部模型执行为具名测试替身；任务、模板、证据、评测发布、Eval合同和Context使用真实隔离PG服务。启动Bundle只证明原事件关联，不代表经营事实或经营质量。尚未接入正式_start_lineage/CompileSaga/TaskRun，未部署主安装、未执行真实首链；严格START已知失败保留。下一波SC4接正式编译和运行血缘。
