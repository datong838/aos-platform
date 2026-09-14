### SC4-5l6d4b 原查询Binding当前守卫

基线eedcb999；新增AnalysisQueryBinding，事务GUC双租户校验、原Binding共享锁和Service解码，限定strategy.plan、active/healthy/available、无reasons、原时间窗口/version/依赖snapshot hash。使用同一TransactionBoundConnectFactory调用原PostgresBindingDependencyAuthority、ModelRuntimeStore、BindingReadinessService只读评估；复用ContentGenerateHostService._binding_dependency_authority纯检查，不调用内容生成。消费前后重读、复验模型和许可/依赖，过期、版本、依赖、输出变化与异步拒绝。返回安全refs/时间/摘要，不输出secret_ref，不写评估/激活或调用Provider。

Red新增模块缺失；首轮隔离schema未给aos_runtime USAGE导致不可见，已按原测试角色补齐；统一fixture使用DB时钟及合法创建/观察顺序。最后12新PG passed/5.10秒，加原BindingReadiness3与严格dependency27共30 pure passed/5.79秒，均7既有warnings。覆盖scope/状态/健康/过期/hash/模型阻断/撤销/写后变更回滚/输出篡改。PG仅原Binding DDL/行/角色/GUC/事务真实，模型和严格依赖为明确named fixtures，另有原算法回归；不是当前真实Provider健康验收。AR2扫描1944/190/93五类错误空，memory strong CURRENT/validate GREEN。

下一波SC4-5l6d4c完整安装快照输入：将原Source/Business/Quality/Query、当前基础计数、安装SnapshotReadinessPolicy及原Binding守卫组合为12来源typed事实，确保当前refs与same group/requirement一致，再接原SourceReadiness状态算法和Receipt。不能以两类fixture/历史health升级为完整ready；主升级安装、恢复/Outbox、栖月汇八场景实跑与连续观察仍未完成。无新源/模型/主环境/外部动作；m1、不push、230 L0挂起。
