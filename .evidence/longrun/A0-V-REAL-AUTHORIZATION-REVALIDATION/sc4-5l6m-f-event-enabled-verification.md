# F 真实事件启用成功

Policy product-event-qyh-full-store-generation-f-20260916 revision 2 经真实 AIP 提议、精确审批与 canonical router 保存；Case 后继为 version 4。新来源窗口为 2026-09-15T20:29:51Z 至 20:44:51Z。

F installation 245959da-9d11-462c-9922-7d08f459992b / generation 0e85a39b-7841-4378-b6c9-2984c4a685c8 / epoch 3。

独立回读 event-enable-v3/live-readback.json：
- automation_schedule_binding：revision 1、policy_revision 2、enabled=true、approved=true。
- v3-control 业务 Receipt 1，通用运行 Receipt 1。
- dev-org/dev-project 负租户事件绑定 0。
- 通用 Policy head.enabled=false；当前 Product 事件消费者按 automation_schedule_binding.enabled/approved 判断（ecommerce_product_event_discovery.py），不读取旧 enabled 字段。不能用该字段替代事件控制权威。

26 项窗口/幂等保护测试通过。下一步真实 P02 Product 数据执行与自动事件消费者观察；不声明 Case/Run 首链及八工作台经营闭环完成。
