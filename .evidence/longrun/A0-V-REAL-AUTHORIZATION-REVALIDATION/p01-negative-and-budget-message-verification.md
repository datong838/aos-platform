# P01 重复运行边界与提示验证

2026-09-13 02:38，m1。真实验收基线80171540，资料提交ec63cb64。

原成功Run scr-4a7626db8f3d436e的recover返回409 SCHEDULE_RECOVERY_CONFLICT。额度已耗尽的再次手动运行scr-21a34d9c8a4a40df失败，729ms、0行、executor_stopped=true；当前控制SourceClaim仍1条，拒绝Run没有原始Journal，原成功Journal和Dataset Receipt hash保持不变。计划sch-p01-qyh-controlled-20260913-v1已通过API停用并经DB复核，Cron仍关闭。四份p01-formal-negative-*-v1.json保留HTTP与数据库证据。

提示缺陷修复：Owner仍用原持锁额度检查，只改抛SourceCallBudgetExhausted类型；线程结果只识别exact类型返回固定中文和PIPELINE_SOURCE_CALL_BUDGET_EXHAUSTED；不改变行为，不传播自由异常文本。新增测试先因模块不存在RED，修复后专用/普通错误真实线程测试与管道/受控运行/PG额度竞争合计117 passed，15.57秒，7既有warning。AR2 ar2-7闭包1808/158/93，五类错误为空，diff检查通过。API尚未加载此新提示，旧真实失败记录保持原状，不能声称新中文已在实际API验收。

入口发现：真实IAB目录为空；当前旧GET /v1/ecommerce-workshop/modules使用legacy_content_predicate排除runtime包，不能去掉过滤。此前AR2八页浏览器结果明确使用拦截fixture。已存在RuntimeUiSessionView/ProductionUiSessionResolver/ExtensionHost；先核对当前签名包是否提供frontend及resource origin，再决定最小目录/会话接入。新路径必须保留禁用/卸载/角色/标记/租户隔离，不能静态补八个菜单或拿运行状态projection当命令授权。

总目标未完成：P01只证明Shop受控快照；商品/SKU等真实首链数据、自然Case/Run、来源化分析、exact方案评审、内容与能力产物、人工评审续跑、总控Wiki和八业务场景仍需逐项验证。下一波先核对签名前端与真实安装入口方案，同时对照经营参谋任务图谱安排商品尖刀验证链。
