# SC3-1 当前首阶段Eval事务准备验证

基线532ae00c，m1串行，父Lease覆盖Host/tests。先在analysis-startup-context-design.md登记接口、文件和实际发布测试复用方案。

AnalysisStartupEvalPreparation在当前CompilationSelectionReader回调内，只取蓝图首阶段技能。读取其原发布事件及最新有效状态、parent Skill、ReleaseGate与TTL，复用发布门报告hash验证器和原EvalRun核验；派生原isolated_skill_contract用途合同。当前同hash冻结合同必须唯一，缺失走事务锁+稳定key创建/冻结，不独立commit；回调后复验发布血缘、合同正文及唯一性。

测试共享helper由原test_aip_skill_publication_service实际EvalRunner/发布门/发布/技能发布准备段提取，原断言保留。测试使用隔离bind3临时租户、实际PG评测/发布/技能/合同表；模型路由、Logic能力、target/judge执行及安装Selection为具名替身，不是栖月汇真实模型验收。测试准备允许已知Host/VM时钟差自然消逝（上限1秒），产品未来时间检查不变。

Red缺模块4失败（先纠正测试请求类型名）；Green原13通过。复核增加回调中第二份同正文冻结合同，先1失败再补唯一性后最终14 passed/7 warnings/3.95秒。实际验证两条修订、同键相同、外层rollback无head，TTL失效、发布在回调中经原revoke接口撤销、下游异常及重复合同均拒绝并回滚。失败测试断言明确原因，避免无关错误误算通过。

AR2 1897扫描/175分类/93迁移，所有错误数组为空；memory validate GREEN/AOS-000573（1100 delivery/1083 task）；diff --check通过。无主库写、模型调用、部署或push，230 L0挂起。

下一SC3-2：使用本任务启动Evidence生成Bundle，与此当前Eval及配置职责合入Context，再SC4组合正式Saga和TaskRun。当前仍未消除原真实START严格xfail，尚未证明经营闭环完成。
