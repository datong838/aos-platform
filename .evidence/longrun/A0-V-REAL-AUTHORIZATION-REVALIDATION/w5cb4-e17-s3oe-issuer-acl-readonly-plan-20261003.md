# E17-s3o-e｜正式发行身份与 DB ACL 只读审计计划

基线 `m1@1c2fbe0e`、`AOS-001189`、当前 `aos_current_preview_20260927@a0v_135` 只读；上位 231-4/231-9、W6-01、E17-s3l/s3m 与 D-waves 已读。此波只查事实并写下一施工方案，绝不在当前卷执行 GRANT/REVOKE/迁移。

1. 只读 SQL：确认连接角色与当前库/迁移；对 `aip_skill_binding`、`aip_capability_binding`、`aip_tool_binding`、`aip_agent_registry_receipt`、`aip_assignee_resolution_receipt` 回读 owner、`aos_runtime` 的 INSERT/UPDATE/DELETE、RLS/策略与触发器；列出发行相关角色和 SECURITY DEFINER 函数。只输出角色名和布尔值，不输出任何密码/secret。
2. 对照 `aip6_001`、`aip6_002`、`aip13_001`、`w6_001` 与当前安全迁移模式，明确哪类记录仍可被运行角色直接签发/篡改、谁应是窄发行身份、哪些命令需兼容。形成最小文件级迁移及隔离克隆 RED 清单，不直接编码或切换当前实例。
3. 输出 verification 与 01/06、D-waves、续接文档、Task/Authority/Prime，精确提交。审计结论只针对当前数据库权限；即使修 ACL，也不自动证明正式六绑定/Host/首链可执行。
