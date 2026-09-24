# W5c4j 组负载与控制续期设计方案（2026-09-24）

W5c4i `1ee800cd` 证明当前 cron 下次 20:00 UTC，而 12 控制 19:50:47 到期，不能 enable。历史 W4 注释称 12 路同时派发曾导致 2 CPU/3 GiB Host 续租饥饿，但需追溯当前整组执行实际并发边界，不把事故猜测写成新代码需求。

1. 只读追 `dispatch → runtime.execute → claim → ingress → completion/Store`，定位真正并发/超时/资源续租边界及历史 W4 失败记录；不读商城源行。
2. 找正式 Selection/Control/Binding/Definition 在 disabled 状态下的续期机制，列出是否必须重新生成 12 条链、对 current member 的影响、窗口应覆盖首次 slot 后多久。
3. 提出最小可验证方案：若单组仍有不可控 12 路负载，先定向测试/容量门禁，再续授权和启用；若现有执行器已有串行保护，则证明而非改动。落验证和下一波具体任务。
