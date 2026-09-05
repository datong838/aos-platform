# AR1-c 签名 Registry / OCI / Installation 联合检查点

2026-09-06；基线068c4bb7，AR1-c仍进行中，业务场景新增0。

临时签名测试包经真实RegistryService创建、验证、发布；真实SnapshotReader、resolver、CompositionStore形成immutable lock；真实InstallationService提交/分离审批、RuntimeLifecycleService接纳、资源意图、真实签名OCI注册、commit_prepared提交applied、真实旧verify按runtime专用原因拒绝，最后退出清理并独立inspect确认容器不存在。第二用例在实际注册后通过RegistryService撤销发布资格，最终提交拒绝、安装approved与操作preparing保留且资源确实释放；reached断言排除撤销动作自身失败形成假阳性。

夹具修正LoadedBundle制品ref、签名名称、当前测试时钟和resolved contributions。临时schema内仅补aos_runtime对四张全局模板表的SELECT，以重现隔离控制读取，不授予Registry写权限；所有schema在finally移除。未迁移或修改共享库及业务实例，没有公共Provider或公开发布动作。

累计389 passed、6既有warnings、64.94秒、exit0。其后仅加强旧verify异常原因断言，联合专项再跑2 passed、13.16秒；既有JDBC退出日志提示保留。默认引擎未切换，专用引擎只余aos-ar1c-pg。Prime只读审查未发现实质缺陷，建议的异常链断言已加强并实测。

边界：这是隔离运行制品的完整准备联合证据，不是业务场景；当前权限检查仍测试宿主True，非正式权限服务。无active/enabled binding、无业务ports，context退出会释放容器；下一项持久准备worker、健康verify、正式策略/broker及完整生命周期仍须开发。无页面/API变化，浏览器不适用。
