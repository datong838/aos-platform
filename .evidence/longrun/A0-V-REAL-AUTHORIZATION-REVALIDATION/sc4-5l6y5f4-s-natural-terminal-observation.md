# SC4-5L6Y5F4 S 验证：Policy9 自然终态

## 已证实

- `2026-09-17 01:00:12 +08:00`，Cron 自然领取唯一 run `scr-fa4d8b91162c4ef5`；没有人工 run。
- SSH tunnel 于 01:00:14 打开、01:00:15 ready；run 于 01:00:22 succeeded，65 rows，error code 为空，executor 已停止。
- 原始 ingress 已持久化，sourceId/configuration revision 与授权一致；runtime 只读身份能发现唯一合法 Product event candidate。
- schedule 在 01:10:38 被观察器自动禁用；最终 inflight/unresolved=0、负租户 dispatch=0、十条 route 未变化。

## 未完成与定位

- occurrence、dispatch attempt、investigation Run 均为 0。因此只证明“真实数据自然触发 P02 → ingress”，未证明“ingress → Case/Run”。
- derived command、dataset receipt 与 discovery SQL 均满足，actor 只有一个 admin membership；缺口已缩小到外部 Runtime Host 的 process-owned live target / ProductEvent worker 消费装配。
- 旧 Host 早于本轮部署启动；受控重载为 PID 5203 后仍未消费，说明仅重启不足，下一波必须增加 live target/worker 状态可观测性并修复装配，不能手工调用 worker `tick()` 冒充自然链。

## 观察器验证

- 18 项测试通过，覆盖失败立即禁用、成功等待 investigation Run、空窗口/下游超时禁用、多 run fail-closed、running 延长观察。
- `py_compile`、`git diff --check` 通过。
- 没有恢复、重发、Provider 调用、发布或负租户写入；230 L0 继续挂起，不 push。
