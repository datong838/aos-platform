# 切换 Proposal 当前权限与风险基础切片验证

基线 b2874ad2，m1 单写者。按 cutover-proposal-owner-plan.md 串行细分实施，不代表 Proposal Owner 已接通。

- 两固定切换 ActionType 风险底线 R2；hint 只能提高，R4 仍 draftOnly/禁止执行；其余风险分类不变。
- CurrentControlPermission 增加可信 APPROVE 白名单，复用当前持久角色、租户、安装 marking 与事务锁。asset-install-approver/admin 可审，asset-installer/owner 不可审。未授予真实用户新角色。
- RED：21 failed / 41 passed，失败为原缺失的风险底线和审批操作支持。
- GREEN：81 passed，含两类动作、升风险、旧风险、Provider Health、绑定、当前权限、撤权/锁、租户/marking 拒绝。7 条现有依赖警告。
- AR2 ar2-7：1829 scanned / 159 classified / 93 migrated，五类错误为空。git diff --check 通过。

本片无真实 Proposal 创建、无真实审批、无切换写入、无 source/model 调用，也未重载 API。继续同事务当前 ActionType/安装/权限绑定，并接入 Proposal 创建、Draft 提交及决定（包含旧键回放前检查）。新内部绑定最终需由切换端重算；之后才能进行真实切换验收。
