# 待核算 Store PostgreSQL 集成证据

基线 84359d26。复用随机测试 schema、非 superuser/non-bypass RLS 的 aos_runtime。fixture 使用当前审批窗口，并显式放置开发未核价 payload；不代表正式 Model Store 已允许发布该 payload。

首次真实集成在事件写入失败：aip_budget_reservation_event_to_state_check 未支持新状态。已同步 from/to_state CHECK，降级禁止遗留 pending 事件历史，防止历史状态被抹去。另补 _view 中 cost_pending→completed 的 Invocation 对账映射。第二次在负租户断言类型失败，实际正确返回 BudgetReservationNotFound，测试修正为精确预期。

最终 2 passed：完整 reserve/submit/usage/complete/replay 场景与 SQL guard 场景。错误 result hash 触发回滚且 Provider Receipt 数量为 0；成功后 amount=null、Invocation completed、Provider Receipt 恰好 1、重放 ref 不变、settled bucket 金额未增加；dev-org 隔离读取不存在。临时 schema 已清理，public 未升级，未发起真实 Provider 调用。

尚未完成 active deferred Model 发布、Host 选择该结算路径、开发额度不阻塞和后核价；不能据此声称 A0-V 或首链完成。下一步完成这些联合运行前置，再进行真实首链。
