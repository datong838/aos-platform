# UQ3-A 单次领取与原子封存验证

2026-09-13，基线a8707a06。ui_read_worker_store在调用者事务中锁请求行，核规范请求/当前binding，建立唯一signed_read Attempt并记录claim。owner token不出现在repr。已领取或终态不再给出执行claim。封存校验token/Attempt/版本/原target，先结束Attempt再更新结果；期限到或绑定失效丢弃结果。

10 passed、7项既有warning：真实隔离PG双连接只领取一次、领取整体回滚、终态不可重复封存、伪造owner/target拒绝、失败/绑定失效、真实短期限过期、超限结果写入失败使Attempt一并回滚、负租户不能领取。成功结果{}仅测试账本原子性，不是业务结果验收。AR2扫描1843模块、163分类、93迁移，错误集合为空。

没有包调用，没有主库迁移，没有API或宿主新授权。下一波UQ3-B处理待领取/已领取过期恢复与原宿主具体消费者；后者必须再次校验当前成员/签名目标、同快照与原PreparedJob，使用固定独立只读方法analyst_workspace_view_v1，不能借九项业务命令通道读数据。新包尚未交付，业务链未完成。
