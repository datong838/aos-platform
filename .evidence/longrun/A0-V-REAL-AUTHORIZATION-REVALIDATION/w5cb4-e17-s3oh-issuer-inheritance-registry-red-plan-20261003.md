# E17-s3o-h｜Assignee issuer 继承权限与 Registry 直写 RED

基线 `m1@67cffbb2`、`AOS-001192`。复习 231-4/231-9、s3og 隔离验证、`aip6_001/aip6_002`、原 Agent/Skill/Capability 同事务 Registry Receipt Store；本波为隔离权限审计/RED，不改当前原库、Alembic head 或正式 API。

1. 在新 disposable PG 复用 s3og 非 owner Assignee issuer 测试身份，查询其对 `aip_agent_registry_receipt`、`aip_skill_binding`、`aip_capability_binding`、`aip_tool_binding` 的实际 INSERT/UPDATE/DELETE；记录继承自 `aos_runtime` 的多余写权。只输出表名/布尔值，不打印测试密码。
2. 对普通 `aos_runtime` 直接伪造 Registry Receipt 写一条失败预期的测试，保留 RED；正向 org-org/dev-project，仅测试库事务，避免缺外键/约束造成假 RED。然后针对独立 Assignee issuer 的跨域 Registry 直写做失败预期测试。切片目标是**诊断**继承风险，不在同波擅自把原 Store 切到新身份。
3. 方案复审：单独 `GRANT` Assignee Receipt 给 issuer 但同时继承广域 runtime 权限不是最小权。RED 实际证实 Registry/Skill/Capability/Tool 四表的 I/U/D 全 true。**本波最小隔离修复**：只改 test-only fixture 和默认关闭的 issuer 连接身份校验，issuer 不再是 runtime 成员；对原 Resolver 四类候选的 `meta_membership`、AgentInstance/Template、Skill/Tool/Capability Binding 显式 SELECT，对 Assignee Receipt 仅 SELECT/INSERT；租户表仅为 issuer 新增同 org/project 的独立 RLS 策略。原 Resolver 正向/跨租户、四表无写权与 runtime 直写红线复验。Registry/Binding 原发行同事务命令另波设计；正式迁移需独立备份、ACL-faithful 克隆、零执行窗口。

本波只有测试/证据和下一步文件级设计；不得把 RED 或新 Task/文档说成安全修复或首链完成。测试和当前服务保持真库只读、Host/worker/Provider关闭。
