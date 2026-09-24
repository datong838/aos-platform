# W5c4r 自然 attempt 50 秒只读观察方案（2026-09-24）

W5c4q `4ad6643f` 定义 rev3 enabled、12 schedule on，下一官方时区 slot 是 2026-09-24 20:00 UTC。唯一 18181 worker PID37241、Host PID17302。**不手工 `run_definition`，不读取商城源行。**

1. 立即启动单一只读观察循环，固定 50 秒间隔：官方 definition/worker/Host/三 held、九路与 claim gate、目标定义 group claim/12 Run、第三继任者 attempt 的 ID/state/revision/错误分类、Store Receipt/projection/canary，以及预算/控制剩余期。私有 0600 逐次落非源行观测；任何身份漂移、第二 worker/attempt、未知提交边界立即冻结，并停止宣称自然成功。
2. 20:00 UTC 前仅显示等待与健康，不触发业务；到点后同一轮持续采样到**唯一 attempt 的正式终态**，然后核 12 Run、Store/投影、Release/Receipt 等正式结果。只认原 Owner 状态及独立 DB 回读，不能凭 HTTP 200 或 worker `IDLE` 判成功。
3. 若出现 `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED` 且十二 Run 仍 running、Store Receipt/ecom_link/projection pending 全0，则走既定 1800 秒有界 saved-snapshot 路径；任何失败/unknown 不手工重发，在本波 verification 中冻结边界，再正式退休/direct successor。
4. 观察终态、verification/commit 后自动进入下一波。观察进程本身不授权副作用；失去观察进程不改变已有定义的自然控制，恢复时先只读按原 group/attempt 认领，不发第二次请求。

## 08:57 UTC 观察器预防性修订（业务未到点）

`W5c4q._worker()` 专用于启用前门禁，要求状态恰为 `IDLE`；自然执行时 worker 会合法进入 `RUNNING`，不能复用它作为 W5c4r 健康判据。W5c4r 应自行只读允许 `IDLE/RUNNING`，仍要求唯一 PID、alive、independent、无本进程 Host、无 error、status 新鲜；`STOPPING/STOPPED` 或异常需以 `FROZEN_OBSERVER_ERROR` 私有落盘并退出，不让进程无痕崩溃。修正后在尚无 claim/attempt 时重新采样验证，再继续唯一观察循环；不得启动第二观察器与正式业务请求。

## 09:07 UTC 无 attempt 有界观察补充

使用已冻结的启用意图 `nextSlotUtc` 作为唯一时钟锚点。若 slot 后 30 分钟仍无本 generation 的 attempt，即使有 group claim 也以 `FROZEN_NO_ATTEMPT_AFTER_SLOT` 停止观察，不推断业务成功、不补发、不手工触发；先独立只读对账 claim/Run/worker/Receipt，再按正式退休与 direct successor 路径处理。只要已出现唯一 attempt，仍按原规则观察至正式终态。该边界是 fail-closed 上限，不改变自然触发和运行时控制。
