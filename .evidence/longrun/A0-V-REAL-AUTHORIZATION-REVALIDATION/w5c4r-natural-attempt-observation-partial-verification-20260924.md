# W5c4r 自然 attempt 观察中（2026-09-24，非终态）

方案 `b912b897`。`scripts/a0v_w5c4r_observe_natural_attempt.py` 已通过 `py_compile`，08:51 UTC 首次只读采样 `WAITING_FOR_NATURAL_TERMINAL`：目标定义仍 rev3 enabled、12 schedule on、唯一 worker/Host/三 held/九路与 claim gate 稳定，目标 group claim0、第三继任者 attempt0、canary0；正式自然 slot 是 20:00 UTC。完整采样只在仓库外 0600 `../.aos-recovery-20260920/state/q-advisor-baseline/20260924-w5c4r-natural-observation/samples.jsonl`。

已启动唯一 50 秒只读循环；**本波未完成，不能作为业务成功**。循环在唯一 attempt 正式终态或身份漂移时收笔，未知结果不重发，不调用 `run_definition`。终态到来后还需另写最终 verification、独立核 Run/Store/投影及风险，提交后才进入下一波。

## 09:03 UTC 观察器修正（仍非终态）

按已提交方案修订 `9a6de475`，先停止旧的**只读**观察循环，保留独立 18181 worker 与 enabled 定义。观察器现在接受合法 `IDLE/RUNNING`，仍严格核唯一 18181 listener PID、存活、独立拓扑、无本进程 Host/错误及 10 秒内状态；异常写入私有 `FROZEN_OBSERVER_ERROR`，避免到点时无痕退出。新增四项状态测试（`IDLE/RUNNING` 接受、`STOPPING/STOPPED` 拒绝）全通过；09:03 UTC 独立单次采样仍为 `WAITING_FOR_NATURAL_TERMINAL`、claim0/attempt0。接下来只重启**一个** 50 秒只读循环，不触发业务请求。

## 09:08 UTC 缺失 attempt 有界修正（仍非终态）

方案修订 `de02a1b5` 先行；再次仅暂停只读观察器，新增从已冻结 `nextSlotUtc` 计算的 slot+30 分钟无 attempt 冻结条件，已有唯一 attempt 不受此上限影响。五项观察器测试全通过，09:08 UTC 单次实测仍 `WAITING_FOR_NATURAL_TERMINAL`、claim0/attempt0。将恢复唯一 50 秒循环；自然调度、worker、Host、业务对象均未写入。
