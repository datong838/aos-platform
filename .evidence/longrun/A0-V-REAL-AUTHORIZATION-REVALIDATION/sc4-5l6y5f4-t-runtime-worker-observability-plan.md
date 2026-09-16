# SC4-5L6Y5F4 T：Runtime Host 业务 worker 可观测性方案

## 问题

自然 P02 已成功并产生可发现 candidate，但独立 Host 未产生 occurrence。现有 status 只写静态 `businessWorkers` 名称，无法区分 process-owned live target 为空、candidate 未发现或消费失败。

## 最小设计

1. ProductEvent worker 保存最近一次 tick 的安全计数：targetsChecked、candidates、occurrences、analysesAccepted、failed；不保存业务载荷或异常文本。
2. 独立 Host 每 2 秒把 live target 的租户、installation、generation 和 worker 最近计数写入既有 status 文件；目标来自同一进程的 `LivePreparedJobDirectory`，不从外部投影猜测。
3. reporter 与 Host/业务 worker 同生命周期；异常必须使 Host fail-closed。停止时保留最后状态并标记 stopped。
4. 定向测试后受控重载 Host，读取真实 status 再决定装配修复；本波不启用 schedule、不调用 worker tick、不创建新业务 run。

## 文件

- `services/aos-api/aos_api/ecommerce_product_event_worker.py`
- `scripts/a0v_ecommerce_runtime_host.py`
- 对应两组 extension_runtime 测试与本波证据。
