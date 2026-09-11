# D01 方法权威验证

2026-09-11；m1基线5a22c175；任务A0V-D01-METHOD-AUTHORITY-20260911；AOS-000573。方案portrait-method-authority-plan.md，五文件pre/post hash见portrait-method-authority-files.json。

MethodRevision正式合同限定descriptive_snapshot_v1/observation，保存名称、解释、来源条数/年龄界限及局限。既有Analyst Owner补publish_method/get_method_exact，完整hash和真实prior检查、method身份和幂等键锁、原有CAS/Receipt原子保存。当前引用读取allowlist补MethodRevision，历史exact仍可达。未复制指标/查询/Eval。

新增a0v_013 additive两张表，复用原receipt，线性head、deferred receipt FK、FORCE RLS、不可改删/截断历史与runtime最小权限。测试发现默认权限给新表继承UPDATE，修复为先REVOKE ALL FROM aos_runtime再按head/revision授权；历史触发器本来也拒绝变更，但现在同时满足最小权限。

**205 passed，7个既有warning，7.89 s，退出码0**。环境AOS_DOTENV_DISABLED=1、AOS_TEST_USE_SHARED_DATABASE=1、AOS_GROWTH_DRAFT_FULL_GRAPH_TEST=1、AOS_GROWTH_DRAFT_OWNED_CLONE_TEST=1；范围为method_authority、authority_contracts、authority_store、diagnosis_worker、diagnosis_service、diagnosis_receiver、diagnosis_generation、growth_plan_receiver、growth_plan_generation、growth_plan_worker、growth_plan_full_graph对应11个test_ecommerce_analyst_*.py。

方法专项24项包含两个完整一次性PG：提交前回滚零head/revision/receipt、并发同key同一结果、异key或key复用冲突、错误prior拒绝、r2追加/r1历史可读而不再current；aos_runtime真实角色可写读自己的方法、dev-org看不到、即使管理员更新/删除/截断历史也受guard阻止、runtime无UPDATE权限。其余诊断/方案关联回归通过。Alembic heads为唯一a0v_013；git diff --check通过。退出后既有JDBC日志关闭流提示不影响退出码。

仅一次性测试库应用012和013；主库仍012，API仍旧进程，未应用013或新增真实方法配置、未调用Provider。此为方法元数据权威，不是D01画像已生成，也不是因果分析能力或批准。旧012等其他表的默认权限需要在实际启用正文留存前另行核对，不在此波扩大修改。

下一波读取现有MetricDefinition/EvalContract和当前Method、完整受控Bundle，形成D01固定请求与可信Insight；之后D01工作者、正式三阶段宿主/运行配置、真实数据恢复、经营参谋业务计划首链、八场景与持续观察。整体未完成，不push，230 L0挂起，自动继续。
