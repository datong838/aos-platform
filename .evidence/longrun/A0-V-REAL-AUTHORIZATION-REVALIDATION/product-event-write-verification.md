# BG-02 事件策略原子存储验证

2026-09-14，基线c47ae4e9，租约A0V-PRODUCT-EVENT-WRITE-20260914。新增a0v_040事件专用SECURITY DEFINER函数，固定search_path，仅runtime EXEC；复用原策略head/history/Receipt与Case两表。旧定时写函数与表权限不改。策略保存恒未启用，不生成批准、ScheduleBinding或Occurrence。

RED：原7项因函数不存在失败。实现后15项通过；追加规范UTC负例发现PostgreSQL接受秒60和无意义零微秒，2项失败。补UTC格式回读比较后，完整迁移链隔离PG、039存储约束、包策略及Case组合累计55项通过，无skip。验证含首次/后继双版本原子写、原Receipt跨head回读、同key冲突、CAS冲突、跨租户与缺scope、重算hash后的方法/Case篡改/NULL、外层回滚、禁止直接表写以及未启用投影。

日志：/tmp/product-event-write-red.log、/tmp/product-event-write-time-red.log、/tmp/product-event-write-final.log。数据库均为18432服务创建的临时*_ti4_test数据库；主库18435未迁移，仍038。代码head040不等于主库部署；未重启Host/API，未产生真实自然Case/Run。本片仅持久化边界，当前来源、当前身份、exact批准与运行准入由后续Owner负责。

下一波：按既有集成方案补Host事件存储适配；严格schema分派、原keyReceipt回读、事务由调用者控制，保持旧定时API结构不变。随后接当前来源/方法与exact审批，再接事件绑定/Occurrence消费者、产品入口及真实链验收。
