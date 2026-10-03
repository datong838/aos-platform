# s3o-w-s 第一切片｜受限函数精确六 ID

- 基线 `m1@b02d201e`、Authority `AOS-001231`，上位 231-3/231-9 与 D-wave s3o-w-s。只改原签名全 schema 一次性库的 test-only 函数/断言，未改生产服务、migration 或当前真实库。
- RED：额外插入第七个 active 测试 Agent 后，用五个 `BI_ROLE_BLUEPRINTS` ID 加一个未列 ID 调函数，原函数返回六行，`pytest.raises(InsufficientPrivilege)` 未触发，专项 exit1。
- 最小修复：函数要求传入六个互异 ID 的排序集合与 `BI_ROLE_BLUEPRINTS` 六个精确 ID 完全一致；保留同租户 GUC、`session_user`、active/version 和 `FOR SHARE`。仅精确发行角色可执行，错租户/缺 ID/重 ID/未列 ID/冒用均拒；原 BI prepare 在克隆继续产生1 Plan/1 配对 Receipt，并保持同键重放、停用和版本漂移负例。
- 原签名全 schema `1 passed` exit0，相邻 BI/安装/当前权限 `97 passed` exit0，`py_compile`/`git diff --check` exit0。一次性库、测试发行角色/函数零残留；当前实例 Plan/BI Receipt0，Host/worker/Provider关。
- 风险：精确 ID 由当前产品蓝图提供，不证明这六个当前正式 AgentInstance 已创建，也不为任意调用者提供 OIDC 身份认证。正式 migration/ACL/凭据、签名六 Agent 来源和当前卷切换需独立新备份、全链克隆、零执行窗口；不能将本切片当业务首链。
