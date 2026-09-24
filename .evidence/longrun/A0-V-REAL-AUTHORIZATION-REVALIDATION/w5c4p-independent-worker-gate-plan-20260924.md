# W5c4p 独立 snapshot worker 启用前门禁方案（2026-09-24）

W5c4o `df3d3ca8` 新定义 rev2 disabled。初步只读检查：Host PID17302 存活，但 18181 **没有监听者**；不能 enable。旧独立 worker 启动器 `scripts/a0v_snapshot_product_api.py` 只应在独立 API 进程运行，保持 Host 不重启。

1. 只读核独立 worker 旧状态/锁/PID、端口和 8080 配置，确认无残留未知 worker/活动 attempt；核 12 schedule off、definition rev2 与新窗口/预算覆盖下次 slot。
2. 若无旧活实例、启动器/配置/签名身份精确且 Host 不受影响，以原启动器在 18181 恢复唯一独立 worker；只读观察 status=IDLE/alive/topology=independent、同租户、hostInThisProcess=false、8080/Host 不变。未知进程/锁/启动结果即停，不能起第二个。
3. 只做进程门禁，不 enable/手工 Run/读商城源行。验证落盘提交后，再独立 W5c4q 启用门禁与正式请求。
