# CF3-2 简报引用环修正验证

基线b182e0de。旧Brief→L2 Profile→Context→Brief形成创建hash环。新增显式v2 TaskBriefIntentSpec(case/run/domainProfile/analysisType/compilerProfile)，保留原v1；编译请求v2验证Case/Run/分析类型/compilerProfile且领域与L2独立。桥接要求领域exactRef等于原L1，编译resolver新增DOMAIN_PROFILE。合法顺序为Task→意图Brief冻结→Context→L2 Profile→Compilation，无两份不一致Brief或虚构引用。

Red v2合法输入失败1项；Green新意图5+绑定11+旧编译5+Saga6共27 passed，/tmp/cf3-brief-intent-green.log。追加DOMAIN_PROFILE_NOT_RESOLVED在Plan创建前拒绝5 passed，/tmp/cf3-brief-intent-resolver.log。AR2 1894/172/93全部错误为空，memory validate GREEN/AOS-000573，diff --check通过。仍是合同/Saga测试，真实Task/Brief/Context尚未组合。

下一波CF3-3 Task及v2简报的真实事务准备，之后当前证据/Eval与Context、CompileSaga；CF4 START缺编译已知失败仍在。未主库写入/部署/push，230 L0挂起。
