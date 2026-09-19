# Recoverable Store Attempt 有界寿命验证（2026-09-19）

## 完成结果

`RecoverableStoreAttemptOwner` 现在固定默认 300 秒最大执行寿命，并拒绝小于等于 heartbeat 周期、超过 300 秒或非有限值。attempt 从进入上下文时开始使用 monotonic 绝对 deadline；等待 heartbeat 前后均检查截止时间，避免在边界上多续一次 Lease。到期设置原 `INGRESS_DEADLINE_EXCEEDED`、停止 heartbeat，并令组合 cancellation 可见。

上下文按期退出时仍由原 Owner 结算。若业务调用阻塞且不响应 cancellation，本实现不强杀线程、不虚写 failed；heartbeat 停止后 Lease 到期，由既有 `abandon_expired_reads` 记录 `abandoned / ATTEMPT_LEASE_EXPIRED`。后续只可沿原 request hash、operation key 与 Store 幂等身份恢复，未知结果不得换键重发。

## 测试与检查

- `test_recoverable_store_attempt.py`：11 passed。覆盖组合取消、固定错误归类、unsafe 类型脱敏、新 heartbeat deadline 归类和寿命参数边界。
- `test_generation_attempts_pg.py` 定向隔离 PostgreSQL：3 passed。覆盖绝对寿命停止、正常 heartbeat 跨 fence 后成功结算、调用方 deadline 固定失败原因。
- AO 守卫、Continuation Router 与 attempt 纯单元累计：56 passed。
- Python 编译与 `git diff --check` 通过。
- AR2 `--phase ar2-7`：1988 扫描、200 分类、93 迁移；hash、正反向依赖、跨层与动态引用错误全空。
- 浏览器沿本轮既有只读会话复核：`127.0.0.1:8434/ontology` 页面可达，本体对象与健康入口可读；当前身份下电商工作台保持“暂无可见工作台入口”。本波未重载服务，没有可见性或租户权限变化。

## 当前 AO 与限制

本波末只读观测为 attempt revision 233、elapsed 7027 秒、control 尚余 14541 秒；心跳/Lease 仍新鲜，十二 Run 与原 Dataset/关系/链接命令事实不变，Retirement、链接 Store Receipt、`ecom_link` 和链接 Outbox 均为零，三资源有效，canary=0。分类仍为 `RUNNING_HEARTBEAT_ONLY_DIAGNOSE`。

该旧 attempt 由未加载新代码的 Host 持有，所以不会自动获得 300 秒寿命。若直接重载 Host，原心跳会停止，但阻塞中的未知 Store 调用边界必须先保留；新 Host 的 attempt recovery 只能在 Lease 明确过期后记录 abandoned。不能在旧 Lease 新鲜时启动保存恢复，也不能手工 `run_definition`。

## 下一波

进入旧 Host 安全重载与 AO 失联回收：先确认唯一 Host PID、singleton、当前线程/会话、最新 attempt 与 Store 零事实；形成停止判据和回滚方案；受控停止旧 Host，等待 Lease 明确过期并由正式 recovery Owner 记录 abandoned，再用已提交新代码启动唯一 Host。此后只允许自然 Worker 读取原 Recovery Receipt 与原 Store 幂等键恢复。若停止前 AO 终结，则取消重载处置并改走 succeeded inspect/disable 或 failed 边界流程。
