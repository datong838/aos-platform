# 实际占用账本：仅初始准备态与首个不可变事件

复习231、actual-occupation-ledger-design-1610及actual-ledger-next1614。候选一根记录/初始事件依当前原Target可信call已有全部必要事实；候选二Target真实结果到Judge输入依实际admission/executor，暂不执行。选择一。

唯一产品路径 `/Users/ddt/work/projects/ai_agent/aos-platform/services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py`，追加显式artifact `occupation_target_ledger_statements()` 和窄 `public.prepare_capacity_target_occupation(bytea,jsonb,uuid,uuid,uuid)`。参数仍仅原Source packet/ref、完整plan、原Intent和call UUID；经原Target call producer重新验证当前原件再服务端派生根与首事件，不接收状态/金额/费率/是否占用。

私有call_occupation根FK原prepared_call；唯一call、原plan/purpose/case/physical/token/parent及preparedCallHash；initial_state只prepared_only，counts_as_inflight只false，immutable canonical SHA/origin xid pid。私有call_occupation_event FK根(call_id,content_hash)，首event_seq只1、previous_event_hash只NULL、state只prepared_only；immutable事件绑定根hash、原login/xid/pid。原NOLOGIN Owner/FORCE RLS/runtime无DML，两个表UPDATE/DELETE/TRUNCATE拒绝；分别deferred无条件提交拒绝。窄producer精确重放根/首事件不变、写后原Target facts再校验。

此阶段不实现状态转换/真实占用/额度分配/unknown释放/transport，不允许prepared变admitted或event2，不扩原held parent cap10，不将任意准备1minor/null价格视为执行风险。新账本不与旧prepared_debit双计数，不接默认migration或正式库。

先原签名Source/SCRAM/两独立批准/完整plan/原Input Intent真实call下缺接口42883 RED；再最小DDL/producer，新独立全库正向插入及精确replay、两表运行身份DML拒绝、两表专门deferred constraint拒绝、实际callerCOMMIT拒绝。独立六准备表0/Source1/xid aborted/原身份NOLOGIN/member0/31原资源保留。相邻纯测试验证原产品契约；不得重复已封存六负门造成原Judge50秒超时。浏览器不适用于未接运行入口artifact。

完整状态事件/unknown与费用责任/全锁图/最终实际COMMIT期限、formal首链后续另实施；不能以本阶段替代整个Goal。
