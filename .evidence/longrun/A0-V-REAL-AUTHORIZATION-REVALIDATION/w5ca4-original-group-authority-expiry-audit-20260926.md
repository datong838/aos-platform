# W5ca4｜原组关闭权威与 18181 租约责任只读复核

方案 `m1@10dd1ce7`。新鲜读回 W5ca3 本地诊断进程 PID36529、`launchd runs=1`、唯一 loopback 18181，8080 无监听、恢复 PG 唯一 Up；m1 精确进程 lease ACTIVE 至 `2026-09-27T04:00:00+08:00`，尚未到期，不能预告到期自停。未续租、未运行 worker/definition、未读商城源。

一次 W5c9d 只读原组/受管目录/本机 Host 分类：`LOCAL_QUIET_NO_GLOBAL_AUTHORITY`、`timeGate=ELIGIBLE_NO_AUTHORITY`、`knownLocalHostCount=0`、`runningOriginalRuns=12`、`automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false`。独立 W5c4t 精确原组只读分类仍 `STALLED_ELIGIBLE_REQUIRES_FRESH_AUTHORITY`，原 attempt `a5e60b0d-2d97-44d0-88bf-9f08990624d1`，严格时间门已过但 `automaticAction=false`；其硬编码精确效果/Receipt/Facts 全部匹配，否则会 FROZEN。此分类不把全租户 Store Receipt 26 当原组 12 条 Dataset Receipt。

静态复审 W5c9h：原十二 Run 无独立于保存输入链的原始行语义 hash/row-count 复核，不能重读商城源来补造历史证据。W5c7t：仓库/当前现场没有覆盖全部机器、离线节点、旧入口和部署 revision 的权威 Fleet Universe；本机 Host=0 不等于全机安全。W5c5g：读门非跨面单事务，缺 Fresh Owner 同事务 closure 方案/唯一 key。以上三个缺口彼此独立；本波不启动真实 closure、不发 ACK、不改变十二 Run。

工程顺序建议：W5ca5 优先做 `FRESH_SINGLE_TRANSACTION_OWNER_GATE` 的现有代码/SQL/隔离测试覆盖差距清单，找到一项可无真实库迁移、无业务效果地缩小的缺口；若只有外部 Fleet/历史 row proof 无法取得，显式保留 no-authority，而非持续重复现状文档。18181 lease 到期必须由守卫停进程且由独立现场读回验证；当前只证明未到期、runs=1。
