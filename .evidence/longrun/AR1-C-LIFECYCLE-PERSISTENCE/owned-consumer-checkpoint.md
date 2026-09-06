# AR1-c 原持有者验证启用消费联合检查点

2026-09-06；基线m1@969536a2/AOS-000540，主Lease继续。

OwnedControlConsumer只接已有PreparedJob与精确TenantScope，按installation/kind领取原outbox；已确认终态不再次调用，accepted调用原job.verify/enable，保留原健康、权限、schema/config和安装事务权威。enable在进入owner.control前用原不可变目标reader核对generation，错代只延迟，避免误触不匹配owner清理。PreparedJob新增只读scope路由属性，旧构造兼容。数据库连接检查抽取consumer_connection供停用和持有者消费者共用，原隔离强检查不减。

请求取消只撤销等待；独立内部task注册单实例消费，不得并发覆盖。内部task关闭取消同样以原_settle等待claim/read/原job命令/ACK线程收敛后传播，宿主须wait_idle再stop原owner。不会由消息重投重建旧IPC owner。权限/CAS失败不ACK，未知phase受限retry。

测试：初始12Red→40相关passed16.16s；Prime发现内部取消早退及错代owner路由，两项补方案与实现、反证。16专项passed8.12s，再加read/command连续取消共18专项，最终累计864passed、6既有warnings、125.19s、exit0。真实签名Registry/Installation/实际专用OCI原owner链通过；verify与enable分别注入提交后ACK SQL回滚，精确claim过期再领，不允许再次执行，operation revision和binding epoch/revision不变，剩余旧事件限定30次内确认，17.92s通过。测试编辑时错位断言NameError已修正，无生产放宽。git diff --check通过。

Prime复审两项补强均落实，无新增实质问题。无页面改动，不称新增浏览器验收；仅隔离18432临时schema与专用OCI，无共享迁移/业务写/Provider/费用/发布。配置与drain仍命名测试权威，新业务场景0，整波未完。

下一段：准备消息消费与单安装有界持有宿主，领取→原worker.start→保留原job→准备完成ACK，取消或ACK失效不丢失已创建owner，关闭收敛；随后正式配置/broker/预算和完整启停卸载重装。
