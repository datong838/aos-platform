# 内部控制绑定纯合同验证

基线3f215f3c；主库无cutover/rollback ActionType、无对应Proposal（cutover-approval-inventory.json，只读）。普通Proposal仅有ImpactPreview时生成action_binding_hash，故当前不能直接得到真实可用切换审批。补范围明确的内部控制内容绑定，未造Task/ImpactPreview或approved行。

新测试先9失败，实现后与阶段合同联合24 passed。覆盖固定两动作、完整ActionType snapshot哈希、Scope及执行纪元绑定、未知字段、布尔版本、错误9操作集、非UUID与缺原始登记。AR2扫描1829五类错误空，diff检查通过。纯函数不访问数据库或外部模型，不授予执行权限。

下一波接AIP Proposal生成与风险底线，保留外部动作原preview/draft门，切换端对新内部证明重算；实际maker/checker仍从当前持久角色和安装作用域判定。当前无真实切换审批、无切换执行；API仍运行c3e57bf9。
