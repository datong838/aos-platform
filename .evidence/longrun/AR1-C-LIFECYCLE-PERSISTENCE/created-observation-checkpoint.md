# AR1-c 实际创建观察检查点

2026-09-06，m1；AR1-c 继续，业务新增0。

ResourceJournal.record_created 记录实际OCI容器ID，锁序安装→操作→资源，核对已领取/未释放、owner/context，同ID重放不增加事件，异ID拒绝，记录/事件/outbox原子回滚。journaled_session 创建后立即登记；登记失败仍清理、不启动会话，不更改ready/active。

专项PG反证RED→GREEN。真实签名OCI测试回读64位实际ID；真实创建后注入登记失败，账本released且独立docker inspect确认该容器不存在。正常签名测试也独立确认容器不存在。

累计361 passed、6 warnings、47.98秒、exit0；补独立inspect断言后对应真实专项2项再次通过。现有JDBC退出日志提示仍保留。Prime只读复核无实质缺陷并建议补独立inspect，已采纳。

无页面修改，浏览器不适用；不代表安装active、业务ports、完整AR1-c。下一项继续准备阶段与最终Installation事实提交衔接。
