# W5CB4 E17-s3o-w-d｜Plan 与共享 Receipt 发行权限 RED 方案

日期：2026-10-03。已复习 231-3/4/5/9、栖月汇全店经营分析执行方案、当前 D-waves 与 s3o-w-a/b/c 证据。当前真库 `aos_current_preview_20260927@a0v_135` 只读；本波只在独立 `aos-ar1c-pg:18432` 的临时 schema 中验证，不提交高于 135 的 migration，不切运行进程身份。

## 文件级步骤

1. 在 `services/aos-api/tests/extension_runtime/test_plan_receipt_issuer_red_pg.py` 复用 `current_configuration_sources_case.source_case` 的真实 `w2_002` Plan ACL/RLS，及 `w2_001` 的共享 Receipt DDL/ACL 形状。先证 `aos_runtime` 能直接增添 Plan head，并能伪造 `responsibility_plan.*`/`bi_responsibility_plan.*` Receipt；同时证原 `content_draft.register` operation 的合法 INSERT 仍被当前 ACL 允许。把期望的禁止行为标 strict xfail，真实 SQL 通过即不可误报 GREEN。
2. 在隔离 schema 分别核验 generic/BI 的原 Store operation 白名单、successor 的 Plan head 直写与无 ProductionContract Receipt、content draft 的共享 Receipt 写路。写者清单与测试覆盖若不一致，先补证，不用只修改 generic Store 声称已封锁全部写者。
3. 在设计数据库触发器时，Plan head `INSERT/UPDATE/DELETE` 全覆盖，Receipt 依 operation 分流；仅 session_user 独立受限 issuer 可写 Plan operation，内容原写者在同等防伪发行合同下保留独立路径。runtime SELECT-only 的同键事务锁必须覆盖所有 Plan 写者，维持原幂等/CAS/失败回滚、跨租户拒绝。

## 边界与退出

- 本波 RED 不使用模拟结果作为正式来源或业务成功证据；不启 Host、worker、Provider，不触及当前业务库和商城源。
- 原 Store 的真实前置依赖、正式 OIDC/凭据与当前库 ACL 切换需后续独立波验证。若 RED 表明单角色无法区分内容与 Plan，方案必须先拆发行身份，不以 SQL 文本或应用层约定代替数据库权限。
- 专项测试、相邻回归、方案/代码复审和 verification 后，精确提交；D-waves 与 01/06/Prime 登记下一波正式隔离 issuer 合同。

## 本次执行界限

已落下步骤 1 的 RED 与相邻回归。步骤 2 仅从原代码列出了 generic/BI 的六个 operation、successor 的直接 Plan 写入、内容草稿的 `content_draft.register`；原 create/revise/freeze/successor 的完整受限身份正向调用尚未证明。步骤 3 的 issuer/trigger/读者替换未实现，必须留为下一波，不能把 strict xfail 算安全门 GREEN。
