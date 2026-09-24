# W5c4i 自然触发与治理窗口只读核验方案（2026-09-24）

W5c4h `61513898` 新定义 rev1 disabled。正式 dispatch 对 `body.timezone=Asia/Shanghai` 转换当前 UTC slot 后匹配 cron；旧 W5 文档把 `0 4 * * *` 称为 04:00 UTC，与代码语义可能不一致，必须核验。当前 12 控制在 19:50:47 UTC 到期。

1. 只读复审新定义/绑定/调度、Runtime/Host、预算当前 revision/effective_until、12 控制 notBefore/expiresAt；对 `Asia/Shanghai` 用正式 `cron_matches` 算未来 48 小时首次匹配 UTC slot。
2. 比较首次 slot 与预算/控制窗口，核此前 12 路同刻运行导致资源饥饿事故证据、当前 Host 容量；明确区分“能配置”“能 enable”“可完成一组自然执行”。
3. 只读保存非敏感时间线和约束，verification/commit。若下次 slot 未覆盖授权，禁止 enable；下一波须选择有界续期/调度架构修正方案，不靠提前启用或手工 Run 绕过。
