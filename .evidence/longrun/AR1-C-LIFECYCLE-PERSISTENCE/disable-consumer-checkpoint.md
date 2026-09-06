# AR1-c 具体停用消费者联合检查点

2026-09-06；基线m1@cf6884e2/AOS-000539，主Lease继续。

RuntimeDisableConsumer单步持久领取→当前operation回读→原RuntimeDisableExecutor→独立终态ACK。只消费disable；默认OutboxStore行为不变。连接必须独立IDLE、非特权runtime session、RLS与明确TenantScope。旧事件不按sequence重放动作，未支持阶段受限retry，执行错误不ACK。终态结果区分succeeded/failed/cancelled，不把消息确认当业务成功。

专项初始9项Red→实现；最终10项消费者测试覆盖非IDLE、其他kind、三种终态、失败不ACK和非终态延迟。真实签名Registry/Installation/当前权限/实际专用OCI持有者联合接入消费者，隔离注入停用提交后ACK SQL成功但事务抛错回滚；精确claim到期，新消费者不得execute，operation revision与execution epoch不变；剩余旧停用事件在限定次数内确认。联合11passed17.64s。测试脚本曾误写next_attempt_at及将committing当status，按原schema修正，未改变生产规则迁就测试。

累计沿用前检查点安全集合：846passed、6既有warnings、140.74s、exit0。既有JDBC退出日志流错误不影响exit0。Prime两次独立只读复核无新增实质风险。git diff --check通过。

仅隔离18432临时schema与专用OCI；配置/排空仍命名测试权威，不是正式业务broker。无页面改动，不称新增浏览器功能验收；无共享迁移、真实业务写、Provider、费用或发布。新增业务场景0，AR1-c整波未完成。

下一段：受原PreparedJob持有者约束的验证/启用命令消费，保留原权限、当前条件和取消收敛；随后准备持有者调度、正式配置/broker/费用与完整启停卸载重装。
