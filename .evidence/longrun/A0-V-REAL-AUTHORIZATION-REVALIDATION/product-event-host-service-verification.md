# BG-02 事件Host写入服务验证

2026-09-14，基线87cca430，迁移租约A0V-PRODUCT-EVENT-AUTHORITY-LOCK-20260914。新增ProductEventSchedulePutHostService，严格七字段命令；来源Guard内核对当前Case/Profile/Scope、两版本与原精确批准，040保存后关闭旧调度绑定并再次复核批准有效期。读取原key Receipt，不以新head替代原结果。actor由可信Host注入，无默认，不从包命令接收。

首次真实PG揭示Case表无UPDATE导致普通FOR UPDATE失败；未放宽权限。新增041按当前tenant/runtime执行精确Case/策略/批准/Proposal锁，无行写入。批准验证提取共享纯函数，旧定时仍保持原加锁查询。测试环境历史迁移批准表有UPDATE，因此另在隔离事务显式撤销UPDATE，验证真实批准行读取+041仍成功；Case始终无直接UPDATE。没有将权限假设当证据。

累计100 passed，无skip：新服务12项、原适配器20项、事件Store/040/包组合与来源Guard。来源Owner和方法目录仍用具名替身；大部分批准负例用具名返回行，另有真实批准表+受限权限成功验证。fixture种子仅隔离临时PG，不代表真实审批。执行中到期、未来批准、proposal版本/摘要漂移、方法变化、自报actor、跨租户/缺scope、来源拒绝都拒绝/回滚。

AR2首次发现新Host反向调用者未登记；按已有Host权威读取边界补清册新行（不改历史preHash）与实际路径约束。重跑1867模块/165分类/93迁出，所有错误数组为空。日志/tmp/product-event-host-{red,green,green2,expiry-red,lock-green,lock-green2,final,closure-final}.log。diff和memory-validate通过。

主库仍038，代码head041，未部署或重启Host/API。新服务未注册，未形成实际自然Case/Run。下一波：包事件命令与正式Host装配，解决真实当前执行身份及来源Owner注入，核验原批准人当前权限后再纳入资格登记；随后事件绑定、Occurrence消费、产品入口与实际自然链。真实首链/八工作台/连续观察仍未关闭。
