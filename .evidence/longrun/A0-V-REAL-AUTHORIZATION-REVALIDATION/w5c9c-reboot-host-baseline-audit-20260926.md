# W5c9c｜重启后 knownHost 拒绝根因审计

方案 `m1@b4a740ef`。分解 `a0v_w5c5c_host_role_topology.observe()`：W5c4t 基础 read-only 观察成功；宿主 `ps` 精确已知 Host launcher 计数 0；注册角色只读 SQL 成功、角色存在 1。唯一 ValueError 在其 `prior` W5c5b observe 链，进一步定位于 W5c4s `_read()` 的 `prior._worker()`，明确错误码 `W5C4Q_INDEPENDENT_WORKER_DRIFT`。

原因不是数据库 Run/role 漂移：W5c4q `_worker()` 要求其历史状态文件 `workerState=IDLE`、`workerTaskAlive=true`、`topology=independent`、PID 等于 18181 listener 且 observedAt 新鲜 10 秒。电脑重启后旧独立 snapshot worker 已不在；当前 18181 是 W5c9a 受控纯 HTTP 进程 PID26881，明确 snapshot worker=false。旧观察器因此按设计 fail-closed。不能把旧 worker 状态改写为当前 PID，也不能删除条件来宣称全机 Host 拓扑完整。W5c5g 组合门依赖旧 prior，当前不可作为真实关闭授权。

W5c9b 精确 DB 仍证原组 12 stalled-running、closure Receipt=0；受管目录只证明已知目录与三条 released lease，`topologyComplete=false`。本波无 DB/服务/代码变更，没读 `ps args`/plist Env/凭据或商城源。下一波应独立设计当前阶段的**无执行、只读、重启可复核** Host/Owner topology evidence，保留 `automaticAction=false`、`closureAuthorized=false`；严格 24h 到线也不改变这些限制。
