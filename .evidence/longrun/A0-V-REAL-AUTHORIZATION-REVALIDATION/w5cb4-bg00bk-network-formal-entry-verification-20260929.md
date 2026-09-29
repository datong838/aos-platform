# W5CB4 BG-00bk｜NetworkPolicy 正式入口只读结果

1. `aip_action_store.py::action_type_snapshot` 只从当前 `meta_action_type` 取固定 ID；BG-00bg 当前真实库只读查询证明 policy/budget ActionType 0。`aip_action_service.py` 的 Proposal/Draft 必先取得此快照，故 BG-00bh 风险 floor 与 BG-00bj target hash 不会自动生产可审批单。
2. `routers/actions.py` 的通用 `POST/PUT /v1/actions/types` 持久化全局 `meta_action_type`，`action_template_registry.py` 插件模板也能 upsert。该通用编辑入口目前没有为五个未来系统动作 ID 的保留规则，不能让其作为正式策略注册 Owner；下一最小独立代码切片应先拒绝通用创建/覆盖这五个固定 ID，并对其他 ActionType 保持兼容。
3. `routers/aip_actions.py` 已有 Draft、Proposal、decision、withdraw 与读取接口；`aip_action_service.py::decide` 做审批角色门。Web `/aip/drafts` 和 `ActionTypeEditorPage.tsx` 可见通用入口，但 NetworkPolicy 产品界面只让用户填 `approvalRef` 草稿；没有精确 NetworkPolicy activation preview/目标绑定/正式发起及当前审批导航。自由文本不等于正式批准。
4. `routers/aip_runtime_guard_policies.py::publish_network` 仍调用 Store `publish`；`aip_network_policy_store.py` 在幂等读后对新 active 无条件拒绝。BG-00bj 的纯绑定没有消费连接。后续 Producer 应服务端生成精确 proposal/preview，独立 checker 在当前身份/成员资格下决定；Store 必须同事务锁目标/head、重验 Proposal/Approval/撤销/期限/target hash，写唯一消费和 revision/Receipt，并有兼容迁移/ACL及当前卷独立安全波。不能先放开 422。

本波只读，无测试成功冒充业务。BG-00bl 先实现通用 ActionType 编辑/插件 seed 对五固定系统 ID 的保留禁入，RED 覆盖创建、更新和 seed，保留其他 ID；不登记正式 ActionType 或改当前库。之后才做正式 Producer/预览和原子消费。当前 approved 安装 binding0、八候选0、Host/Owner/自然首链 pending。
