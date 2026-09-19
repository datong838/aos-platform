# AO qcursor 有界重载与自然后继 attempt 方案

## 目标与现状

AO `recoverable_store` attempt `67c2331d-b73f-4863-b881-0d67e6c55508` 由合并 API/Snapshot Worker 进程持有。它持续续租超过两小时，但十二个 Run、十二个 Dataset Receipt 和一个 1168 铭接命令之后的 Store Receipt、`ecom_link`、Outbox 与 retirement 均为零。当前运行进程加载于有界执行修复之前，不能依靠新代码自行停止。

本波仅重载 `com.aos.qcursor-worker-u`。独立 Runtime Host `com.aos.a0v-runtime-u`、8434 Web、AO installation/generation、definition/recovery、冻结输入和原 Store 幂等键保持不变。禁止手工 `run_definition`、源数据重读、未知结果重发、创建 installation 或变更路由。

## 文件级清单

1. `scripts/a0v_ao_attempt_guard.py`
   - 从 AO 固定 installation/generation/operation key 读取完整 attempt 链及最新 attempt；
   - 只接受原 attempt 单独运行，或原 attempt 以 `ATTEMPT_LEASE_EXPIRED` abandoned 后出现一个同 request hash、同 operation key、ordinal-2 key 的直接后继；
   - 将 abandoned 等待窗口、后继运行、后继成功和后继失败分别路由为只读结果。
2. `scripts/a0v_ao_saved_snapshot_recovery.py`
   - 终态验收允许且仅允许上述两段 attempt 链；最终必须恰有一个 succeeded、一个 expired-abandoned、无其他 attempt；
   - 保持原 Store Receipt、1168 links/outbox、零 projection pending、九路由、三资源和 dev-org 零 canary 门禁。
3. `scripts/a0v_ao_continuation_router.py`
   - 增加等待正式 Lease 回收和观察自然后继的确定性只读路由；闭包只接受新的两段链终态。
4. `services/aos-api/tests/extension_runtime/test_a0v_ao_attempt_guard.py`、`test_a0v_ao_saved_snapshot_recovery.py`、`test_a0v_ao_continuation_router.py`
   - 覆盖原 attempt、abandoned 空窗、合法 ordinal-2、伪造 request/key/第三 attempt、终态闭包与纯 SELECT 边界。

## 运行步骤与停止条件

1. 提交方案、守卫和测试；专项与累计纯回归通过后才重载。
2. 只对 `gui/501/com.aos.qcursor-worker-u` 执行原 LaunchAgent kickstart；记录前后 PID，确认 Runtime Host PID 不变。
3. 只读观察旧 attempt 停止续租并由 Runtime Host 正式 abandoned。若旧 attempt 出现任何 Store 进展或成功，停止后继判断，转既有 inspect/disable。
4. 由自然 Worker 领取 ordinal-2；核对 request hash、operation key、原幂等键族、十二 Run、Receipt 与租户边界。不得手工触发或补发。
5. 新 attempt 由加载后的 300 秒绝对上限约束。成功则 inspect/disable；失败则冻结终态并进入正式 retirement/direct-successor。出现第三 attempt、request 漂移、Store 未知部分提交、canary 非零或 Runtime Host 变化时立即停止写动作，仅做对账。

## 完成条件

AO 必须形成可验证的两段 attempt 链并到达成功或明确失败终态；服务健康与测试通过本身不算经营闭环完成。成功后还需完成 saved recovery disable、浏览器拒绝态复验、证据和提交，然后进入经营参谋 Policy v3 自然首链。
