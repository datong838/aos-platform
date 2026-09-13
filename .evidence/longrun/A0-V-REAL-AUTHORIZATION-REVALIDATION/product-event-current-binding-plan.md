# BG-02 当前事件策略与Case读取门

基线67e28e91。保留旧定时解析器，ProductEventPolicyStore新增get_current_binding(policy_id)，只读、不发许可。单条作用域查询连接策略head/current revision及Case head/current revision；校验策略schema/摘要/实际版本/历史正文一致，当前Case摘要/版本/lifecycle ACTIVE、策略引用及methodRef一致。返回policy/caseAuthority，未找到策略返回None，已有策略但历史或Case断裂拒绝。不把head.enabled映射成批准或运行权限。

代码services/aos-api/aos_api/ecommerce_product_event_store.py；PG测试services/aos-api/tests/extension_runtime/test_product_event_store_pg.py。测试合法保存、当前绑定、未保存、Case关闭/换策略、策略head漂移拒绝；故障注入仅隔离数据库事务、恢复原运行role后读。旧get/原Receipt不变，允许历史Receipt恢复不受当前Case显示状态影响。

读取不替代消费时加锁/当前Owner复核。后续启用/消费Owner调用此读取后仍需锁当前authority和精确签名合同；自然Case/Run/八场景/观察未完成。

本波将读取门接入ecommerce_product_event_host_service.py._check：在041锁之后代替仅查head版本的查询；已有策略同时核对current Case绑定，初次保存仍允许None，原Receipt恢复保持但当前已换绑/关闭必须拒绝写路径。补服务测试回归。测试不修改不可变历史，追加后继Case验证拒绝。
