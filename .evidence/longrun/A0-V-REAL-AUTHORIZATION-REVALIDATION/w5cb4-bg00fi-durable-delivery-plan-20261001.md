# BG00FI 新批准事件持久投递

m1@c1c86169/AOS-001023；Task W5CB4-BG00FI-20261001。复习231-5§3/5/7与416、runtime/data-requirement/Action outbox及a0v118-122边界。

## 选型事实
通用aip_action_dispatch_outbox依赖execution_attempt/lease，不能绕独立网络consumer复用。RuntimeOutbox仅runtime operation；DataRequirementOutbox亦为领域绑定。采用专用网络批准投递表，仍使用现有consumer_call/consumer_owner，不新增高权登录或角色。

## 文件级计划
1. 新alembic/versions/a0v_123_network_approval_delivery.py（down_revision=a0v_122）：投递表同租户event FK；after-insert触发器只为新网络approved事件同事务登记，不回填历史。表归迁移owner，consumer_owner仅SELECT/INSERT及状态列UPDATE，API/runtime/caller无直接写权限；FORCE RLS双租户。
2. claim SECURITY DEFINER只允许consumer_call会话+精确GUC+原maker当前成员；SKIP LOCKED单行、固定30秒token fencing。pending首次返回dispatch，unknown或过期claimed只能inquiry；不把租约到期当重发授权。
3. finish同claim token/期限/原maker验证，只有immutable NetworkPolicyReceipt精确匹配proposal/event/target/binding来源才delivered；未找到为unknown并延迟再次查询。无客户端成功布尔值、无重置pending、无删除历史。
4. 新test_network_approval_delivery_pg.py：隔离PG事务原子登记/回滚、认领并发、防跨scope/actor/角色、过期认领仅query、无Receipt不ack、真实Receipt才完成；调整现有consumer_boundary测试仅增加新表状态列精确UPDATE允许集，不扩大其他权限。

## 安全和限度
仅在独立pytest临时库升级；当前真实库不迁移，现有最后实测a0v118不变。代码头将变123，后续正式恢复门相应需118到123备份/克隆/零执行验证。触发器只写投递事实，不调用消费者/Provider，不扫描/回放旧事件或12Run。生产轮询/身份供应及daemon IPC接线后续单独开波，默认保持关闭。每次实际消费仍经外部OIDC原maker及独立consumer最终门；此表不授予执行权。

## 验证与收口
RED缺表函数→最小migration→新专项及角色/原子消费/事件driver相邻累计→review→verification→m1精确commit/Receipt/CAS/417/D-waves。无UI变化，不宣称浏览器通过。下一BG00FJ接有界claim→单事件driver→精确finish，身份供应必须正式可验证，不能保存人类JWT或复用checker。
