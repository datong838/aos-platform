# AR1-c 持久隔离会话内部检查点

2026-09-06，m1。AR1-c仍进行中，业务场景新增0，无运行启用或发布权。

固定SDK --serve入口实现同一容器注册后连续调用；只接受已声明API operation，业务ports全部拒绝。原一次性注册保持原行为。会话有帧、深度、请求数、注册与调用超时、stderr上限，失败后永久关闭。

真实专用OCI实测：连续两次调用、非法结果、调用取消、连续两次取消、闲置stderr超限；在调用方捕获异常且尚未退出上下文时容器已回收。未知创建与删除失败保留结构化资源引用。

Prime只读增量复核发现并修复：异常被调用方捕获导致延迟回收、闲置stderr未监控、创建/删除双错丢引用、重复取消抢在清理前、通信收尾再次取消掩盖清理未决。最后组合反证先RED，屏蔽通信收尾追加取消后GREEN；复核未发现新增问题。

最终累计318 passed、6已有warnings、38.15秒、exit0。命令与signed-reader/query检查点相同：精确extension_runtime目录及列明的asset_registry单测，显式开启专用OCI和PG。既有JDBC退出日志closed stream仍存在，不宣称零告警。git diff --check通过。

变更：SDK runner.py/session.py；extension_runtime oci_driver.py/session_supervisor.py；test_oci_driver.py、test_sdk_session.py、test_persistent_supervisor.py、test_session_cleanup.py。未改页面，浏览器不适用。

下一切片：持久资源账本与会话回收接线，再闭合权限/epoch/审计、schema、最终Installation CAS。未完成AR1-c，未进入AR1-d；持久会话不是正式安装或业务能力已启用的证据。
