# AR1-c 准备消息与有界宿主检查点

2026-09-06；基线m1@d8766f4c/AOS-000541，主Lease继续。

PreparationConsumer固定scope/installation，复用原worker.start和持久outbox；单宿主最多一个job，不无界注册、不自动换代。原start返回即登记job，内部取消仍等登记收敛。accepted且没有job才start，旧terminal只确认事件，未完成中间态或已有job不重建。stop拒绝新接纳、等待消费、再原job.stop；原消费错误不能跳过清理，清理不确定保留传播，重复stop复用关闭任务。

初始7Red→7passed7.84s；补关闭顺序/失败清理2项及scope/install/op错配清理3项共12专项。实际签名Registry/Installation/真实专用OCI链的准备改为消费者入口，实际准备提交后ACK SQL回滚，原host保留同job/container/resource；过期重投禁止start，新host只确认历史终态且job仍None，原job健康仍通过；随后原verify/enable/disable消费和host.stop清理，联合10passed18.50s。最终累计876passed、6既有warnings、125.57s、exit0。git diff --check通过；既有JDBC退出日志流错误不影响exit0。

Prime初审与最终差异复审均无新增实质问题；无页面改动，不称新浏览器功能验收。仅隔离18432临时schema及专用OCI，无共享迁移/真实业务写/Provider/费用/发布。新业务场景0，原活跃IPC不由新进程接管，正式全租户调度未完成。

下一段：配置持久消费者，先独立提交fence再排空/提交配置，替换实际联合里直接推进的测试接线；随后正式引用/broker/预算和完整卸载重装。
