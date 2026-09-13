# 切换消费端当前审批重验

基线 6c0b3781。规则：m1 单写者，不 push，230 L0 挂起；当前实现先方案再代码。真正配置 FirstDispatchRegistrationService 的生产切换 Store 必须重验内部内容绑定、可执行 R2/R3 策略、完整独立审批人数，以及发起人和各审批人的当前安装权限、marking、ActionType。每个消费阶段继续原 exact Proposal/Approval/期限/CAS 校验，新增门不能代替这些校验。

文件：services/aos-api/aos_api/ecommerce_growth_cutover.py 接消费点；新增 ecommerce_growth_cutover_current_approval.py 实现当前事务内重验；tests/extension_runtime/ 对应审批消费测试及 control PG 回归。不创建新的审批权威表，不直接授角色、不修改已存在审批/Receipt。

事务内先 maintainer 读取已核对原 Proposal 的全部 approved 事件，再切 runtime 复用 require_internal_cutover_binding：发起 APPLY、每位独立审批人 APPROVE。审批必须非空期限未过、同 proposal hash/binding、非 maker、不同 actor；有效独立人数满足至少 R2=1/R3=2 且满足策略值。拒绝 draftOnly/R4/缺策略/hash漂移。返回 maintainer 后继续原协议。失败交由原事务回滚，不隐式重试。

历史无 registration service 的 Store 测试仍验证旧协议，不代表当前产品授权。现有 control PG 用例使用历史简化审批 fixture，可在测试中替换新增当前门以专注原权限/phase职责；必须新增真实调用新门的隔离 PG 负例，证明旧 fixture 无法通过当前生产组合。主库真实审批、正式 ActionType 发布与切换仍须后续完整验收。
