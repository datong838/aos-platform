# 本地源接口实际 HTTP 核验

2026-09-11，代码基线 78916007，诊断 API 18181，同一隔离恢复库启动器。旧 PID 6683 优雅退出后启动新服务；启动前 OpenAPI 无源探针，启动后存在 `/v1/sources/{source_id}/test`。

- GET /v1/sources 未认证：401 AUTH_REQUIRED。
- GET /v1/sources，开发身份、org-org/dev-project：200，items=0。
- POST 不存在的 a0v-nonexistent-readiness-probe 源，零 UUID 版本：404 SOURCE_NOT_FOUND。

未创建数据源、未提供连接凭据、未调用上游；不是有效源版本的连接成功或生产身份验证。启动日志确认迁移关闭、扩展执行器及业务定时任务关闭；既有启动内存冷启动 seed 日志存在，因此不将整个服务启动描述为绝对无状态变更。已有 Pydantic 警告仍在。

原真实连接配置位置仍待提供。真实接入、完整经营首链、八工作台与观察发布均未完成。不 push，230 L0 挂起。后续补齐事实接入与可信内容上下文，配置可用后再实际连接。
