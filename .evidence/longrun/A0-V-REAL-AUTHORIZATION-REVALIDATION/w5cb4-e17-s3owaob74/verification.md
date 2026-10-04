# b74 数据库强制门真实前测

B74_REAL_STORE_BYPASSED_EPOCH_FENCE实际(0,1,1)，1failed/7warnings/15.09s；有效全新fixture，原Store实际撤销成功，独立admin epoch0/event1/Receipt1。不包装epoch UPDATE，原tenant connect、Store请求hash/Receipt/commit保留；证明现隔离epoch仅靠包装器不能约束原生产写路。不是正式触发器失败，也不声明正式源可信。

B74关闭的b73候选相邻复验1passed/7warnings，原并发同key/首次事件回滚/冲突与b70/b71/b72断言仍运行。编译与diffcheck通过，仅两测试opt-in分支修改，无生产Store/迁移/135库/服务动作、无UI浏览器不适用。authority与strong投影本次CURRENT，validateGREEN。

自复审：unwrapped只关闭候选epoch锁/UPDATE，不绕过真实Store；新key/有效来源fixture避免重放旧撤销掩盖效果。原失败保留不xfail，未改断言求GREEN。正式DB强制门仍待b75；下步设计见b75-plan.md，最小权限RLS/固定search_path与raw SQL/missing exact/canary必须验证。Goal active，不将前测当整链完成。
