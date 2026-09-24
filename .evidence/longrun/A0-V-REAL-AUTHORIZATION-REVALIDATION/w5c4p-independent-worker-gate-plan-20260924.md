# W5c4p 独立 snapshot worker 启用前门禁方案（2026-09-24）

W5c4o `df3d3ca8` 新定义 rev2 disabled。初步只读检查：Host PID17302 存活，但 18181 **没有监听者**；不能 enable。旧独立 worker 启动器 `scripts/a0v_snapshot_product_api.py` 只应在独立 API 进程运行，保持 Host 不重启。

1. 只读核独立 worker 旧状态/锁/PID、端口和 8080 配置，确认无残留未知 worker/活动 attempt；核 12 schedule off、definition rev2 与新窗口/预算覆盖下次 slot。
2. 若无旧活实例、启动器/配置/签名身份精确且 Host 不受影响，以原启动器在 18181 恢复唯一独立 worker；只读观察 status=IDLE/alive/topology=independent、同租户、hostInThisProcess=false、8080/Host 不变。未知进程/锁/启动结果即停，不能起第二个。
3. 只做进程门禁，不 enable/手工 Run/读商城源行。验证落盘提交后，再独立 W5c4q 启用门禁与正式请求。

## 16:30 CST 预检补充（写代码前）

18181 无监听；旧 `replacement-bl/snapshot-worker/status.json` 最后于 9 月 20 日记录 STOPPED/PID63195，旧 `A0V-BL-SNAPSHOT-WORKER-20260920` task 已完成且不在当前 leases；原启动器硬编码旧 task，因此不能直接 `serve`，也不能借其他过期 lease。先通过仓库 `scripts/memory/memory-receipt task-start` 在共享记忆正式取得全新、精确 `local-process/aos-api-18181` 的 m1 lease（project revision 以实时 authority 为准），不复活旧 task；随后最小修改 `scripts/a0v_snapshot_product_api.py` 将常量改为该新 task ID，并要求 lease scope 精确包含该端口。定向测试旧 task/错误 scope/过期/第二实例拒绝。新 lease 仅是进程所有权，不是源读取或业务执行批准；本波仍保持定义 disabled。
