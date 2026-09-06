# AR1-c 恢复批次与outbox联合检查点

2026-09-06；基线m1@5de57310/AOS-000538，主AR1-C-LIFECYCLE-PERSISTENCE Lease继续。

复用原账本，无新增迁移。恢复批次单页1..100、immutable结果/cursor，只跳过明确busy/live，不吞权限/DB/身份失败；到尾由下一扫描轮重置cursor，不能永远停尾。精确当前CAS的准备收敛仅提交前4phase，至少一资源且observed_release与cleanup_state双事实一致，拒绝committing/succeeded，修复旧接口可能改写提交历史的缺口。

OutboxStore复用attempt/claim_until/next_attempt/delivered_at：固定runtime-reconciler、显式scope、事件hash、SKIP LOCKED互斥；attempt是新领取代次，期限由DBclock。ACK/retry锁后复核代次/完整事件定位/精确期限并重读DB时钟，不能以旧worker确认新代。ACK只表示事件已对账，不更改operation/resource或发放执行许可。无通用callback伪造业务成功。

验证：阶段/释放事实8Red后相关86passed1skip16.25s，新增批次异常分类21passed8.70s。outbox9Red→联合30passed8.58s；完整事件定位3Red→补齐；包含等待行锁跨期拒绝、过期再领及两个连接单赢家，专项34passed10.50s。最终累计836passed、6既有warnings、119.91s、exit0；测试范围沿用前检查点安全集合，已包括真实OCI新进程恢复。git diff --check通过。既有JDBC关闭日志流警告不影响exit0。

Prime独立只读复审无新增实质问题，指出扫描到尾须重开周期、事件不能假定sequence顺序；已明确宿主约束。无页面改动，不称新增浏览器功能已验。仅18432隔离PG/专用OCI，无共享迁移、真实业务写、Provider、费用、发布。新增业务场景0；AR1-c整波仍未完成。

下一段自动进入具体停用消费者：持久领取提交后调用既有停用执行器，按当前operation/CAS处理乱序/重投，实际成功已提交但ACK失败时只回读终态，不重复推进；再接准备/验证/配置等持有者与正式broker费用合同。
