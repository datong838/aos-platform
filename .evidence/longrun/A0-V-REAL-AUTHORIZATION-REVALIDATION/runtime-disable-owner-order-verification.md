# RuntimeHost 停用顺序实际复现与修复

2026-09-13，基线52448e64，m1串行。

真实事件：20:04:43Z最后续租；20:05:04.713Z旧实例disable受理；20:05:05.994Z至20:05:06.290Z三资源释放，未出现fencing/disabled_committed。v15错误栈为Host._consume→consumer.finish_claimed→executor.begin_disable→binding_store.fence→RuntimeRevisionConflict。旧进程不存在，Docker中仅两个数据库容器，旧绑定@5/epoch4被禁入但desired仍enabled。详见parent-disable请求、观察和failure-events JSON。

将原签名OCI生命周期测试从直接executor改为RuntimeHost._consume→真实RuntimeDisableConsumer→真实PreparedJob.stop，修复前1 failed（9.40秒），错误沿相同Host/disable执行栈。修复后先finish_claimed完成真实禁入与drain，只有succeeded结果才revoke。非成功不释放，清理异常仍传播且保留已完成停用。

第一次主机+实际OCI 25 passed；进一步把测试的无条件drain替换成实际GenerationDrainReader并带consumer PG回归，35 passed（11.24秒），7条既有告警。测试隔离18432随机schema/签名容器；断言运行前后既有容器集合一致，不涉及主库源数据。

尚未启动新Host/API；当前旧请求仍accepted，历史不修改。此提交修复后续正常停用顺序，但不声称当前故障已恢复。下一波须为失效accepted目标构建严格恢复协议，再新鲜目标正式停用，最终才允许新版启用。商品真实首读、自然经营链和八工作台验收仍未完成。
