# N8 路由所属包签名前端解析验证

基线 90f9a33b，按 runtime-workshop-routed-ui-plan.md 第 1 项实施。

ProductionUiSessionResolver 新增可选 requested_route。无参数保留原单前端规则；有参数按安装组合中唯一 navigation 归属选包，核对其 UI 精确 routeClaims 不越出所属包，并继续原锁/Release/签名资源哈希校验。另一个包即使没有 frontend，也不能重复占有该路由。

- 初始 RED：9 failed（原 resolver 无此参数）。
- 补充重复归属但另一包无前端的 RED：1 failed；修复为计数整个组合的路由所有者。
- 最终路由、原资源解析与 Runtime Installation API 联合 31 passed，7 条现有依赖警告。
- AR2 ar2-7：1831 /159 /93，五类错误为空；diff check 通过。

这是解析合同的隔离测试，无主库写入、无新签名前端交付、无目录开放，也未重载 API。当前实际包仍不声明 frontend，页面保持关闭正确。下一波将路由参数接到 current-ready RuntimeView 和只读 HTTP 会话，再衔接运行时工作台目录及新包 frontend/bridge 交付。真实切换仍待独立审批身份和正式动作定义。
