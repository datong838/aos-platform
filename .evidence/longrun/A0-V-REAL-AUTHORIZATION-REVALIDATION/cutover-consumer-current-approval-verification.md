# 切换消费端当前审批重验结果

基线 6c0b3781，按 cutover-consumer-current-approval-plan.md 实施。生产组合（具有 FirstDispatchRegistrationService）在原 exact 审批核对后新增重验；无服务的历史协议 Store 不作为当前产品授权路径。

- 新增内部内容 hash、风险/策略 hash、执行许可、独立审批人数、审批期限、maker/checker 分离检查。
- 使用同一事务，以维护角色读取不可变审批事件，以运行角色复用当前安装/角色/marking/ActionType 校验，再回到维护角色；不新增授权，不扩大账本权限。
- 初始 RED：12 failed（缺模块）。最终消费门、真实 PG 读取/拒绝、control phases、first-registration、历史回读联合 46 passed，7 条现有依赖警告。
- 一次测试配置遗漏专用 PG 端口导致 28 setup errors，未执行数据库逻辑；补齐既有 18432 配置后完成最终验证。主库不受影响。
- PG 证明 select-only maintainer 可读取事件，事务及角色切换正确；真实生产组合遇到旧 fixture 简化策略拒绝，cutover operation count=0。
- AR2 ar2-7：1831 scanned /159 classified /93 migrated，五类错误为空；diff check 通过。

历史控制/首装阶段测试明确替换新增消费门，仅测试原有阶段和登记资产职责；新增消费门测试另行覆盖其拒绝与当前资格调用。这些测试均不是主库端到端授权成功证据。无真实 Proposal/Approval/cutover 写入，无 API 重载，无 push。

下一波：当前主库身份/正式动作定义只读核查，完成定义发布及受控 Proposal/Approval 入口，运行真实 exact 审批与切换验收。仍需前端包交付、自然数据触发首链、八工作台经营计划与连续观察。
