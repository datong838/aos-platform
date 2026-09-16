# SC4-5L6Y5F4 S：Policy9 自然终态观察方案

## 目标

在已装备的唯一 `01:00 Asia/Shanghai` Cron 窗口中，只读等待 P02 正式运行终态，并在出现唯一 succeeded/failed 终态后立即禁用 schedule。不得人工运行、补跑或把中间态视为结果。

## 控制

1. 复用 `a0v_l_natural_product_event2.py` 的精确 Policy9/L generation 快照与既有 disarm；不新增业务 API。
2. 每 5 秒读取一次权威数据库快照。窗口内 run 必须为 0 或 1；超过 1 条立即失败关闭，不做任何重发。
3. 唯一 run 为 failed 时立即禁用。run 为 succeeded 时，保持 schedule enabled 让 15 秒 ProductEvent worker 完成 discovery/origin 回查；观察到 investigation Run 后立即禁用。Cron 槽位已有数据库唯一键，不会在同一小时重复领取。
4. 01:10 前仍无 run，或 succeeded 后仍无 investigation Run，则禁用并返回对应 timeout；若 run 仍 running，则保持当前 schedule 状态再等待该 run 最多 10 分钟，终态后按前述规则处理。未知终态或第二阶段超时仅禁用并返回失败，不触发恢复。
5. 观察内容固定为 run、ingress、occurrence、attempt、investigation Run、inflight/unresolved、负租户 dispatch；不输出凭据或源业务行。

## 变更与验证

- 修改 `scripts/a0v_l_natural_product_event2.py`：增加 `watch` 命令。
- 修改 `services/aos-api/tests/extension_runtime/test_l_natural_product_event2.py`：覆盖失败立即禁用、成功等待 investigation Run、无 run/下游超时禁用、多 run fail-closed、running 延长观察。
- 退出后落 final JSON、验证文档并提交；若失败，下一波按安全错误码和持久化阶段诊断。

## 运行中诊断与处置（2026-09-17 01:03 +08:00）

- Cron 已自然成功：65 rows、1 ingress，SSH tunnel ready；权威 runtime 身份可读到唯一 discovery candidate，actor membership 唯一且合法。
- 外部 Runtime Host PID 87185 启动于 22:14，早于本轮 L/Policy9 消费代码部署，且在候选出现后的多次 15 秒 tick 中仍未生成 occurrence。Python 进程不会热加载已更新模块。
- 处置固定为优雅停止旧 Host，再以相同 bundle root、trust roots、credentials 和 interval 启动当前代码；不调用 worker `tick()`，不创建新 schedule run，不重写原 ingress。新常驻 worker 对数据库中同一 candidate 的自然轮询仍受原 Receipt、租户和幂等约束。
