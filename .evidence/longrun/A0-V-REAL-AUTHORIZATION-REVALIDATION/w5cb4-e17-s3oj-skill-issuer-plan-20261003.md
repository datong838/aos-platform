# W5CB4 E17-s3o-j｜原 SkillBinding 事务的独立发行权限计划

日期：2026-10-03。依据 231 总控、231-4 数据/权限、231-9 双侧增长、581 接续与 D-waves 原 Registry 下一波清单。此波只处理隔离库的原 SkillBinding create；CapabilityBinding 与 evaluate/update 在后续波逐项核对，不把夹具当正式签名发布。

## 已读事实与权限边界

- `AipSkillRegistry.create_binding` 在同一事务读取 `aip_skill_template_revision`、`aip_agent_instance`（原 `_instance_row` 同时 JOIN `aip_agent_template_revision`）、可选 `aip_capability_binding`，写 `aip_skill_binding` 与 `aip_agent_registry_receipt`。幂等回读 Receipt，绑定生命周期仍受 published/latest/publication_tenant 和能力覆盖校验。
- 既有独立 Registry issuer 只准 AgentInstance SIU、Registry Receipt SI，明确拒绝 SkillBinding 写。普通 runtime 当前真库仍可直写 Registry Receipt，因此正式当前库不能接入。
- 独立测试库撤普通 runtime 的 Registry Receipt 写权，先以原 create 命令复现回滚；然后给 Skill 专用登录 `aos_aip_skill_issuer` 的 `aip_skill_binding` SELECT/INSERT 及其租户 RLS，读取 CapabilityBinding 只授 SELECT，保持 AgentInstance 与 CapabilityBinding 写权关闭。原 Agent 登录 `aos_aip_registry_issuer` 保持不变；两组互斥最小 ACL 不能装进同一个登录。发行连接预检须按命令族精确校验登录、表权及 runtime 禁写。

## 文件与步骤

1. 新增 `services/aos-api/tests/aip/test_e17_s3oj_skill_issuer_pg.py`：隔离库真实原 Store、独立角色和私有 passfile；RED 是缺 SkillBinding 表权时原命令失败且无半成品。正向 create/replay、同 key 异载荷拒绝、跨租户不可见、runtime 直插 Receipt 被拒、issuer 不获 CapabilityBinding/ToolBinding/Assignee 写权；夹具仅 test-only。
2. 最小修改 `services/aos-api/aos_api/aip_registry_issuer_connection.py`：Skill 命令族只接受 `aos_aip_skill_issuer`，要求 SkillBinding SELECT/INSERT，不允许 UPDATE/DELETE；要求 CapabilityBinding SELECT、AgentInstance 仅 SELECT，仍拒绝其他跨域写权。Agent 命令族沿用旧登录与 ACL。此连接默认不接当前 API/Host。
3. 运行专项和相邻原 Registry 测试、语法检查和 diff 审查；适用时仅局部重载 API，复核健康。当前主库只读，绝不做 migration、GRANT、Host/worker/Provider 启动。
4. verification 落盘后按精确路径提交 m1，更新 D-waves、01/06、接续与 AOS/Prime Authority。未完成项继续列出 CapabilityBinding、SkillBinding evaluate/update、当前 ACL 切换/正式身份、六正式 Binding、八配置与自然首链。

回滚：移除未接线的连接权限调整和隔离测试；不触碰真实数据。若原命令依赖超出上述读写集，先记录 RED 与事务回滚，再修订本计划，不猜测扩大权限。
