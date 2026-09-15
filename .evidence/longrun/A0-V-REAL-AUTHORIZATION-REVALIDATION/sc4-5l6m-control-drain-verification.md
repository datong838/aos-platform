# SC4-5l6m 同步控制事务排空验证

Rules：m1 单写、先方案、隔离 PG、证据提交；不 push、主库不变、230 L0 挂起。

方案 b1206f7e，Task Receipt SC4-5L6M-CONTROL-DRAIN-20260916。

使用原 a0v_028+a0v_044 安装组锁函数，实际 aos_runtime 连接保持十项组锁；另一 maintainer 连接调用原 fence SQL。100ms lock_timeout 产生明确 LockNotAvailable，fence Receipt 数量 0，控制行仍未 fence。释放旧事务后同请求成功，Receipt 数量恰为 1。没有线程调度或固定 sleep 猜测结果。

聚焦两个 event_control_dispatch_lifecycle 测试文件：16 passed，7 既有警告，1.86 秒，退出 0；退出时既有 JDBC closed-file 日志异常不计为产品验证。只修改测试。

边界：证明同步 Host 的组锁互斥及超时无写后重试；没有证明整个 Service、异步 generation/occurrence drain、真实安装退役或业务八工作台完成。下一步仍需分别闭合。
