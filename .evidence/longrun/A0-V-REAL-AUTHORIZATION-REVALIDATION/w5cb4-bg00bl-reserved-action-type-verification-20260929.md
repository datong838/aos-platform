# W5CB4 BG-00bl｜策略系统动作 ID 保留门验证

方案：`w5cb4-bg00bl-reserved-action-type-plan-20260929.md`。本波只修改纯保留判据、通用 ActionType 写入口和插件 seed，不写当前真实库。

1. RED：新增专项测试后运行 `services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/aip/test_aip_policy_action_type_reservation.py -q --tb=short --disable-warnings` 退出 2；集合阶段缺 `PolicyActivationActionTypeReserved`，说明原五 ID 无通用写入保留门。
2. GREEN：新增纯 helper 后，通用 `POST/PUT /v1/actions/types` 在 seed/DB 前映射为 403 `AIP_POLICY_ACTION_TYPE_RESERVED`；插件 `upsert_action_type(force=False/True)` 在 connect 前拒绝五固定 ID。相似 ID、普通 ID 通过 helper。专项与相邻风险/目标合同 `24 passed`，现有通用 ActionType 与插件路由回归 `6 passed`；均退出 0。
3. `compileall -q` 及 `git diff --check` 对三个生产文件退出 0。实现/方案复审：保留集合复用 BG-00bh 的固定映射，新增写门不改变读取或普通 ID 保存语义；没有当前 ActionType 注册、Proposal/Approval、Store active 开放和迁移。

风险：现有通用 ActionType 编辑器对非保留 ID 的角色模型未在本波重写；若未来需正式注册五系统 ID，必须新建受控 Owner、权限、签名/版本、产品预览与可审计迁移，而非取消本门。安装 approved、binding0、八候选0，Host/Owner/首链 pending；当前真实库只读、Host/worker/Provider 关闭。BG-00bm 应设计受控 NetworkPolicy ActionType 元数据与正式生产者在 test-only PG 的可验证最小切片，仍保持 active 禁入。
