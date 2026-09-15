# SC4-5l6m 收缩异步排空门

Rules：m1、方案先行、最小修改、隔离 PG，不 push、不迁移主库，230 L0 挂起。

基线 32efc9b2。修改未部署的 a0v_054 与原 PG 测试。在 exact fence 回执验证后、任何 dispatch 写前，沿 ar2_017 退役检查口径：同安装/代次存在 running execution attempt，或同安装/代次/epoch 存在 claimed occurrence / claimed dispatch attempt，则拒绝收缩。租约是否过期不替代终态。维持 runtime 与组行锁以及 serializable 事务，不新增人工终结或重试机制。

采用保守的安装代次级排空，可能暂时阻塞与控制入口无关的在途读取；优先保留已有任务和明确恢复语义。成功回执记录三个检查项、精确安装代次 epoch 和数据库 checkedAt；不把瞬时零值宣称为永久空闲。

先增加 running attempt 的有效/过期租约负例，检查错误后原分派和收缩回执未变，再由已有终态更新结束 attempt，同 key 收缩成功。随后增加 claimed occurrence/dispatch 分支测试。退出前执行当前生命周期回归。

该门不替代完整 Service 资格/审批链与 resumed 退役组合验证。

复核补充：dispatch attempt 的 unknown 同样未得到确定结果，必须与 claimed 一起阻止收缩；不靠租约过期或 needs_attention 字样推断已结束。
