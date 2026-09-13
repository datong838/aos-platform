# 内部切换 Proposal Owner 接线验证

基线 e393d5c8，沿用 cutover-proposal-owner-plan.md。m1 单写者；父 A0-V Lease 范围内开发。未重载 API、未写真实提案或切换。

## 实现

- 新增 ecommerce_growth_cutover_proposal_gate.py：同事务安装 CAS 锁、持久角色与安装 marking、当前 ActionType 快照 share lock、动作 marking 校验；返回绑定及当前持久角色，不授予角色、不提交事务。
- aip_action_store.py：固定两类内部动作在 direct Proposal、显式 Draft 创建/修改/提交接入当前门；创建、提交、审批原键回放之前重验当前条件。风险策略与服务端分类一致，不接受 Task/Run/ImpactPreview 混入。
- 审批重算绑定并核对原 stable Proposal hash，不升级旧无绑定记录。资格 hash 使用当前持久角色，保留独立 maker/checker、版本/hash CAS、时效及审批人数原规则。

## 本次证据

- Gate RED 8 failed（缺模块）；GREEN 79 passed 联合权限/绑定/风险测试。
- Owner RED 1 failed（原 actionBindingHash=None）；补齐后联合测试 95 passed，包括既有 AIP3 Action control 与 W5 显式 Draft/Proposal/Approval 流程。
- 最后增补动作身份一致性与资格 hash 校验：Owner 6 passed。
- AR2 ar2-7：1830 modules /159 classified /93 migrated；五类错误均为空。
- git diff --check 通过；项目 memory-validate GREEN，AOS-000573。

## 证据边界

Gate 使用隔离 PG，安装锁加载由最小 fixture 替代；角色、租户、marking、ActionType 查询为真实 SQL。Owner 用例使用隔离完整迁移数据库，当前 gate 由受控测试替身提供，验证真实 Proposal/Draft/Approval 持久化与回放门。两组组合不冒充真实租户端到端验收。

没有发布正式 ActionType、创建主库 Proposal、批准主库 Proposal 或切换 9 路由。原 legacy/fenced 路由不变。下一波：切换消费端重算内部绑定和当前审批资格/策略，补齐真实定义发布与受控提案路径，然后真实切换验收；前端领域包及经营首链仍在后续清单。
