# W5c9z｜OpenAPI 可达性与受控部署门禁只读审计

方案 `m1@836360d5`。一次无 lifespan/端口/DB/商城源的短命进程展开当前 FastAPI 有效路由并读取 OpenAPI；没有调用业务 handler。有效 method route 4,515，exact 同 method/path 碰撞仍 10 组，每组两条注册路由、`include_in_schema=[True, False]`；七组已知参数形状（含 Dataset detail）在 OpenAPI 都是前置模板该方法可见、后置模板该方法不可见，路径总数 2,706。W5c9y 累计测试的业务 route 封印 4,511/原哈希保持。注意：这个结论仅覆盖已知十加七组、代表参数及离线当前代码，不证明不存在其它模板语义碰撞，也不证明线上 18181 已更新。

只读现场：8080 无监听；18181 唯一监听为旧 PID 28077；共享租约 `A0V-W5C9A-HTTP-ONLY-20260926` 为 owner=m1/ACTIVE/scope=`local-process/aos-api-18181`，到期 `2026-09-27T04:00:00+08:00`。W5c9e 已证该 wrapper 内租约守卫的代码/隔离测试及此前受控重载，**尚未证明真实到期自停**。本波未重启/续租/迁移/触发 worker，也未读商城源。若计划刷新 18181 以加载当前 OpenAPI，必须另波新鲜读回唯一 PID、lease、PG/Host/Cron/snapshot/迁移/sourceCalls/runsCreated，精确停旧进程后受控单次启动，并比较前后；本审计不授权原组自然重放或 closure。

决策：已知文档碰撞切片在代码/离线测试层关闭；下一波 W5ca0 先方案化 18181 当前代码加载与保守只读 HTTP 验收，任何门禁缺失则冻结而非启动。原十二 Run row proof/Fleet/Owner/ACK/closure 无权威；230 L0 挂起。
