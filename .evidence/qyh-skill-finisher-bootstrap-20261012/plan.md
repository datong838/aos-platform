# 受限finisher权限部署原型

Rules：AGENTS.md、231、已批准Skill生产链/D-wave。候选一当前原卷升级另正式维护门；候选二完整producer角色部署条件，选择二隔离原型。新增aip_skill_eval_finisher_bootstrap.py及test_skill_eval_finisher_bootstrap_pg.py，不推进已发布Alembic或真实库。

仅维护aos_app未切角色、非autocommit/SERIALIZABLE，必填exact DB/cluster/schema161；public Run/event实际owner aos_app且ENABLE/FORCE RLS。旧writer有效Run UPDATE及列UPDATE必须无；finisher预存在时须NOLOGIN/NOINHERIT/无特权/无parent或members/无现存表列grants，拒绝unknown，不夺角色。四policy命名若已存在拒绝，不覆盖；全部验证后保存点内建NOLOGIN角色（无LOGIN/member自动授权），Run仅SELECT+4列UPDATE、event仅SELECT/INSERT、双tenant限定SELECT/UPDATE/INSERT policies。caller独自commit；角色/旧权限/数据整体回滚可验证。

此原型不自动执行或初始化，不是当前正式部署器，正式操作还需独立零执行/备份/全恢复/Owner审批及精确资源合同。新完整UUID clone原生正向/错资源、事务、owner、role、policy、宽旧writer权限负向；旧ACL/RLS/数据守恒，不用测试账号授真实权。初始阶段无LDAP/OIDC或publisher密钥创建。生产链准入/外部调用/自然首链仍独立PENDING。

复审增量：除四个精确操作许可policy，新增Run/event两个只TO finisher的RESTRICTIVE双tenant policy，避免PUBLIC permissive策略绕过。旧角色policy不变，正向验证6policy及两限制策略精确角色；安装器仍维护原型，不授Source调用。
