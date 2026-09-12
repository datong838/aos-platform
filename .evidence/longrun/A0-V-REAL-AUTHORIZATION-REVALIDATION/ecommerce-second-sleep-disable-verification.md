# 第二次休眠后正式禁用验证

2026-09-12，实现 00b4180f，原 Host v13 基线 b8b38137。新增 sleep-recovery 精确目标入口，旧默认和 config-recovery 文件/幂等命名空间不变，双目标拒绝。RED 1 failed/11 passed，修复后相关 34 passed，包括真实隔离 PostgreSQL 禁用目标和消费者测试。

12:54:12.260818Z 通过原 RuntimeDisableService、实际 Membership/CurrentControlPermission 提交唯一命令，installation a0fd8e25-cb6f-49e5-aa77-7faddae12099，etag 5，generation 49427eeb-e9f8-42d5-8588-108e90110beb，bindingRevision 5。Operation 76e09779-9bd2-4947-b29b-ff8224c52a35。命令冻结于仓库外 state/ecommerce-1.7-sleep-recovered-disable-command.json，未换键重发。

12:54:13.993926Z 原 Host 正常推进 accepted → fencing → draining → committing → disabled_committed → succeeded。只读回查 operation succeeded@6，binding unknown/desired disabled/enabled false/fence true@7，executionEpoch 5。已过期三资源此前确认 released/observed_release=true；disabled_committed 中 resourcesRetained=true 表示该控制命令不额外销毁资源，并不代表容器重新存在。完整事件见 ecommerce-second-sleep-disable-readback.json。

本波完成的是明确禁用状态和恢复前置，未卸载，未创建后继安装，未修改源审批、管道、业务数据或调用 Provider。旧 API 进程不变。Niushop 1.4 新构建资格通过但尚未正式发布安装；真实自然首链及八工作台业务场景仍未完成。230 L0 挂起，不 push。

下一波先比较新构建与既有已发布同版本包的文件和依赖锁，确定不可变新组合；同时核查旧实例无调度、无未决调用、正常卸载权限。通过正式 Registry/Installation Owner 完成恢复，不覆盖旧版本、不直接改状态、不以 Host 进程存活替代业务容器和首链。
