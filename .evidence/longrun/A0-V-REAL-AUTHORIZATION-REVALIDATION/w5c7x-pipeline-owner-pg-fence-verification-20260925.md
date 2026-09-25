# W5c7x Pipeline Owner 隔离 PG fence verification

方案 `d2031366` 先于测试代码 `6939d225`。首次测试 fixture 未显式导入上游 `host_lease_case`，3 setup errors；补导入后 1 passed、2 项因同一 session 探针表名重复 setup errors；改成每例唯一表后新隔离 PG 专项 **3 passed**。这两次错误是测试 fixture 缺陷，已修，未改生产代码。

新 3 项证明：真实隔离 PG guard 允许当前 lease 下三入口提交；旧 epoch 三入口写前拒绝且行数 0；写后异常同一事务回滚。近期 A0-V 短累计另起会话 **239 passed**、7 warnings/18.74 秒；旧长例未重跑。临时 `aos_test_%` 库 0，测试 PG 已停回原态；`git diff --check` 通过。

浏览器 2026/9/25 18:50:21 CST 只读确认 A0-V Canonical rev4 已停用、数据组已停用；待同步写操作 1 未冲刷，页面/Vite 已关闭。真实 closure 只读门仍 `automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false`、12 原 Run running、stalled Receipt 0；缺全机拓扑、Fresh Owner、独立 plan/key。严格 24h 时间门并非动作许可。

复审与方案一致：测试只证明事务钩子到 SQL guard，不证明真实 Owner 全规则或上线。下一波 W5c7y 先方案，选择业务 worker 的单一跨事务路径，梳理 unknown/Receipt 和 Host fence；真实迁移/opt-in/closure 冻结。旧 attempt 不重发、不手工 run_definition，商城源行不读、230 L0 挂起、dev-org 仅隔离 canary、m1 不 push。
