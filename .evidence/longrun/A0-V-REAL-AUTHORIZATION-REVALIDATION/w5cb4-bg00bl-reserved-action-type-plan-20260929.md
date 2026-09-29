# W5CB4 BG-00bl｜五类策略系统动作 ID 通用写入保留门

复习 AGENTS.md、aos-engineering-delivery、231/231-5/231-9、BG-00bh～bk。五固定 ID 风险 floor 已存在但当前正式 ActionType 不存在；通用 ActionType 编辑与插件 seed 不能承担策略注册 Owner。本波只守住未来 ID，既不正式注册，也不开放策略 active。

文件级方案：在 `services/aos-api/aos_api/aip_policy_activation_action.py` 暴露纯 `require_generic_action_type_mutable`，对五个固定 ID 抛明确保留错误，其余 ID 原样通过。`services/aos-api/aos_api/routers/actions.py` 的通用 create/update 在任何 seed/DB 前调用，并映射为稳定 403 `AIP_POLICY_ACTION_TYPE_RESERVED`；`services/aos-api/aos_api/action_template_registry.py::upsert_action_type` 在 connect 前调用，阻止插件 seed 的 force/non-force 覆盖。新增 `services/aos-api/tests/aip/test_aip_policy_action_type_reservation.py` 先 RED，覆盖五 ID、相似 ID、create/update、seed 在无 DB 访问前拒绝；相邻通用功能回归。

不改 `meta_action_type` 数据、迁移/ACL、Action Proposal/Approval 或 Store。正常非保留 ActionType 路径及历史读取不改。专项/邻接、编译/diff 复审，verification 与精确 m1 提交。下一波应定义受控正式生产者/预览，只有原子消费与独立安全迁移齐备才能考虑解除 active 门。
