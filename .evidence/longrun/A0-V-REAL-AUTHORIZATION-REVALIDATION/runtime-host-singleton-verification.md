# UQ6-D1 宿主启动单写者检查

基线80dddbea，方案先行。scripts/a0v_ecommerce_runtime_host.py使用固定canonical锁、两个已知旧状态锁与本次状态锁；所有锁持有到serve结束，冲突只输出拒绝、不覆盖原状态。原运行6606尚未重启。

38项启动器和RuntimeHost停止/生命周期测试通过，7项既有警告；git diff --check通过。兼容当前旧runtime-host-aa3010c4.lock，避免修改源码后启动新版本绕过仍运行旧版本。此为本地固定部署配置，不主张跨机器分布式排他；数据库租户分配与Lease约束继续生效。

下一步实际持锁拒绝验证。拒绝探针使用interval=0，若原锁意外缺失也会在Host构造前停止；成功标准必须HOST_ALREADY_RUNNING且原状态摘要不变、探针状态文件不存在。
