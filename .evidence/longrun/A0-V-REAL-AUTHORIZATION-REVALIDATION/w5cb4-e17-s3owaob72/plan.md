# b72 License epoch 幂等与事务候选

基线代码06b64a64、权威AOS-001329；复习b70/b71方案、复核结论与真实Store revoke合同。只修改两隔离测试文件，不改生产Store、正式迁移、当前135库或运行门。

先增加独立opt-in replay probe，要求b71及b70合法顺序。实际同key同body调用真实Store两次，独立admin检查epoch、revoke event、production receipt不增加；先保留真实RED。若原连接退出回滚使replay不增加，则如实保留GREEN并继续并发同key及失败回滚，不预设失败。

候选修复仅在已有epoch行锁取得后，以同租户operation/key Receipt判断重放；不替代Store request hash冲突验证。新key错hash、强制事务异常须epoch/event/Receipt全部回滚；并发相同key须精确锁等待且最终epoch1/event1/Receipt1。仅测试候选，不宣称正式writer DB强制门完备。

验收：新逻辑实际一次性PG运行，两个b71顺序及默认相邻回归；新库自行清理，历史库不删；方案/逻辑复审、Task/Delivery精确commit、资料同步。真实未知结果不重复外部行为，测试失败先排障，不暂停整个Goal。
