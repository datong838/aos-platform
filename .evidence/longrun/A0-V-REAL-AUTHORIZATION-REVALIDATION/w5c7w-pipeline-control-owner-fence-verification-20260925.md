# W5c7w Pipeline Owner 可选 fence verification

方案 `d5ea92ed` 先提交；红测 2 项先因 `build()` 不接受 `host_lease` 失败，最小实现 `9e7b0bbf` 后工厂专项 **9 passed**。测试精确覆盖默认 None、错误对象/跨租户连接前拒绝、selection/control/bind 三路同连接 fence-before-write；不 acquire 真实 lease。近期 A0-V no-effect + main lifecycle 累计 **239 passed**、7 warnings/20.13 秒，旧长例未重跑；`git diff --check` 通过，临时 `aos_test_%` 库 0，测试 PG 停回原态。

浏览器 2026/9/25 18:42:27 CST 只读核对 A0-V Canonical rev4「已停用」「数据组已停用」；待同步写操作 1 未冲刷，页面与 Vite 已关闭。真实 closure 只读门仍 `automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false`、12 原 Run running、stalled Receipt 0，缺全机拓扑、Fresh Owner 同事务门、独立方案/key。

复审与方案一致：默认调用形态无额外参数，生产 `main.py`/Host 未注入，真实 DB/Host/Store 均无改动。当前顺序测试不是失租并发 PG 证明；下一波 W5c7x 先做隔离 PG 三 Owner 的 fence 拒绝/回滚/同事务验证，再逐个拆三业务 worker 多提交边界。真实 opt-in/closure 冻结；旧 attempt 不重发、不手工 run_definition、商城源行不读、230 L0 挂起、dev-org 零 canary、m1 不 push。
