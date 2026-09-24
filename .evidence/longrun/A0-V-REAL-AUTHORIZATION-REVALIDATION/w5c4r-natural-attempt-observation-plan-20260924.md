# W5c4r 自然 attempt 50 秒只读观察方案（2026-09-24）

W5c4q `4ad6643f` 定义 rev3 enabled、12 schedule on，下一官方时区 slot 是 2026-09-24 20:00 UTC。唯一 18181 worker PID37241、Host PID17302。**不手工 `run_definition`，不读取商城源行。**

1. 立即启动单一只读观察循环，固定 50 秒间隔：官方 definition/worker/Host/三 held、九路与 claim gate、目标定义 group claim/12 Run、第三继任者 attempt 的 ID/state/revision/错误分类、Store Receipt/projection/canary，以及预算/控制剩余期。私有 0600 逐次落非源行观测；任何身份漂移、第二 worker/attempt、未知提交边界立即冻结，并停止宣称自然成功。
2. 20:00 UTC 前仅显示等待与健康，不触发业务；到点后同一轮持续采样到**唯一 attempt 的正式终态**，然后核 12 Run、Store/投影、Release/Receipt 等正式结果。只认原 Owner 状态及独立 DB 回读，不能凭 HTTP 200 或 worker `IDLE` 判成功。
3. 若出现 `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED` 且十二 Run 仍 running、Store Receipt/ecom_link/projection pending 全0，则走既定 1800 秒有界 saved-snapshot 路径；任何失败/unknown 不手工重发，在本波 verification 中冻结边界，再正式退休/direct successor。
4. 观察终态、verification/commit 后自动进入下一波。观察进程本身不授权副作用；失去观察进程不改变已有定义的自然控制，恢复时先只读按原 group/attempt 认领，不发第二次请求。
