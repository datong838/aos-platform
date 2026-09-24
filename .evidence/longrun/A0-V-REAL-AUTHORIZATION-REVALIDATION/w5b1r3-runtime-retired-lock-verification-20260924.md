# W5b1R3 最小特权退休锁与旧 enable 正式退休验证（2026-09-24）

## 结论

**GREEN，只限旧 DS enable 的正式取消与退休。** 原 enable operation `1d5b0071-3067-456f-8ab5-ee1f666abd83` 已 `cancelled`；本波唯一 disable operation `245d3953-44e8-4ec8-9fea-7dc178408c2c` 已 `succeeded`，其 6 条 outbox 事件全部 delivered。安装 `c6812824-a0c3-4adc-9ebc-d56178ae135c` 的 binding rev13/epoch7 为 disabled/fenced，配置仍 rev2；12 schedules disabled，active attempts=0，canary bindings=0，旧定义 disabled，新定义不存在，3 个资源继续 released。没有商城源读取、provider call、业务 Run 或重新使能。

## 方案步骤与证据

1. 继 W5b1R2 `663851c1` 的原请求同事务回滚，新键/新私有目录不复用。独立 18434 测试容器恢复后复现 `FOR UPDATE` 权限拒绝。代码采用 `a0v_092` 窄权限 SECURITY DEFINER 行锁：必须为带有效租户的非特权 runtime 成员，且是同事务 `running/fencing` 的精确 disable、同安装/代际、精确恢复 activation/group；锁住 runtime/activation/binding/9 dispatch 行，基表 UPDATE 未开放。Python 退休谓词继续完整读取 9/9 legacy/fenced、无关联、无 gate、历史 detached、无未终态 attempt，多个 matched 不走捷径。
2. 18434 专用库：退休/分发/配置回归 37 passed；完整 cutover opt-in 回归 66 passed、1 skipped。新增权限测试证明 `aos_runtime` 对 activation 基表 `UPDATE=false`、没有精确 fencing disable 时函数拒绝、非 runtime 角色执行被拒。`git diff --check` 通过。
3. 主库 `aos_meta_head` 从 `a0v_091` 一次迁移到 `a0v_092`，私有 migration intent/result 均 0600；独立 audit：函数仅授 runtime 执行，maintainer 无执行权限，runtime 基表 UPDATE=false。8080 原 launchd 服务重启后 `/openapi.json` HTTP 200。
4. W5b1R3 新键 `a0v-w5b1r3-retire-unconsumed-enable-20260924-v1` 前预检旧 enable accepted/expired/claim0/attempt0、binding rev11/epoch6 disabled/fenced、12 schedules off、active attempts/canary 0。精确请求一次返回 `replayed=false`、新 operation `245d3953-44e8-4ec8-9fea-7dc178408c2c`；精确消费一次返回 `succeeded`/`acknowledged`；独立 audit 为 `W5B1R_ENABLE_RETIRED_GREEN`，旧 enable cancelled，新 disable succeeded，deliveredEvents=6。

## 一致性与后续边界

符合计划 `531b288e` 的最小权限、串行新键、先测试后主库、正式终态要求。W5b1R2 仍是失败历史，不重发；本波仅关闭悬置 enable，不等于 DS live successor 已可运行。下一波先方案：核查 released DS 的 PreparedJob/安装资源与 12 个当前 selection 的真实约束，再决定新 live successor 路径；保持定义 disabled、调度关闭，不手工 `run_definition`。
