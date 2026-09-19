# AQ 自然 attempt 与严格 Store 终态守护方案

## 上位权威

AQ preparation 已由 commit `71bb2ae2` 固化：installation `d6839bf3-55b5-474c-aa21-49966e15db3d`、generation `b31be2a7-36fd-4348-9ff8-10939cc3d1cd`、九路由 revision102/group129、definition revision65 enabled、recovery revision21。执行前事实为 attempts=0、12 Run running、12 Dataset Receipt、3 live resources、canary=0。

Runtime Host PID 87894 启动于 strict Store 修复 `b287ccbb` 之后。唯一外部调度通道为 qcursor LaunchAgent；禁止手工 `run_definition`。

## 文件级清单

1. `scripts/a0v_aq_attempt_guard.py`
   - 在 qcursor 产生唯一自然 attempt 后冻结 attemptId；
   - 只读 heartbeat、Lease、definition/recovery、12 Run、Dataset Receipt、relationship/link command、Store Receipt、live link/outbox/projection、routes/resources/canary；
   - running 仅观察；succeeded 必须满足完整 Store/Run 闭环；failed/abandoned 仅路由诊断，绝不重发。
2. `services/aos-api/tests/extension_runtime/test_a0v_aq_attempt_guard.py`
   - 锁定身份漂移、心跳健康/陈旧、严格成功、失败边界和 select-only 合同。
3. `aq-natural-attempt-verification-20260919.md`
   - 记录自然领取、运行轨迹、终态、浏览器、测试和下一波。

## 执行与停止规则

启动唯一 qcursor，等待自然领取；看到首个 attempt 后先冻结只读 guard，再继续观察。running 且 heartbeat/Lease 健康时不改变运行态；超过 300 秒且 Store 无进展时只诊断。succeeded 后才执行 AQ saved recovery `inspect/disable`。failed 或 unknown 时不得重发，先界定提交边界并关闭 definition；出现第二 attempt、租户污染、路由或哈希漂移立即 fail closed。

成功退出条件是：唯一 attempt succeeded，12 Run succeeded/stopped，1 retirement、1 Store Receipt、1168 links、1168 outbox、projection pending=0、resources/routes/canary保持预期，并完成 definition disable、浏览器复验、证据、测试与提交。
