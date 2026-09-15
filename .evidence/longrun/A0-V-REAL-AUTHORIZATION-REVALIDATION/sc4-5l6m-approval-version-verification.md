# SC4-5l6m 真实审批 writer 版本协议修复

Rules：m1、方案先行、隔离数据库、最小修改；不 push，主库不变，230 L0 挂起。

方案 29db84ba/14f54473；Task SC4-5L6M-APPROVAL-VERSION-20260916。

RED：实际 AipActionStore.decide 写出 Proposal.version=2、ApprovalEvent.proposal_version=1，原 current gate 报 current approval set binding differs。此前手工等版本 fixture 的 21 项绿测没有覆盖真实 writer 协议。

修复公共 Event 审批门禁：已批准方案版本必须为批准事件数量+1，批准版本从 1 连续且唯一；所有批准事件必须绑定当前方案内容、action binding 和 policy hash。原有效期限、角色、maker-checker、quorum、marking 与 exact reference 校验保留。Schedule Host 单事件前置检查只接受早于当前方案的批准，最终连续链由公共门禁核验。旧 fixture 版本同步真实 writer 语义。

真实 writer 测试覆盖 schedule/dispatch × 一人/两人批准，以及批准后额外版本跳跃拒绝；没有替换 decide SQL、guard 或返回模型。连接适配器只将 commit 留在 fixture 的回滚事务内，因此证明真实 writer 行协议，不声称独立提交或完整 Service 集成。

标准自动创建并销毁 _ti4_test 数据库（管理入口 18434 aos_test_admin）；writer/current/control/host 四文件 37 passed，7 既有警告，4.15 秒，退出 0。原 ProductEvent 审批 21 项已在标准隔离库运行，旧环境阻碍解除。diff check 通过。

下一项：完整 EventControlDispatchLifecycle 真实签名资产、安装、独立审批、SQL、Receipt 集成；还需复核 Registry 锁以及签名复验与提交之间的并发边界。未部署新包，真实业务八工作台与发布决定未完成。
