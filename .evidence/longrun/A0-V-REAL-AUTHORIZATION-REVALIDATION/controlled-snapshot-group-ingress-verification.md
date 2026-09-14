# 原输入组执行器验证


SC4-5f4d：ControlledSnapshotGroupIngress完成，原组认领独立提交确认后一次读取，全部原ControlledIngressJournal输入和真实哈希manifest同事务保存。47项隔离PG组合测试通过（14.19秒），含新增13项、旧单表、组认领与schema；AR2扫描1914模块五类错误为空。失败/取消/读后禁入/第二输入失败整组回滚，认领保留且不重读；输入commit成功但ack丢失能完整零源重放。无对象apply/运行完成/Fulfillment，无主库迁移或真实源调用。本波fixture不是主真实安装验收。下一项：对同批对象开展关系/软删/业务窗口的方案与实际字段差异核对，采用包内声明与通用校验落实，不沿用未核验旧link别名。

红：新增模块尚不存在，收集失败。绿：原始7项通过后扩展到13项，组合47通过。源调用前独立连接验证两个原claim和一个group已提交；正常/空组重放输入相同，源仅一次；未知认领拒绝重读；保存回滚和第二输入故障均原input=0、group input=0、claims=2；输入提交ack丢失则input=2/group input=1且可重放。

边界：原源码输入仍按各pipeline存储，组清单不等于对象关联、质量或正式Observation/Fulfillment。当前运行、精确控制和有效窗必须仍成立；完成后跨窗恢复、生产Outbox消费和调度组绑定后续。旧单表执行器未修改。
